#!/usr/bin/python3

from evdev import InputDevice, UInput, ecodes, categorize
import sys
import signal
import time

### SETUP ###
dev = InputDevice(sys.argv[1])
dev.grab()
ui = UInput.from_device(dev, name='keyboard-remapper')

def emit(code, value):
    ui.write(ecodes.EV_KEY, code, value)
    ui.syn()
def tap(*codes):
    for c in codes: emit(c, 1); time.sleep(0.01)
    for c in reversed(codes): emit(c, 0); time.sleep(0.01)

def cleanup(sig, frame):
    dev.ungrab()
    ui.close()
    sys.exit(0)
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


### LAYERS ###

class HoldTapLayer:
    def __init__(self, key, layer, tap_keys=None, tap_timeout=0.2,
                 lock_key=None, consume_unmapped=True):
        self.key = key
        self.layer = layer
        self.tap_keys = tap_keys      # keys to tap on short press, or None
        self.tap_timeout = tap_timeout
        self.lock_key = lock_key       # if set, this key toggles lock while held
        self.consume_unmapped = consume_unmapped

        self.pressed = False
        self.used = False
        self.time = 0
        self.locked = False
        self.active_keys = {}

    @property
    def active(self):
        return self.pressed != self.locked  # XOR; locked inverts

    def handle_key(self, event):
        if event.code != self.key:
            return event
        if event.value == 1:
            self.pressed = True
            self.used = False
            self.time = time.time()
        elif event.value == 0:
            self.pressed = False
            if not self.used and (time.time() - self.time) < self.tap_timeout:
                if self.tap_keys:
                    tap(*self.tap_keys)
        return None

    def handle_lock(self, event):
        if self.lock_key is None or event.code != self.lock_key:
            return event
        if self.pressed and event.value == 1:
            self.locked = not self.locked
            self.used = True
            return None
        return event

    def handle_active_release(self, event):
        if event.code not in self.active_keys:
            return event
        target, mods = self.active_keys[event.code]
        if event.value == 0:
            emit(target, 0)
            for m in reversed(mods): emit(m, 0)
            del self.active_keys[event.code]
        elif event.value == 2:
            emit(target, 2)
        return None

    def handle_layer_press(self, event):
        # mark as used regardless of lock state
        if self.pressed and event.value == 1 and event.code in self.layer:
            self.used = True

        if not self.active:
            return event

        if event.code in self.layer and event.value == 1:
            target, mods = self.layer[event.code]
            self.active_keys[event.code] = (target, mods)
            for m in mods: emit(m, 1)
            emit(target, 1)
            return None

        return None if self.consume_unmapped else event

    def handlers(self):
        h = [self.handle_key]
        if self.lock_key is not None:
            h.append(self.handle_lock)
        h.extend([self.handle_active_release, self.handle_layer_press])
        return h

nav = HoldTapLayer(
    key=ecodes.KEY_ESC,  # post caps/esc swap = physical capslock
    tap_keys=[ecodes.KEY_ESC],
    lock_key=ecodes.KEY_TAB,
    layer={
        ecodes.KEY_A:  (ecodes.KEY_LEFT,      [ecodes.KEY_LEFTCTRL]),
        ecodes.KEY_D:  (ecodes.KEY_RIGHT,     [ecodes.KEY_LEFTCTRL]),
        ecodes.KEY_Q:  (ecodes.KEY_LEFT,      []),
        ecodes.KEY_E:  (ecodes.KEY_RIGHT,     []),
        ecodes.KEY_1:  (ecodes.KEY_HOME,      []),
        ecodes.KEY_3:  (ecodes.KEY_END,       []),
        ecodes.KEY_W:  (ecodes.KEY_UP,        []),
        ecodes.KEY_S:  (ecodes.KEY_DOWN,      []),
        ecodes.KEY_R:  (ecodes.KEY_PAGEUP,    []),
        ecodes.KEY_F:  (ecodes.KEY_PAGEDOWN,  []),
        ecodes.KEY_Z:  (ecodes.KEY_BACKSPACE, [ecodes.KEY_LEFTCTRL]),
        ecodes.KEY_X:  (ecodes.KEY_DELETE,    [ecodes.KEY_LEFTCTRL]),
        ecodes.KEY_C:  (ecodes.KEY_BACKSPACE, []),
        ecodes.KEY_V:  (ecodes.KEY_DELETE,    []),
    },
)

alt_layer = HoldTapLayer(
    key=ecodes.KEY_LEFTALT,
    tap_keys=[ecodes.KEY_LEFTALT],
    layer={
        ecodes.KEY_Q:  (ecodes.KEY_KP7, []),
        ecodes.KEY_W:  (ecodes.KEY_KP8, []),
        ecodes.KEY_E:  (ecodes.KEY_KP9, []),
        ecodes.KEY_A:  (ecodes.KEY_KP4, []),
        ecodes.KEY_S:  (ecodes.KEY_KP5, []),
        ecodes.KEY_D:  (ecodes.KEY_KP6, []),
        ecodes.KEY_Z:  (ecodes.KEY_KP1, []),
        ecodes.KEY_X:  (ecodes.KEY_KP2, []),
        ecodes.KEY_C:  (ecodes.KEY_KP3, []),
    },
)


### STANDALONE HANDLERS ###

ralt_state = {'pressed': False, 'used': False}

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


### MAIN LOOP ###

active_handlers = [
    handle_nonkey,
    handle_ralt,
    handle_swap_caps_esc,
    *alt_layer.handlers(),
    *nav.handlers(),
]

for event in dev.read_loop():
    for handler in active_handlers:
        event = handler(event)
        if event is None:
            break
    else:
        ui.write_event(event)
        ui.syn()
