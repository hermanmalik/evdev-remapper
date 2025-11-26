from evdev import InputDevice, UInput, ecodes as e
import signal
import sys

class KeyRemapper:
    def __init__(self, device_path):
        self.dev = InputDevice(device_path)
        self.dev.grab()
        self.ui = UInput.from_device(self.dev)
        self.running = True
        signal.signal(signal.SIGINT, self._cleanup)
        signal.signal(signal.SIGTERM, self._cleanup)
    
    def _cleanup(self, *args):
        self.running = False
        self.dev.ungrab()
        self.ui.close()
        sys.exit(0)
    
    def type_string(self, text):
        """Convenience: emit string as keypresses"""
        # Implement shift logic, char->keycode mapping
        pass
    
    def run(self, handler):
        """Convenience: event loop with user callback"""
        for event in self.dev.read_loop():
            if not self.running:
                break
            handler(event, self.ui)

"""
example usage:

from keyremapper import KeyRemapper
from evdev import ecodes as e

def handle_event(event, ui):
    if event.type == e.EV_KEY and event.code == e.KEY_RIGHTALT:
        # Emit Alt+Tab
        ui.write(e.EV_KEY, e.KEY_LEFTALT, 1)
        ui.write(e.EV_KEY, e.KEY_TAB, 1)
        ui.syn()
        # etc...
        return
    
    ui.write_event(event)
    ui.syn()

KeyRemapper('/dev/input/by-id/...').run(handle_event)
"""