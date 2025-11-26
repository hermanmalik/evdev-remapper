from evdev import InputDevice, UInput, ecodes

dev = InputDevice('/dev/input/event0')

# Direct libevdev API access:
print(dev.capabilities(verbose=True))  # libevdev_has_event_code()
print(dev.name, dev.phys, dev.uniq)    # libevdev device properties
dev.grab()                              # libevdev_grab()

# Read with different flags:
for event in dev.read():  # LIBEVDEV_READ_FLAG_NORMAL
    pass

# Or use the lower-level API:
event = dev.read_one()  # Returns None or InputEvent

# Sync handling:
try:
    event = dev.read_one()
except BlockingIOError:
    pass  # SYN_DROPPED handling via exception