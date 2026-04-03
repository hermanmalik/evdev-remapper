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

# nav layer state
NAV_KEY = ecodes.KEY_ESC
NAVKEY_TAP_TIMEOUT = 0.2  # 200ms
navkey_pressed = False
navkey_used_as_modifier = False
navkey_press_time = 0
nav_active_keys = {}  # maps original key -> (target, mods)
NAV_LAYER = {
    ecodes.KEY_K:           (ecodes.KEY_LEFT,      []),
    ecodes.KEY_L:           (ecodes.KEY_RIGHT,     []),
    ecodes.KEY_J:           (ecodes.KEY_LEFT,      [ecodes.KEY_LEFTCTRL]),
    ecodes.KEY_SEMICOLON:   (ecodes.KEY_RIGHT,     [ecodes.KEY_LEFTCTRL]),
    ecodes.KEY_H:           (ecodes.KEY_HOME,      []),
    ecodes.KEY_APOSTROPHE:  (ecodes.KEY_END,       []),
    ecodes.KEY_I:           (ecodes.KEY_UP,        []),
    ecodes.KEY_COMMA:       (ecodes.KEY_DOWN,      []),
    ecodes.KEY_U:           (ecodes.KEY_BACKSPACE, []),
    ecodes.KEY_O:           (ecodes.KEY_DELETE,    []),
    ecodes.KEY_Y:           (ecodes.KEY_BACKSPACE, [ecodes.KEY_LEFTCTRL]),
    ecodes.KEY_P:           (ecodes.KEY_DELETE,    [ecodes.KEY_LEFTCTRL]),
}

def emit(code, value):
    ui.write(ecodes.EV_KEY, code, value)
    ui.syn()

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

    # Handle RAlt -> Alt+Tab on release (if not held for modifier)
    if event.code == ecodes.KEY_RIGHTALT:
        if event.value == 1:  # Press
            ralt_pressed = True
            ralt_used_as_modifier = False
            # Don't emit yet - wait to see if it's used as Level 3 shift
            continue
        elif event.value == 0:  # Release
            if not ralt_used_as_modifier:
                # RAlt was pressed alone - emit Alt+Tab
                emit(ecodes.KEY_LEFTALT, 1)
                time.sleep(0.01)
                emit(ecodes.KEY_LEFTCTRL, 1)
                time.sleep(0.01)
                emit(ecodes.KEY_TAB, 1)
                time.sleep(0.01)
                emit(ecodes.KEY_TAB, 0)
                time.sleep(0.05)
                emit(ecodes.KEY_LEFTALT, 0)
                time.sleep(0.01)
                emit(ecodes.KEY_LEFTCTRL, 0)
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
        emit(ecodes.KEY_RIGHTALT, 1)
        ralt_used_as_modifier = True

    # Numlock only works when shift is held
    #if event.code == ecodes.KEY_LEFTSHIFT:
    #    shift_state['left'] = bool(event.value)
    #elif event.code == ecodes.KEY_RIGHTSHIFT:
    #    shift_state['right'] = bool(event.value)
    #elif event.code == ecodes.KEY_NUMLOCK:
    #    if not any(shift_state.values()):
    #        continue

    # Swap CapsLock and Escape
    if event.code == ecodes.KEY_CAPSLOCK:
        event.code = ecodes.KEY_ESC
    elif event.code == ecodes.KEY_ESC:
        event.code = ecodes.KEY_CAPSLOCK

    # Handle nav key
    if event.code == NAV_KEY:
        if event.value == 1:
            navkey_pressed = True
            navkey_used_as_modifier = False
            navkey_press_time = time.time()
            continue
        elif event.value == 0:
            navkey_pressed = False
            if not navkey_used_as_modifier and (time.time() - navkey_press_time) < NAVKEY_TAP_TIMEOUT:
                emit(NAV_KEY, 1)
                emit(NAV_KEY, 0)
            continue
        elif event.value == 2:
            continue
    
    # Handle nav layer (check active keys OR nav key held)
    if event.code in nav_active_keys:
        target, mods = nav_active_keys[event.code]
        if event.value == 0:
            emit(target, 0)
            for m in reversed(mods): emit(m, 0)
            del nav_active_keys[event.code]
        elif event.value == 2:
            emit(target, 2)
        continue

    if navkey_pressed and event.code in NAV_LAYER:
        navkey_used_as_modifier = True
        target, mods = NAV_LAYER[event.code]
        if event.value == 1:
            nav_active_keys[event.code] = (target, mods)
            for m in mods: emit(m, 1)
            emit(target, 1)
        continue

    ui.write_event(event)
    ui.syn()