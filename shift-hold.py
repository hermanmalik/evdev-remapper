#!/usr/bin/env python3
import evdev
from evdev import ecodes, UInput, InputDevice
import time
import threading

# Timing thresholds (seconds)
TAP_THRESHOLD = 0.2
SHIFT_THRESHOLD = 0.5
REPEAT_DELAY = 0.5
REPEAT_RATE = 0.03

# Keys to apply tap-hold behavior to (KEY_A through KEY_Z)
TAPHOLD_KEYS = set(range(ecodes.KEY_A, ecodes.KEY_Z + 1))
class TapHold:
    def __init__(self):
        self.pressed_keys = {}  # keycode -> (press_time, shifted)
        self.last_repeat = {}
        
    def key_down(self, keycode, timestamp, ui):
        self.pressed_keys[keycode] = (timestamp, False)
        # Immediately output lowercase
        ui.write(ecodes.EV_KEY, keycode, 1)
        ui.write(ecodes.EV_KEY, keycode, 0)
        ui.syn()
        
    def key_up(self, keycode):
        self.pressed_keys.pop(keycode, None)
        self.last_repeat.pop(keycode, None)
        
    def check_held(self, timestamp, ui):
        """Check if any keys should be shifted or repeated"""
        for keycode, (press_time, shifted) in list(self.pressed_keys.items()):
            duration = timestamp - press_time
            
            # Shift if held medium duration and not yet shifted
            if TAP_THRESHOLD <= duration < SHIFT_THRESHOLD and not shifted:
                # Backspace the lowercase, output uppercase
                ui.write(ecodes.EV_KEY, ecodes.KEY_BACKSPACE, 1)
                ui.write(ecodes.EV_KEY, ecodes.KEY_BACKSPACE, 0)
                ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 1)
                ui.write(ecodes.EV_KEY, keycode, 1)
                ui.write(ecodes.EV_KEY, keycode, 0)
                ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
                ui.syn()
                self.pressed_keys[keycode] = (press_time, True)
                
            # Start repeating if held long
            elif duration >= SHIFT_THRESHOLD:
                last = self.last_repeat.get(keycode, press_time + SHIFT_THRESHOLD)
                if timestamp - last >= REPEAT_RATE:
                    ui.write(ecodes.EV_KEY, keycode, 1)
                    ui.write(ecodes.EV_KEY, keycode, 0)
                    ui.syn()
                    self.last_repeat[keycode] = timestamp
# class TapHold:
#     def __init__(self):
#         self.pressed_keys = {}  # keycode -> press_time
#         self.shifted_keys = set()  # keys that were shifted
#         self.repeating_keys = {}  # keycode -> last_repeat_time
        
#     def key_down(self, keycode, timestamp):
#         self.pressed_keys[keycode] = timestamp
#         self.shifted_keys.discard(keycode)
        
#     def key_up(self, keycode, timestamp):
#         if keycode not in self.pressed_keys:
#             return None
            
#         press_time = self.pressed_keys[keycode]
#         duration = timestamp - press_time
        
#         del self.pressed_keys[keycode]
#         self.repeating_keys.pop(keycode, None)
        
#         # Already shifted or repeated, just release
#         if keycode in self.shifted_keys:
#             return ('shift_release', keycode)
        
#         # Determine behavior based on duration
#         if duration < TAP_THRESHOLD:
#             return ('tap', keycode)
#         elif duration < SHIFT_THRESHOLD:
#             return ('shift_tap', keycode)
#         # else: was repeating, just release
        
#         return ('release', keycode)
    
#     def check_repeat(self, timestamp):
#         """Check if any held keys should start repeating"""
#         to_repeat = []
#         for keycode, press_time in list(self.pressed_keys.items()):
#             duration = timestamp - press_time
            
#             if duration >= SHIFT_THRESHOLD:
#                 last_repeat = self.repeating_keys.get(keycode, press_time + SHIFT_THRESHOLD)
#                 if timestamp - last_repeat >= REPEAT_RATE:
#                     to_repeat.append(keycode)
#                     self.repeating_keys[keycode] = timestamp
        
#         return to_repeat

def main():
    keyboard = InputDevice('/dev/input/event16')
    keyboard.grab()
    ui = UInput.from_device(keyboard, name="taphold-virtual-keyboard")
    
    taphold = TapHold()
    try:
        for event in keyboard.read_loop():
            timestamp = event.timestamp()
            
            # Check for shift/repeat
            taphold.check_held(timestamp, ui)
            
            if event.type == ecodes.EV_KEY:
                keycode = event.code
                
                if keycode not in TAPHOLD_KEYS:
                    ui.write(event.type, event.code, event.value)
                    ui.syn()
                    continue
                
                if event.value == 1:  # Key down
                    taphold.key_down(keycode, timestamp, ui)
                elif event.value == 0:  # Key up
                    taphold.key_up(keycode)
            else:
                ui.write(event.type, event.code, event.value)
            ui.syn()

    finally:
        keyboard.ungrab()
        ui.close()

if __name__ == '__main__':
    main()