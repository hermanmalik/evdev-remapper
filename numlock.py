#!/usr/bin/python3

from evdev import InputDevice, UInput, ecodes, categorize # linux/input-event-codes.h, linux/input.h, libevdev/libevdev-uinput.h, libevdev/libevdev.h
import sys # stdio, stdlib, string, unistd, fcntl
import signal
import time

# setup
dev = InputDevice(sys.argv[1]) # libevdev_new_from_fd
dev.grab() # libevdev_grab
ui = UInput.from_device(dev, name='keyboard-remapper') # libevdev_uinput_create_from_device

# state
shift_state = {'left': False, 'right': False}
ralt_pressed = False
ralt_used_as_modifier = False

# signal handling
def cleanup(sig, frame):
    dev.ungrab()
    ui.close()
    sys.exit(0)
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


for event in dev.read_loop():  # generator, as opposed to while on libevdev_next_event
    if event.type != ecodes.EV_KEY:
        ui.write_event(event) # libevdev_uinput_write_event
        ui.syn()
        continue

    # Handle RAlt -> Alt+Tab on release (if not used as modifier)
    if event.code == ecodes.KEY_RIGHTALT:
        if event.value == 1:  # Press
            ralt_pressed = True
            ralt_used_as_modifier = False
            # Don't emit yet - wait to see if it's used as Level 3 shift
            continue
        elif event.value == 0:  # Release
            if not ralt_used_as_modifier:
                # RAlt was pressed alone - emit Alt+Tab
                ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTALT, 1)
                ui.syn()
                time.sleep(0.01)
                ui.write(ecodes.EV_KEY, ecodes.KEY_TAB, 1)
                ui.syn()
                time.sleep(0.01)
                ui.write(ecodes.EV_KEY, ecodes.KEY_TAB, 0)
                ui.syn()
                time.sleep(0.05)
                ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTALT, 0)
                ui.syn()
            else:
                # RAlt was used as Level 3 shift - emit the release
                ui.write_event(event)
                ui.syn()
            ralt_pressed = False
            continue
        elif event.value == 2:  # Repeat
            # RAlt repeating means it was already emitted, pass through
            ui.write_event(event)
            ui.syn()
            continue
    
    # If RAlt is held and another key is pressed, RAlt is being used as modifier
    if ralt_pressed and event.value == 1 and not ralt_used_as_modifier:
        # First keypress while RAlt held - emit the RAlt press we held back
        ui.write(ecodes.EV_KEY, ecodes.KEY_RIGHTALT, 1)
        ui.syn()
        ralt_used_as_modifier = True

    # Numlock only works when shift is held
    if event.code == ecodes.KEY_LEFTSHIFT:
        shift_state['left'] = bool(event.value)
    elif event.code == ecodes.KEY_RIGHTSHIFT:
        shift_state['right'] = bool(event.value)
    elif event.code == ecodes.KEY_NUMLOCK:
        if not any(shift_state.values()):
            continue
    
    ui.write_event(event)
    ui.syn()
