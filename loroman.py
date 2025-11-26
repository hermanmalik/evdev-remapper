#!/usr/bin/env python3
from evdev import InputDevice, UInput, ecodes as e
import signal
import sys
import subprocess
import os
from collections import deque

# Map keycodes to characters (lowercase)
KEYMAP = {
    e.KEY_A: 'a', e.KEY_B: 'b', e.KEY_C: 'c', e.KEY_D: 'd', e.KEY_E: 'e',
    e.KEY_F: 'f', e.KEY_G: 'g', e.KEY_H: 'h', e.KEY_I: 'i', e.KEY_J: 'j',
    e.KEY_K: 'k', e.KEY_L: 'l', e.KEY_M: 'm', e.KEY_N: 'n', e.KEY_O: 'o',
    e.KEY_P: 'p', e.KEY_Q: 'q', e.KEY_R: 'r', e.KEY_S: 's', e.KEY_T: 't',
    e.KEY_U: 'u', e.KEY_V: 'v', e.KEY_W: 'w', e.KEY_X: 'x', e.KEY_Y: 'y',
    e.KEY_Z: 'z',
}

# Get actual user's UID (not root)
REAL_USER = os.environ.get('SUDO_USER')
USER_UID = os.environ.get('SUDO_UID', str(os.getuid()))
XDG_RUNTIME_DIR = f"/run/user/{USER_UID}"

# Environment for notify-send
NOTIFY_ENV = os.environ.copy()
NOTIFY_ENV.update({
    'DISPLAY': os.environ.get('DISPLAY', ':0'),
    'WAYLAND_DISPLAY': os.environ.get('WAYLAND_DISPLAY', 'wayland-0'),
    'XDG_RUNTIME_DIR': XDG_RUNTIME_DIR,
    'DBUS_SESSION_BUS_ADDRESS': f"unix:path={XDG_RUNTIME_DIR}/bus",
})
print(USER_UID, XDG_RUNTIME_DIR, os.environ.get('DISPLAY', ':0'), f"unix:path={XDG_RUNTIME_DIR}/bus")

class SequenceDetector:
    def __init__(self, device_path):
        self.dev = InputDevice(device_path)
        self.dev.grab()
        self.ui = UInput.from_device(self.dev, name='sequence-detector')
        self.running = True
        self.buffer = deque(maxlen=20)
        
        signal.signal(signal.SIGINT, self._cleanup)
        signal.signal(signal.SIGTERM, self._cleanup)
    
    def _cleanup(self, *args):
        self.running = False
        self.dev.ungrab()
        self.ui.close()
        sys.exit(0)
    
    def run(self):
        for event in self.dev.read_loop():
            if not self.running:
                break
            
            # Only process key press events
            if event.type == e.EV_KEY and event.value == 1:
                char = KEYMAP.get(event.code)
                if char:
                    self.buffer.append(char)
                    typed = ''.join(self.buffer)
                    
                    if 'loroman' in typed:
                        # not sure why this sudo version doesn't work
                        # subprocess.Popen(['sudo', '-u', REAL_USER, 'notify-send', 'dame mazapan'], env=NOTIFY_ENV)
                        subprocess.Popen(
                            ['runuser', '-u', REAL_USER, '--', 'notify-send', '-a', 'loroman', 'dame mazapán'],
                            env=NOTIFY_ENV
                        )
                        self.buffer.clear()
            
            # Pass through all events
            self.ui.write_event(event)
            if event.type == e.EV_KEY:
                self.ui.syn()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} /dev/input/eventX", file=sys.stderr)
        print("\nFind your keyboard with: sudo evtest", file=sys.stderr)
        sys.exit(1)
    
    detector = SequenceDetector(sys.argv[1])
    detector.run()