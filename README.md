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
