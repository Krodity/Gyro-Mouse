#!/usr/bin/env python3
"""GyroMouse: turn OpenTrack "UDP over network" output into relative mouse movement.

OpenTrack sends one packet per frame: six little-endian doubles
(x, y, z, yaw, pitch, roll), angles in degrees. Each packet's change in yaw/pitch
becomes a relative mouse move, so games that steer the camera with the mouse
follow your head.

Standard library only. Runs on Windows (SendInput) and Linux (/dev/uinput).
"""

import argparse
import math
import socket
import struct
import sys

# Defaults; every one can also be overridden on the command line (see --help).
UDP_IP = "127.0.0.1"
UDP_PORT = 4242
DEADZONE = 0.2            # degrees of change per packet ignored as jitter
YAW_SCALE_FACTOR = 40     # mouse counts per degree of yaw
PITCH_SCALE_FACTOR = 40   # mouse counts per degree of pitch
IDLE_RESET = 0.5          # seconds without packets before the next one is a fresh start

PACKET = struct.Struct("<6d")  # x, y, z, yaw, pitch, roll


def wrap_degrees(angle):
    """Fold an angle difference into [-180, 180) so crossing ±180° isn't a 360° jump."""
    return (angle + 180.0) % 360.0 - 180.0


class Mapper:
    """Turns successive (yaw, pitch) readings into whole-count mouse moves.

    Fractions of a count are carried over to the next packet instead of being
    truncated away, so slow head movement still moves the cursor.
    """

    def __init__(self, yaw_scale, pitch_scale, deadzone):
        self.yaw_scale = yaw_scale
        self.pitch_scale = pitch_scale
        self.deadzone = deadzone
        self.reset()

    def reset(self):
        self.prev = None
        self.carry_x = self.carry_y = 0.0

    def update(self, yaw, pitch):
        if self.prev is None:
            self.prev = (yaw, pitch)
            return 0, 0
        d_yaw = wrap_degrees(yaw - self.prev[0])
        d_pitch = pitch - self.prev[1]
        self.prev = (yaw, pitch)

        if abs(d_yaw) < self.deadzone:
            d_yaw = 0.0
        if abs(d_pitch) < self.deadzone:
            d_pitch = 0.0

        # Turning right lowers yaw, so negate it; positive pitch moves the cursor down.
        self.carry_x += -d_yaw * self.yaw_scale
        self.carry_y += d_pitch * self.pitch_scale
        dx, dy = int(self.carry_x), int(self.carry_y)
        self.carry_x -= dx
        self.carry_y -= dy
        return dx, dy


class WindowsMouse:
    """Relative moves through SendInput: the same path a physical mouse uses."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("mi", MOUSEINPUT)]

        self._send = ctypes.windll.user32.SendInput
        self._input = INPUT(type=0)          # INPUT_MOUSE
        self._input.mi.dwFlags = 0x0001      # MOUSEEVENTF_MOVE
        self._ref = ctypes.byref(self._input)
        self._size = ctypes.sizeof(INPUT)

    def move(self, dx, dy):
        self._input.mi.dx = dx
        self._input.mi.dy = dy
        self._send(1, self._ref, self._size)

    def close(self):
        pass


class UinputMouse:
    """A virtual mouse on /dev/uinput. Needs write access (usually the `input` group)."""

    EV_SYN, EV_KEY, EV_REL = 0x00, 0x01, 0x02
    REL_X, REL_Y, BTN_LEFT = 0x00, 0x01, 0x110
    UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_RELBIT = 0x40045564, 0x40045565, 0x40045566
    UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
    EVENT = struct.Struct("llHHi")  # struct input_event (time is filled in by the kernel)

    def __init__(self, path="/dev/uinput"):
        import fcntl
        import os
        self._ioctl = fcntl.ioctl
        self._fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
        self._write = os.write
        for bit, value in ((self.UI_SET_EVBIT, self.EV_KEY), (self.UI_SET_EVBIT, self.EV_REL),
                           (self.UI_SET_RELBIT, self.REL_X), (self.UI_SET_RELBIT, self.REL_Y),
                           # A button makes udev/libinput classify the device as a mouse.
                           (self.UI_SET_KEYBIT, self.BTN_LEFT)):
            fcntl.ioctl(self._fd, bit, value)
        # struct uinput_user_dev: name[80], input_id (bustype=BUS_VIRTUAL), ff_effects_max, abs tables.
        os.write(self._fd, struct.pack("80s4HI", b"GyroMouse", 0x06, 0, 0, 0, 0) + bytes(4 * 64 * 4))
        fcntl.ioctl(self._fd, self.UI_DEV_CREATE)

    def move(self, dx, dy):
        e = self.EVENT.pack
        self._write(self._fd, e(0, 0, self.EV_REL, self.REL_X, dx)
                    + e(0, 0, self.EV_REL, self.REL_Y, dy)
                    + e(0, 0, self.EV_SYN, 0, 0))

    def close(self):
        import os
        self._ioctl(self._fd, self.UI_DEV_DESTROY)
        os.close(self._fd)


def open_mouse():
    if sys.platform == "win32":
        return WindowsMouse()
    if sys.platform.startswith("linux"):
        return UinputMouse()
    sys.exit(f"GyroMouse: unsupported platform {sys.platform!r} (Windows and Linux only)")


def serve(sock, mapper, mouse):
    """Read packets until interrupted, moving the mouse for each one."""
    while True:
        try:
            data = sock.recv(64)
        except socket.timeout:
            # Tracker paused or stopped: don't treat the next packet as a giant delta.
            mapper.reset()
            continue
        if len(data) != PACKET.size:
            continue  # not an OpenTrack packet; ignore it rather than die
        _, _, _, yaw, pitch, _ = PACKET.unpack(data)
        if not (math.isfinite(yaw) and math.isfinite(pitch)):
            continue
        dx, dy = mapper.update(yaw, pitch)
        if dx or dy:
            mouse.move(dx, dy)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Turn OpenTrack UDP output into mouse movement.")
    p.add_argument("--host", default=UDP_IP, help="address to listen on (0.0.0.0 = all interfaces)")
    p.add_argument("--port", type=int, default=UDP_PORT)
    p.add_argument("--deadzone", type=float, default=DEADZONE,
                   help="per-packet change in degrees ignored as jitter")
    p.add_argument("--yaw-scale", type=float, default=YAW_SCALE_FACTOR, help="mouse counts per degree of yaw")
    p.add_argument("--pitch-scale", type=float, default=PITCH_SCALE_FACTOR,
                   help="mouse counts per degree of pitch")
    p.add_argument("--invert-x", action="store_true", help="flip horizontal direction")
    p.add_argument("--invert-y", action="store_true", help="flip vertical direction")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    mapper = Mapper(args.yaw_scale * (-1 if args.invert_x else 1),
                    args.pitch_scale * (-1 if args.invert_y else 1),
                    args.deadzone)
    mouse = open_mouse()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # The timeout also keeps Ctrl+C responsive: a blocking recv can't be interrupted on Windows.
    sock.settimeout(IDLE_RESET)
    try:
        sock.bind((args.host, args.port))
        print(f"GyroMouse listening on {args.host}:{args.port} (Ctrl+C to stop)")
        serve(sock, mapper, mouse)
    except KeyboardInterrupt:
        print("\nGyroMouse stopped")
    finally:
        sock.close()
        mouse.close()


if __name__ == "__main__":
    main()
