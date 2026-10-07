import os
import socket
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import GyroMouse as gm  # noqa: E402


def packet(yaw, pitch):
    return gm.PACKET.pack(0, 0, 0, yaw, pitch, 0)


class MapperTest(unittest.TestCase):
    def setUp(self):
        self.m = gm.Mapper(yaw_scale=40, pitch_scale=40, deadzone=0.2)

    def test_first_reading_only_sets_reference(self):
        self.assertEqual(self.m.update(10, 5), (0, 0))

    def test_direction_matches_original(self):
        self.m.update(0, 0)
        # yaw down (turn right) -> +x; pitch up -> +y, as in the original script
        self.assertEqual(self.m.update(-1, 1), (40, 40))

    def test_deadzone(self):
        self.m.update(0, 0)
        self.assertEqual(self.m.update(0.1, -0.1), (0, 0))

    def test_yaw_wraparound_is_small_move(self):
        self.m.update(179.5, 0)
        self.assertEqual(self.m.update(-179.5, 0), (-40, 0))

    def test_subpixel_motion_accumulates(self):
        m = gm.Mapper(yaw_scale=1, pitch_scale=1, deadzone=0)
        m.update(0, 0)
        moves = [m.update(-0.25 * i, 0)[0] for i in range(1, 11)]  # 2.5 counts total
        self.assertEqual(moves, [0, 0, 0, 1, 0, 0, 0, 1, 0, 0])  # the old int() cast gave all zeros
        self.assertEqual(m.carry_x, 0.5)

    def test_reset_forgets_reference(self):
        self.m.update(0, 0)
        self.m.reset()
        self.assertEqual(self.m.update(90, 90), (0, 0))


class FakeMouse:
    def __init__(self):
        self.moves = []

    def move(self, dx, dy):
        self.moves.append((dx, dy))


class ServeTest(unittest.TestCase):
    def test_end_to_end_over_udp(self):
        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx.bind(("127.0.0.1", 0))
        rx.settimeout(0.2)
        mouse = FakeMouse()
        t = threading.Thread(target=lambda: self._serve(rx, mouse), daemon=True)
        t.start()
        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for data in (packet(0, 0), b"garbage", packet(float("nan"), 0), packet(float("inf"), 0),
                     packet(-1, 0), packet(-1, 1)):
            tx.sendto(data, rx.getsockname())
        t.join(2)
        self.assertEqual(mouse.moves, [(40, 0), (0, 40)])

    def _serve(self, sock, mouse):
        mapper = gm.Mapper(40, 40, 0.2)
        timeouts = 0
        real_reset = mapper.reset

        def reset():  # stop after the first idle timeout
            nonlocal timeouts
            timeouts += 1
            real_reset()
            if timeouts > 1:
                raise SystemExit
        mapper.reset = reset
        try:
            gm.serve(sock, mapper, mouse)
        except SystemExit:
            pass


if __name__ == "__main__":
    unittest.main()
