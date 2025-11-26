#! /usr/bin/python3

from evdev import InputDevice, UInput, ecodes, categorize # linux/input-event-codes.h, linux/input.h, libevdev/libevdev-uinput.h, libevdev/libevdev.h
import sys
import threading
import time
import select
import signal
import argparse

# Parse command line arguments
parser = argparse.ArgumentParser(description='Mouse click spammer')
parser.add_argument('device', nargs='?', default='/dev/input/event8',
                    help='Input device path (default: /dev/input/event8)')
parser.add_argument('--cps', type=float, default=10.0,
                    help='Clicks per second (default: 10)')
args = parser.parse_args()

dev = InputDevice(args.device) # libevdev_new_from_fd
dev.grab() # libevdev_grab
ui = UInput.from_device(dev, name='mouse-spammer') # libevdev_uinput_create_from_device

spam_active = False
spam_lock = threading.Lock()

# signal handling
def cleanup(sig, frame):
    dev.ungrab()
    ui.close()
    sys.exit(0)
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def click_spammer():
    """Background thread that spams clicks when active"""
    click_delay = 1.0 / args.cps  # Convert CPS to delay between clicks
    while True:
        with spam_lock:
            should_spam = spam_active
        if should_spam:
            # Press
            ui.write(ecodes.EV_MSC, ecodes.MSC_SCAN, 0x90001)  # Add scan code
            ui.syn()
            ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)
            ui.syn()
            time.sleep(click_delay / 2)  # Hold for 50ms
            
            # Release
            ui.write(ecodes.EV_MSC, ecodes.MSC_SCAN, 0x90001)
            ui.syn()
            ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0)
            ui.syn()
            time.sleep(click_delay / 2)  # Wait 50ms before next click
        else:
            time.sleep(0.01)  # Don't busy-wait when inactive

# Start spam thread
time.sleep(1)
spam_thread = threading.Thread(target=click_spammer, daemon=True)
spam_thread.start()

# Main thread: handle mouse events
for event in dev.read_loop():
    if event.type == ecodes.EV_KEY:
        if event.code == ecodes.BTN_RIGHT and event.value == 1:  # Side button press
            with spam_lock:
                spam_active = True
                print("Spam started")
            continue  # Don't pass through the side button press
        
        elif event.code == ecodes.BTN_RIGHT and event.value == 0:  # Right click press
            with spam_lock:
                spam_active = False
                print("Spam stopped")
            continue  # Don't pass through the side button press
            # Fall through to pass the right click
        
        elif event.code == ecodes.BTN_LEFT and spam_active:
            # Block actual left clicks while spamming
            continue
    
    # Pass through all other events
    ui.write_event(event)
    ui.syn()