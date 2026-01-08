#!/usr/bin/env python3
from evdev import InputDevice, UInput, ecodes, categorize # linux/input-event-codes.h, linux/input.h, libevdev/libevdev-uinput.h, libevdev/libevdev.h
import sys # stdio, stdlib, string, unistd, fcntl
import select
import signal
import time

# setup
kbdfd = InputDevice(sys.argv[1])   # probably /dev/input/event16
mousefd = InputDevice(sys.argv[2]) # probably /dev/input/event17
playpausefd = InputDevice(sys.argv[3]) # probably /dev/input/event18
mousefd.grab() # libevdev_grab
playpausefd.grab()
# don't grab keybaord
vmouse = UInput.from_device(mousefd, name='mouse-remapper') # libevdev_uinput_create_from_device
vmousebuttons = UInput.from_device(playpausefd, name='mouse-remapper-button')
vkbd = UInput({
    ecodes.EV_KEY: [
        ecodes.KEY_LEFTCTRL,
        ecodes.KEY_C,
        ecodes.KEY_PLAYPAUSE,
        ecodes.KEY_NEXTSONG,
        ecodes.KEY_PREVIOUSSONG
    ]
}, name='mouse-remapper-kbd')

# state
shift_state = {'left': False, 'right': False}
ralt_pressed = False
ralt_used_as_modifier = False

# signal handling
def cleanup(sig, frame):
    mousefd.ungrab()
    vmouse.close()
    vkbd.close()
    sys.exit(0)
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


while True:
    # use select to read from both devices' generators
    r, _, _ = select.select([mousefd, kbdfd, playpausefd], [], [])
    shift_pressed = shift_state['left'] or shift_state['right']
    
    if kbdfd in r:
        for event in kbdfd.read():
            if event.type != ecodes.EV_KEY:
                continue
            if event.code == ecodes.KEY_LEFTSHIFT:
                shift_state['left'] = bool(event.value)
                print("left shift")
            elif event.code == ecodes.KEY_RIGHTSHIFT:
                shift_state['right'] = bool(event.value)
                print("right shift")
    
    if mousefd in r:
        for event in mousefd.read():
            if event.type != ecodes.EV_KEY:
                vmouse.write_event(event)
                vmouse.syn()
                continue
            
            # BTN_SIDE + Shift → Previous
            if event.code == ecodes.BTN_SIDE and shift_pressed:
                print("side button")
                vkbd.write(ecodes.EV_KEY, ecodes.KEY_PREVIOUSSONG, event.value)
                vkbd.syn()
                continue
            
            # BTN_EXTRA + Shift → Next
            if event.code == ecodes.BTN_EXTRA and shift_pressed:
                print("extra button")
                vkbd.write(ecodes.EV_KEY, ecodes.KEY_NEXTSONG, event.value)
                vkbd.syn()
                continue
            
            # Pass through other mouse buttons
            vmouse.write_event(event)
            vmouse.syn()

    if playpausefd in r:
        for event in playpausefd.read():
            print("got mouse button event" + str(event.type) + str(event.code))
            if event.type == ecodes.EV_KEY and event.code == ecodes.KEY_PLAYPAUSE:
                if shift_pressed:
                    print("middle button shift -> playpause")
                    vkbd.write(ecodes.EV_KEY, ecodes.KEY_PLAYPAUSE, event.value)
                    vkbd.syn()
                else:
                    print("middle button -> ctrl c")
                    vkbd.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 1)
                    vkbd.syn()
                    time.sleep(0.01)
                    vkbd.write(ecodes.EV_KEY, ecodes.KEY_C, 1)
                    vkbd.syn()
                    time.sleep(0.01)
                    vkbd.write(ecodes.EV_KEY, ecodes.KEY_C, 0)
                    vkbd.syn()
                    time.sleep(0.01)
                    vkbd.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 0)
                    vkbd.syn()
                continue

            vmousebuttons.write_event(event)
            vmousebuttons.syn()