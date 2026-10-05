# obs-multiscene-shortcuts

Switch the OBS main canvas and the Aitum Vertical Canvas together from one
keyboard shortcut. This works on Wayland, where OBS's own hotkeys don't.

It connects to OBS over WebSocket. The main canvas switches with
`SetCurrentProgramScene`, and the vertical canvas switches with the plugin's
`aitum-vertical-canvas` / `switch_scene` vendor request.

## Install

1. In OBS, open **Tools > WebSocket Server Settings** and check **Enable WebSocket server** (port 4455).
2. Install [pipx](https://pipx.pypa.io) and PySide6 (Qt for Python, used by the
   config editor) from your distro:
   ```sh
   sudo dnf install pipx python3-pyside6                # Fedora
   sudo apt install pipx python3-pyside6.qtwidgets      # Debian/Ubuntu
   ```
3. Install obs-multiscene-shortcuts:
   ```sh
   pipx install --system-site-packages git+https://github.com/FluffCycle/obs-multiscene-shortcuts.git
   ```
   This puts the `obs-multiscene` and `obs-multiscene-config` commands in
   `~/.local/bin` and installs their other dependencies automatically.
   `--system-site-packages` lets the editor use your distro's PySide6, which
   uses the system Qt and so matches your Plasma theme.
4. Optionally, add the config editor to your app launcher (it shows up as
   **OBS Multiscene Shortcuts**):
   ```sh
   obs-multiscene-config --install-desktop-entry
   ```

If you'd rather not install PySide6 from your distro, use
`pipx install 'obs-multiscene-shortcuts[gui] @ git+https://github.com/FluffCycle/obs-multiscene-shortcuts.git'`
instead. That pulls PySide6 from PyPI, which brings its own copy of Qt, so the
editor works but won't pick up the Breeze style.

To update, run the install command again with `--force`. To uninstall:

```sh
obs-multiscene-config --remove-desktop-entry
pipx uninstall obs-multiscene-shortcuts
```

From a clone, `pipx install --system-site-packages .` installs your local copy
(add `-e` so edits take effect without reinstalling).

## Creating presets

Run `obs-multiscene-config`, or open **OBS Multiscene Shortcuts** from the app
launcher.

If there's no config file yet, it asks for the WebSocket connection details and
creates one. Then it connects to OBS and lists your presets. To make a preset,
click **New**, give it a name, and pick a main scene and/or a vertical scene from
the scenes in OBS. Set a canvas to *(leave unchanged)* to leave that key out of
the preset. Each change is written to the config file as soon as you click
**Save Preset** or **Delete**.

If it can't connect, it tells you whether OBS isn't running or whether the
connection details look wrong, and lets you fix them.

The editor also shows the `obs-multiscene switch …` command for each preset,
ready to paste into a shortcut (see below).

You can also edit the config by hand: copy `config.example.toml` to
`~/.config/obs-multiscene/config.toml` and use `obs-multiscene scenes` to get
the exact scene names. Note that the editor rewrites the file when it saves, so
comments you add by hand are replaced with the standard ones.

## Usage

```sh
obs-multiscene switch gameplay                 # use a preset from the config
obs-multiscene switch -m "BRB" -v "BRB Vert"   # or name the scenes directly
obs-multiscene scenes                          # list scenes (* = live)
obs-multiscene presets                         # list presets
```

A switch takes about 50 ms. If something fails (OBS not running, a misspelled
scene), you get a desktop notification. Add `--verbose` to also get one when a
switch succeeds.

## Binding shortcuts in KDE Plasma

1. Open **System Settings > Keyboard > Shortcuts**.
2. Choose **Add New > Command or Script…**
3. Enter the command `obs-multiscene switch gameplay` (use the full path, e.g. `~/.local/bin/obs-multiscene`, if it isn't found).
4. Assign a key, such as Meta+F1 or a spare macro key.

Repeat for each preset. Desktop shortcuts are global, so they work while a game
has focus.
