#!/usr/bin/python3

from evdev import InputDevice, UInput, ecodes, categorize # linux/input-event-codes.h, linux/input.h, libevdev/libevdev-uinput.h, libevdev/libevdev.h
import sys # stdio, stdlib, string, unistd, fcntl
import signal
import time

# setup
dev = InputDevice(sys.argv[1]) # libevdev_new_from_fd
dev.grab() # libevdev_grab
ui = UInput.from_device(dev, name='keyboard-remapper') # libevdev_uinput_create_from_device

# cleaner rewrite:
# state stored
# - keys_down: (keycode pressed) -> (keycode sequence sent, time sent)
# - mappings: (layer, value, code) -> (arbitrary python code to run, but typically emit keys and record them in keys_down, or change layer)
#   - maps should allow mapping on keyup, tap vs hold distinctions, macros, etc
#
# handlers
# - first handle non-keypresses
# - then switch on event code
#   - on keyup:
#       - look in keys_down map for the keycode sequence sent, and send the corresponding up keys
#       - check which layer we are in and handle keyup remappings
#       - change layer if necessary
#   - on repeat:
#       - 
#   - on keydown:
#       - look for 


# state
shift_state = {'left': False, 'right': False}
ralt_state = {'pressed': False, 'used': False}
nav_state = {'pressed': False, 'used': False, 'time': 0, 'locked': False}
nav_active_keys = {}  # maps original key -> (target, mods) 

# nav layer
NAV_KEY = ecodes.KEY_ESC
NAV_LOCK = ecodes.KEY_TAB
NAVKEY_TAP_TIMEOUT = 0.2  # 200ms
NAV_LAYER = {
    # navigation
    ecodes.KEY_J:           (ecodes.KEY_LEFT,      [ecodes.KEY_LEFTCTRL]),
    ecodes.KEY_L:           (ecodes.KEY_RIGHT,     [ecodes.KEY_LEFTCTRL]),
    ecodes.KEY_U:           (ecodes.KEY_LEFT,      []),
    ecodes.KEY_O:           (ecodes.KEY_RIGHT,     []),
    ecodes.KEY_H:           (ecodes.KEY_HOME,      []),
    ecodes.KEY_SEMICOLON:   (ecodes.KEY_END,       []),
    ecodes.KEY_I:           (ecodes.KEY_UP,        []),
    ecodes.KEY_K:           (ecodes.KEY_DOWN,      []),
    ecodes.KEY_Y:           (ecodes.KEY_PAGEUP,    []),
    ecodes.KEY_P:           (ecodes.KEY_PAGEDOWN,  []),
    # delete and backspace
    ecodes.KEY_M:           (ecodes.KEY_BACKSPACE, [ecodes.KEY_LEFTCTRL]),
    ecodes.KEY_DOT:         (ecodes.KEY_DELETE,    [ecodes.KEY_LEFTCTRL]),
    ecodes.KEY_N:           (ecodes.KEY_BACKSPACE, []),
    ecodes.KEY_SLASH:       (ecodes.KEY_DELETE,    []),
    # window switching
    ecodes.KEY_Q:           (ecodes.KEY_KP7,       []),
    ecodes.KEY_W:           (ecodes.KEY_KP8,       []),
    ecodes.KEY_E:           (ecodes.KEY_KP9,       []),
    ecodes.KEY_A:           (ecodes.KEY_KP4,       []),
    ecodes.KEY_S:           (ecodes.KEY_KP5,       []),
    ecodes.KEY_D:           (ecodes.KEY_KP6,       []),
    ecodes.KEY_Z:           (ecodes.KEY_KP1,       []),
    ecodes.KEY_X:           (ecodes.KEY_KP2,       []),
    ecodes.KEY_C:           (ecodes.KEY_KP3,       []),
}
MACROS = {
    # ecodes.KEY_T: [ecodes.KEY_H, ecodes.KEY_E, ecodes.KEY_R,
    #                 ecodes.KEY_M, ecodes.KEY_A, ecodes.KEY_N],
}

def emit(code, value):
    ui.write(ecodes.EV_KEY, code, value)
    ui.syn()
def tap(*codes):
    for c in codes: emit(c, 1); time.sleep(0.01)
    for c in reversed(codes): emit(c, 0); time.sleep(0.01)

# signal handling
def cleanup(sig, frame):
    dev.ungrab()
    ui.close()
    sys.exit(0)
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

### HANDLERS ###
def handle_nonkey(event):
    if event.type != ecodes.EV_KEY:
        ui.write_event(event) # libevdev_uinput_write_event
        ui.syn()
        return None
    return event

def handle_ralt(event):
    # RAlt -> Alt+Tab on release (if not held for modifier)
    if event.code != ecodes.KEY_RIGHTALT:
        # If RAlt is held and another key is pressed, RAlt is being used as modifier
        if ralt_state['pressed'] and event.value == 1 and not ralt_state['used']:
            # First keypress while RAlt held - emit the RAlt press we held back
            emit(ecodes.KEY_RIGHTALT, 1)
            ralt_state['used'] = True
        return event

    if event.value == 1:
        # Don't emit yet - wait to see if it's used as Level 3 shift
        ralt_state.update(pressed=True, used=False)
    elif event.value == 0:
        if not ralt_state['used']:
            tap(ecodes.KEY_LEFTALT, ecodes.KEY_LEFTCTRL, ecodes.KEY_TAB)
        else:
            # RAlt was used as Level 3 shift - emit the release
            emit(ecodes.KEY_RIGHTALT, 0)
        ralt_state['pressed'] = False
    elif event.value == 2:
        # RAlt repeating means it was already emitted, pass through
        emit(ecodes.KEY_RIGHTALT, 2)
    return None

def handle_numlock(event):
    # Numlock only works when shift is held
    if event.code == ecodes.KEY_LEFTSHIFT:
       shift_state['left'] = bool(event.value)
    elif event.code == ecodes.KEY_RIGHTSHIFT:
       shift_state['right'] = bool(event.value)
    elif event.code == ecodes.KEY_NUMLOCK and event.value == 1:
       if not any(shift_state.values()):
           return None
    return event

def handle_swap_caps_esc(event):
    if event.code == ecodes.KEY_CAPSLOCK:
        event.code = ecodes.KEY_ESC
    elif event.code == ecodes.KEY_ESC:
        event.code = ecodes.KEY_CAPSLOCK
    return event

def handle_nav_key(event):
    if event.code != NAV_KEY:  # post-swap, so physical capslock
        return event

    if event.value == 1:
        nav_state.update(pressed=True, used=False)
        nav_state['time'] = time.time()
    elif event.value == 0:
        nav_state['pressed'] = False
        if not nav_state['used'] and (time.time() - nav_state['time']) < NAVKEY_TAP_TIMEOUT:
            tap(NAV_KEY)
    return None  # consume (including repeat)

def handle_nav_lock_toggle(event):
    if event.code == NAV_LOCK and nav_state['pressed'] and event.value == 1:
        nav_state['locked'] = not nav_state['locked']
        nav_state['used'] = True
        return None
    return event

def handle_nav_active_release(event):
    # this is separate to handle the race condition when the modkey is released first
    if event.code not in nav_active_keys:
        return event
    target, mods = nav_active_keys[event.code]
    if event.value == 0:
        emit(target, 0)
        for m in reversed(mods): emit(m, 0)
        del nav_active_keys[event.code]
    elif event.value == 2:
        emit(target, 2)
    return None

def handle_nav_layer_press(event):
    # any keypress while nav held = not a tap, even if layer is inactive
    if nav_state['pressed'] and event.value == 1 and event.code in NAV_LAYER:
        nav_state['used'] = True

    if nav_state['pressed'] == nav_state['locked']:
        return event

    if event.code not in NAV_LAYER or event.value != 1:
        return None
    
    target, mods = NAV_LAYER[event.code]
    nav_active_keys[event.code] = (target, mods)
    for m in mods: emit(m, 1)
    emit(target, 1)
    return None

def handle_macros(event):
    if event.code in MACROS and event.value == 1:
        for keycode in MACROS[event.code]:
            tap(keycode)
        return None
    return event


### MAIN LOOP ###
active_handlers = [
    handle_nonkey,
    handle_ralt,
    # handle_numlock,
    handle_swap_caps_esc,
    handle_nav_key,
    handle_nav_lock_toggle,
    handle_nav_active_release,
    handle_nav_layer_press,
    handle_macros,
]

for event in dev.read_loop():  # generator, as opposed to while on libevdev_next_event
    for handler in active_handlers:
        event = handler(event)
        if event is None:
            break
    else:
        ui.write_event(event)
        ui.syn()