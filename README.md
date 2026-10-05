# obs-multiscene

Switch the OBS main canvas and the Aitum Vertical Canvas together from one
keyboard shortcut. This works on Wayland, where OBS's own hotkeys don't.

It connects to OBS over WebSocket. The main canvas switches with
`SetCurrentProgramScene`, and the vertical canvas switches with the plugin's
`aitum-vertical-canvas` / `switch_scene` vendor request.

## Setup

1. In OBS, open **Tools > WebSocket Server Settings** and check **Enable WebSocket server** (port 4455).
2. Install the dependency: `pip install --user obsws-python`
3. Put the script on your PATH and create a config:
   ```sh
   ln -s "$PWD/obs-multiscene" ~/.local/bin/obs-multiscene
   mkdir -p ~/.config/obs-multiscene
   cp config.example.toml ~/.config/obs-multiscene/config.toml
   ```
4. Run `obs-multiscene scenes` to see the exact scene names, then edit the presets in the config.
   Or skip the `cp` in step 3 and this step, and use the GUI editor below.

## Editing presets with the GUI

```sh
ln -s "$PWD/obs-multiscene-config" ~/.local/bin/obs-multiscene-config
obs-multiscene-config
```

To add it to the app launcher (it shows up as **OBS Multiscene Config**), install
the `.desktop` file with the script's full path filled in:

```sh
mkdir -p ~/.local/share/applications
sed "s|^Exec=.*|Exec=$PWD/obs-multiscene-config|" obs-multiscene-config.desktop \
  > ~/.local/share/applications/obs-multiscene-config.desktop
```

If there's no config file yet, it asks for the WebSocket connection details and
creates one. Then it connects to OBS and lists your presets. To make a preset,
click **New**, give it a name, and pick a main scene and/or a vertical scene from
the scenes in OBS. Set a canvas to *(leave unchanged)* to leave that key out of
the preset. Each change is written to the config file as soon as you click
**Save preset** or **Delete**.

If it can't connect, it tells you whether OBS isn't running or whether the
connection details look wrong, and lets you fix them.

The GUI rewrites the config file, so comments you added by hand are replaced
with the standard ones. It needs PySide6 (Qt for Python). Install it from your distro so it uses the
system Qt and matches your Plasma theme: `sudo dnf install python3-pyside6` on
Fedora, `sudo apt install python3-pyside6.qtwidgets` on Debian/Ubuntu. A
`pip install pyside6` copy also works but brings its own Qt, so it won't pick up
the Breeze style.

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
