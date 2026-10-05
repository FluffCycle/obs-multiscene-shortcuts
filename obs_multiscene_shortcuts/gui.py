"""Small GUI for creating and editing the obs-multiscene-shortcuts config file.

It reads scene names straight from OBS, so presets can be built by picking
scenes instead of typing them. The config format is the same one the
`obs-multiscene` command reads.
"""

import argparse
import importlib.resources
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QStackedWidget,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    sys.exit(
        "obs-multiscene-config needs PySide6 (Qt for Python).\n"
        "Install it from your distro so it matches your desktop theme "
        "(Fedora: python3-pyside6, Debian/Ubuntu: python3-pyside6.qtwidgets),\n"
        "or reinstall obs-multiscene-shortcuts with its 'gui' extra (see the README)."
    )
from websocket import WebSocketAddressException, WebSocketConnectionClosedException

from obs_multiscene_shortcuts import cli

obs = cli.obs

UNCHANGED = "(leave unchanged)"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


# --- Config file ---------------------------------------------------------

def toml_str(s):
    out = []
    for ch in s:
        if ch in '"\\':
            out.append("\\" + ch)
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def toml_key(k):
    return k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else toml_str(k)


def toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    return toml_str(str(v))


def save_config(config):
    """Write the config atomically, readable only by the user (it may hold a password)."""
    lines = [
        "# obs-multiscene-shortcuts config. Edit by hand or with obs-multiscene-config.",
        "# Scene names must match OBS exactly (run `obs-multiscene scenes` to see them).",
        "",
        "[connection]",
    ]
    lines += [f"{toml_key(k)} = {toml_value(v)}" for k, v in config.get("connection", {}).items()]
    lines += [
        "",
        "# Each preset switches the main canvas and the vertical canvas together.",
        "# Leave out either key to leave that canvas unchanged.",
    ]
    for name, preset in config.get("presets", {}).items():
        lines += ["", f"[presets.{toml_key(name)}]"]
        lines += [f"{k} = {toml_value(preset[k])}" for k in ("main", "vertical") if preset.get(k)]

    path = cli.CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".config.", suffix=".toml")
    try:
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


# --- OBS -------------------------------------------------------------------

def obs_running():
    """True/False if we can tell whether OBS is running locally, None if we can't."""
    if not shutil.which("pgrep"):
        return None
    return subprocess.run(["pgrep", "-x", "obs"], capture_output=True).returncode == 0


def describe_failure(exc, conn):
    host, port = conn.get("host", "localhost"), conn.get("port", 4455)
    local = host in LOCAL_HOSTS
    if isinstance(exc, ConnectionRefusedError):
        if local and obs_running() is False:
            return "OBS isn't running. Open OBS, then click Save & Connect."
        return (
            f"Nothing is accepting connections on {host}:{port}.\n"
            "In OBS, check Tools > WebSocket Server Settings: the server must be enabled "
            "and the port must match."
        )
    if isinstance(exc, (socket.gaierror, WebSocketAddressException)):
        return f"Can't find the host {host!r}. Check the host name."
    if isinstance(exc, (TimeoutError, obs.error.OBSSDKTimeoutError)) or "timed out" in str(exc).lower():
        return f"Timed out connecting to {host}:{port}. Check the host and port."
    if "no password" in str(exc):
        return "OBS requires a password. Enter the one shown in Tools > WebSocket Server Settings."
    if isinstance(exc, (obs.error.OBSSDKError, WebSocketConnectionClosedException)):
        # OBS drops the connection when the password is wrong.
        return "OBS rejected the connection. Check the password in Tools > WebSocket Server Settings."
    return f"Couldn't connect: {exc}"


def fetch_scenes(config):
    """Return (main scenes, vertical scenes or None if the plugin isn't available)."""
    client = cli.connect(config)
    try:
        main = cli.main_scenes(client)
        try:
            vertical = cli.vertical_scenes(client)
        except obs.error.OBSSDKRequestError:
            vertical = None
        return main, vertical
    finally:
        client.disconnect()


# --- GUI -------------------------------------------------------------------

def icon(name):
    return QIcon.fromTheme(name)


def heading(text):
    label = QLabel(text)
    font = label.font()
    font.setPointSizeF(font.pointSizeF() * 1.3)
    font.setBold(True)
    label.setFont(font)
    return label


def shell_arg(s):
    return s if re.fullmatch(r"[A-Za-z0-9_.-]+", s) else "'" + s.replace("'", "'\\''") + "'"


class MessageBar(QWidget):
    """An icon plus a wrapped message, roughly like KDE's inline message widget."""

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.icon = QLabel()
        self.icon.setAlignment(Qt.AlignTop)
        self.text = QLabel()
        self.text.setWordWrap(True)
        layout.addWidget(self.icon)
        layout.addWidget(self.text, 1)
        self.hide()

    def show_message(self, text, kind="information"):
        if not text:
            self.hide()
            return
        size = self.style().pixelMetric(self.style().PixelMetric.PM_SmallIconSize)
        self.icon.setPixmap(icon(f"dialog-{kind}").pixmap(size))
        self.text.setText(text)
        self.show()


class ConnectionPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        layout = QVBoxLayout(self)
        layout.addWidget(heading("OBS connection"))
        self.message = MessageBar()
        layout.addWidget(self.message)

        form = QFormLayout()
        self.host = QLineEdit()
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        reveal = self.password.addAction(icon("view-visible"), QLineEdit.TrailingPosition)
        reveal.setToolTip("Show password")
        reveal.setCheckable(True)
        reveal.toggled.connect(lambda on: self.password.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        form.addRow("Host:", self.host)
        form.addRow("Port:", self.port)
        form.addRow("Password:", self.password)
        layout.addLayout(form)

        hint = (
            "Find these in OBS under Tools > WebSocket Server Settings (Show Connect Info). "
            "Leave the password empty if authentication is off."
        )
        if os.environ.get("OBS_WS_PASSWORD"):
            hint += "\nNote: OBS_WS_PASSWORD is set in your environment and overrides this password."
        hint_label = QLabel(hint)
        hint_label.setWordWrap(True)
        hint_label.setEnabled(False)  # dimmed, like KDE's secondary text
        layout.addWidget(hint_label)
        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel = QPushButton(icon("dialog-cancel"), "Cancel")
        self.cancel.clicked.connect(app.show_presets)
        connect = QPushButton(icon("network-connect"), "Save && Connect")  # && is a literal & in Qt
        connect.setDefault(True)
        connect.clicked.connect(self.save_and_connect)
        self.host.returnPressed.connect(self.save_and_connect)
        self.password.returnPressed.connect(self.save_and_connect)
        buttons.addWidget(self.cancel)
        buttons.addWidget(connect)
        layout.addLayout(buttons)

    def load(self, message, error):
        conn = self.app.config_data["connection"]
        self.host.setText(conn.get("host", "localhost"))
        self.port.setValue(conn.get("port", 4455))
        self.password.setText(conn.get("password", ""))
        self.message.show_message(message, "error" if error else "information")
        self.cancel.setVisible(bool(self.app.main_scenes))

    def save_and_connect(self):
        conn = self.app.config_data["connection"]
        conn.update(host=self.host.text().strip() or "localhost", port=self.port.value(), password=self.password.text())
        save_config(self.app.config_data)
        self.app.try_connect()


class PresetsPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.editing = None  # name of the preset being edited, None for a new one
        layout = QVBoxLayout(self)
        layout.addWidget(heading("Presets"))

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Preset", "Main scene", "Vertical scene"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(QHeaderView.Stretch)
        self.tree.currentItemChanged.connect(self.load_selected)
        layout.addWidget(self.tree, 1)

        # Editor for the selected (or a new) preset
        box = QGroupBox("Edit preset")
        form = QFormLayout(box)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. gameplay")
        self.main = QComboBox()
        self.vertical = QComboBox()
        form.addRow("Name:", self.name)
        form.addRow("Main canvas:", self.main)
        form.addRow("Vertical canvas:", self.vertical)
        self.warning = MessageBar()
        form.addRow(self.warning)

        command_row = QHBoxLayout()
        self.command = QLineEdit()
        self.command.setReadOnly(True)
        self.command.setToolTip("Bind this command to a shortcut in System Settings > Keyboard > Shortcuts")
        copy = QPushButton(icon("edit-copy"), "")
        copy.setToolTip("Copy command")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.command.text()))
        command_row.addWidget(self.command, 1)
        command_row.addWidget(copy)
        form.addRow("Shortcut command:", command_row)

        buttons = QHBoxLayout()
        buttons.addStretch()
        new = QPushButton(icon("list-add"), "New")
        new.clicked.connect(self.new_preset)
        self.delete = QPushButton(icon("edit-delete"), "Delete")
        self.delete.clicked.connect(self.delete_preset)
        save = QPushButton(icon("document-save"), "Save Preset")
        save.clicked.connect(self.save_preset)
        self.name.returnPressed.connect(self.save_preset)
        for b in (new, self.delete, save):
            buttons.addWidget(b)
        form.addRow(buttons)
        layout.addWidget(box)

        # Footer
        footer = QHBoxLayout()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setEnabled(False)
        footer.addWidget(self.status, 1)
        reload_button = QPushButton(icon("view-refresh"), "Reload Scenes")
        reload_button.clicked.connect(app.try_connect)
        conn_button = QPushButton(icon("configure"), "Connection…")
        conn_button.clicked.connect(lambda: app.show_connection("Edit your OBS WebSocket details."))
        footer.addWidget(reload_button)
        footer.addWidget(conn_button)
        layout.addLayout(footer)

        self.name.textChanged.connect(self.update_hints)
        self.main.currentIndexChanged.connect(self.update_hints)
        self.vertical.currentIndexChanged.connect(self.update_hints)

    @property
    def presets(self):
        return self.app.config_data["presets"]

    def load(self):
        if self.app.vertical_scenes is None:
            self.status.setText("Aitum Vertical Canvas plugin not detected; vertical scenes can't be listed.")
        else:
            self.status.setText(f"Config: {str(cli.CONFIG_PATH).replace(str(Path.home()), '~', 1)}")
        self.refresh_tree(select=self.editing if self.editing in self.presets else next(iter(self.presets), None))
        if not self.presets:
            self.new_preset()

    def refresh_tree(self, select=None):
        self.tree.blockSignals(True)
        self.tree.clear()
        for name, p in self.presets.items():
            item = QTreeWidgetItem([name, p.get("main", "—"), p.get("vertical", "—")])
            item.setData(0, Qt.UserRole, name)
            self.tree.addTopLevelItem(item)
            if name == select:
                self.tree.setCurrentItem(item)
        self.tree.blockSignals(False)
        if select:
            self.fill_editor(select, self.presets[select])

    @staticmethod
    def fill_combo(combo, scenes, current):
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(UNCHANGED, None)
        for s in scenes or []:
            combo.addItem(s, s)
        # Keep scenes that are in the config but missing from OBS selectable, so they aren't silently dropped.
        if current and current not in (scenes or []):
            combo.addItem(icon("dialog-warning"), f"{current} (not in OBS)", current)
        combo.setCurrentIndex(max(combo.findData(current), 0) if current else 0)
        combo.blockSignals(False)

    def fill_editor(self, name, preset):
        self.editing = name
        self.fill_combo(self.main, self.app.main_scenes, preset.get("main"))
        self.fill_combo(self.vertical, self.app.vertical_scenes, preset.get("vertical"))
        self.vertical.setEnabled(self.app.vertical_scenes is not None or bool(preset.get("vertical")))
        self.name.setText(name or "")
        self.delete.setEnabled(bool(name))
        self.update_hints()

    def load_selected(self, item):
        if item:
            name = item.data(0, Qt.UserRole)
            self.fill_editor(name, self.presets[name])

    def new_preset(self):
        self.tree.blockSignals(True)
        self.tree.setCurrentItem(None)
        self.tree.clearSelection()
        self.tree.blockSignals(False)
        self.fill_editor(None, {})
        self.name.setFocus()

    def update_hints(self):
        warnings = []
        main, vertical = self.main.currentData(), self.vertical.currentData()
        if main and main not in self.app.main_scenes:
            warnings.append(f"Main scene “{main}” doesn't exist in OBS.")
        if vertical and self.app.vertical_scenes is not None and vertical not in self.app.vertical_scenes:
            warnings.append(f"Vertical scene “{vertical}” doesn't exist in OBS.")
        self.warning.show_message("\n".join(warnings), "warning")
        name = self.name.text().strip()
        self.command.setText(f"obs-multiscene switch {shell_arg(name)}" if name else "")

    def save_preset(self):
        name = self.name.text().strip()
        main, vertical = self.main.currentData(), self.vertical.currentData()
        if not name:
            QMessageBox.warning(self, "Missing name", "Give the preset a name.")
            return
        if name != self.editing and name in self.presets:
            QMessageBox.warning(self, "Name taken", f"A preset named “{name}” already exists.")
            return
        if not (main or vertical):
            QMessageBox.warning(self, "Nothing to switch", "Pick a main scene, a vertical scene, or both.")
            return

        preset = {}
        if main:
            preset["main"] = main
        if vertical:
            preset["vertical"] = vertical
        # Rebuild the dict so a renamed preset keeps its position.
        if self.editing in self.presets:
            self.app.config_data["presets"] = {
                (name if k == self.editing else k): (preset if k == self.editing else v) for k, v in self.presets.items()
            }
        else:
            self.presets[name] = preset
        save_config(self.app.config_data)
        self.refresh_tree(select=name)
        self.status.setText(f"Saved preset “{name}”.")

    def delete_preset(self):
        name = self.editing
        if not name:
            return
        answer = QMessageBox.question(self, "Delete preset", f"Delete the preset “{name}”?")
        if answer != QMessageBox.Yes:
            return
        del self.presets[name]
        save_config(self.app.config_data)
        self.refresh_tree()
        self.new_preset()
        self.status.setText(f"Deleted preset “{name}”.")


class App(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OBS Multiscene Shortcuts")
        self.setWindowIcon(QIcon.fromTheme("preferences-desktop-keyboard-shortcut", icon("input-keyboard")))
        self.resize(640, 520)
        self.config_data = cli.load_config()
        self.config_data.setdefault("connection", {})
        self.config_data.setdefault("presets", {})
        self.main_scenes, self.vertical_scenes = [], None
        self.connection_page = ConnectionPage(self)
        self.presets_page = PresetsPage(self)
        self.addWidget(self.connection_page)
        self.addWidget(self.presets_page)

    def start(self):
        if cli.CONFIG_PATH.exists():
            self.try_connect()
        else:
            self.show_connection("No config file yet. Enter your OBS WebSocket details to create one.")

    def try_connect(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            self.main_scenes, self.vertical_scenes = fetch_scenes(self.config_data)
        except Exception as e:
            self.show_connection(describe_failure(e, self.config_data["connection"]), error=True)
        else:
            self.show_presets()
        finally:
            QApplication.restoreOverrideCursor()

    def show_connection(self, message, error=False):
        self.connection_page.load(message, error)
        self.setCurrentWidget(self.connection_page)

    def show_presets(self):
        self.presets_page.load()
        self.setCurrentWidget(self.presets_page)


# --- Desktop entry ---------------------------------------------------------

DESKTOP_ID = "obs-multiscene-config"


def desktop_entry_path():
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data_home / "applications" / f"{DESKTOP_ID}.desktop"


def install_desktop_entry():
    # Launchers may not have ~/.local/bin on PATH, so point Exec at this command's full path.
    command = shutil.which(DESKTOP_ID) or os.path.abspath(sys.argv[0])
    template = importlib.resources.files(__package__).joinpath(f"{DESKTOP_ID}.desktop").read_text()
    entry = re.sub(r"^Exec=.*$", f"Exec={command}", template, flags=re.M)
    path = desktop_entry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(entry)
    print(f"Installed {path}")


def remove_desktop_entry():
    path = desktop_entry_path()
    if path.exists():
        path.unlink()
        print(f"Removed {path}")
    else:
        print(f"Nothing to remove at {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    entry = parser.add_mutually_exclusive_group()
    entry.add_argument("--install-desktop-entry", action="store_true", help="add this editor to the app launcher")
    entry.add_argument("--remove-desktop-entry", action="store_true", help="remove it from the app launcher")
    args = parser.parse_args()
    if args.install_desktop_entry:
        return install_desktop_entry()
    if args.remove_desktop_entry:
        return remove_desktop_entry()

    logging.getLogger("obsws_python").setLevel(logging.CRITICAL + 1)  # we report errors ourselves
    qt_app = QApplication([])
    qt_app.setApplicationName("obs-multiscene-config")
    qt_app.setDesktopFileName("obs-multiscene-config")
    window = App()
    window.show()
    window.start()
    qt_app.exec()


if __name__ == "__main__":
    main()
