
goals
- basic key remapping
- layers (momentary / toggle)
- time.time() for tap vs hold
- macros: sequences of key events with `time.sleep()` for delays between events
- macro recording: record events to list, replay via uinput.
- combos: simultaneous keypresses = small time window
- easy modifier keys, support both tap and hold
- chord detection using a set()?
- context-aware remapping: use D-Bus (`dbus-python`), conditionally apply mappings based on window class. this also should allow KWin script integration (KWin D-Bus methods)
- emit unicode with ~~Ctrl+Shift+U sequence~~ (that doesn't work systemwide) XTest/uinput with proper keysym
- tap dance = count rapid taps within timeout, emit different keys based on tap count.
- leader key: Detect leader key press, buffer next N keys, match against command sequences.
- device-specific config
- device hot-plugging: Use `pyudev` to monitor `/dev/input` for new devices, automatically grab them.
- hold to shift, hold longer for repeat
- text expansion: use `buffer.endswith(trigger)` to detect triggers. could upgrade to regex triggers.
- compose sequences: same mechanism
- script execution
- bash built in? 
- clipboard features using wl-copy and wl-paste
- cursor positioning / effects
- window management: `wmctrl` subprocess or KWin D-Bus

features i don't care about
- dynamic config reload - `watchdog` library
- tkinter config editor
- layout switching
- Cmd-button with `subprocess.run()` - maybe better handled by rofi
- smart form-filling - more easily handled by password manager
- system tray options using `pystray`.
- clipboard history - just use the KDE one
- clipboard manipulation - solid maybe
- AHK's image search: use OpenCV (`cv2`) to find images on screen
- pixel color detection: Use `pyscreenshot` + `PIL` to read screen pixels