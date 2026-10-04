# GyroMouse

GyroMouse turns [OpenTrack](https://github.com/opentrack/opentrack) head-tracking output into ordinary mouse movement. Any game that aims or looks around with the mouse can then follow your head, even if it has no head-tracking support.

It's a single Python file with no dependencies, and it runs on **Windows** and **Linux**.

```
head tracker ──► OpenTrack ──UDP 4242──► GyroMouse ──► mouse movement ──► game
 (webcam, phone gyro, IMU, …)
```

## Contents

- [Quick start](#quick-start)
- [Setting up OpenTrack](#setting-up-opentrack)
- [Command-line options](#command-line-options)
- [Tuning](#tuning)
- [Linux setup](#linux-setup)
- [How it works](#how-it-works)
- [Packet format](#packet-format)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

## Quick start

1. Install **Python 3.8 or newer**. Nothing else is needed.
2. Download `GyroMouse.py`, or clone the repo:
   ```sh
   git clone https://github.com/Krodity/Gyro-Mouse.git
   cd Gyro-Mouse
   ```
3. Set OpenTrack's output to **UDP over network** (see [below](#setting-up-opentrack)) and press **Start**.
4. Run GyroMouse:
   ```sh
   python GyroMouse.py
   ```
5. Move your head and the mouse follows. Press **Ctrl+C** to stop.

On Linux, read [Linux setup](#linux-setup) first. GyroMouse needs write access to `/dev/uinput`.

## Setting up OpenTrack

1. **Input:** choose your tracker, for example a webcam with *neuralnet tracker*, a phone app, or an IMU.
2. **Output:** choose **UDP over network**, then click the 🔨 button next to it:
   - **IP address:** `127.0.0.1`, or the IP of the PC running GyroMouse if it's a different machine
   - **Port:** `4242`
3. **Filter:** *Accela* (OpenTrack's default) works well. Smoothing in OpenTrack is better than raising GyroMouse's deadzone.
4. Press **Start**, then start GyroMouse.

OpenTrack's own *Mapping* curves still apply. GyroMouse sees the angles after mapping, so you can shape the response there too.

## Command-line options

Every setting has a default, so `python GyroMouse.py` with no options works out of the box.

| Option | Default | What it does |
|---|---|---|
| `--host` | `127.0.0.1` | Address to listen on. Use `0.0.0.0` to accept packets from other machines. |
| `--port` | `4242` | UDP port. It must match OpenTrack's output port. |
| `--yaw-scale` | `40` | Horizontal sensitivity, in mouse counts per degree of head turn. |
| `--pitch-scale` | `40` | Vertical sensitivity, in mouse counts per degree of head tilt. |
| `--deadzone` | `0.2` | Per-packet change, in degrees, that's ignored as jitter. |
| `--invert-x` | off | Flip horizontal direction. |
| `--invert-y` | off | Flip vertical direction. |

Example: listen on the network, with faster horizontal movement and an inverted vertical axis:

```sh
python GyroMouse.py --host 0.0.0.0 --yaw-scale 60 --invert-y
```

If you'd rather not type options, you can change the defaults at the top of `GyroMouse.py`:

```python
UDP_IP = "127.0.0.1"
UDP_PORT = 4242
DEADZONE = 0.2
YAW_SCALE_FACTOR = 40
PITCH_SCALE_FACTOR = 40
```

## Tuning

- **Too slow or too fast:** change `--yaw-scale` and `--pitch-scale`. Also check the game's own mouse sensitivity, because the two multiply.
- **Cursor creeps when your head is still:** first try more smoothing in OpenTrack's filter, then raise `--deadzone` a little (for example to `0.3`).
- **Slow, small turns are ignored:** lower `--deadzone`. The deadzone is checked against the change in *each packet*, so it scales with OpenTrack's output rate. At 250 Hz, a 0.2° deadzone ignores turns slower than about 50°/s. With a smooth tracker, `0.05` or even `0` is often fine.
- **Directions are backwards:** use `--invert-x` or `--invert-y`.
- **Roll** (tilting your head sideways) and position (x/y/z) aren't used.

## Linux setup

On Linux, GyroMouse creates a virtual mouse named **"GyroMouse"** through `/dev/uinput`. It works on both X11 and Wayland, and in native games as well as games running under Proton or Wine.

Your user needs write access to `/dev/uinput`. Many distros grant that to the `input` group:

```sh
ls -l /dev/uinput          # e.g. crw-rw---- root input
sudo usermod -aG input $USER   # then log out and back in
```

If `/dev/uinput` is owned by `root` only, add a udev rule:

```sh
echo 'KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"' \
  | sudo tee /etc/udev/rules.d/99-uinput.rules
sudo udevadm control --reload && sudo udevadm trigger
```

If the module isn't loaded, run `sudo modprobe uinput`.

OpenTrack runs natively on Linux, so the whole pipeline can stay on one machine.

## How it works

For every packet OpenTrack sends, GyroMouse:

1. Reads yaw and pitch.
2. Subtracts the previous packet's values to get how far your head moved.
3. Wraps yaw changes into ±180°, so turning past the back of the tracker's range doesn't make the cursor jump.
4. Drops changes smaller than the deadzone.
5. Multiplies by the scale to get mouse counts. Any fraction of a count is **carried over** to the next packet, so slow movements still add up instead of being rounded away.
6. Sends the whole-count part as a relative mouse move. On Windows this uses `SendInput`; on Linux it uses the uinput virtual mouse.

If no packets arrive for 0.5 s (for example, OpenTrack is paused), GyroMouse forgets the last position. The first packet after the pause is then treated as a fresh start instead of a big jump.

Packets that aren't exactly 48 bytes are ignored, so a stray packet on the port can't crash it.

## Packet format

GyroMouse uses OpenTrack's "UDP over network" format: six little-endian 64-bit floats, 48 bytes per packet.

| Index | Value | Unit | Used |
|---|---|---|---|
| 0 | x | cm | no |
| 1 | y | cm | no |
| 2 | z | cm | no |
| 3 | yaw | degrees | **yes** |
| 4 | pitch | degrees | **yes** |
| 5 | roll | degrees | no |

You can feed it from your own program instead of OpenTrack:

```python
import socket, struct
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(struct.pack("<6d", 0, 0, 0, yaw, pitch, 0), ("127.0.0.1", 4242))
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Nothing happens | Check that OpenTrack is started and its output is **UDP over network** with the same IP and port. GyroMouse ignores packets until the second one arrives, because it needs two readings to compute a change. |
| `OSError: address already in use` | Something else is on port 4242, such as another GyroMouse or an OpenTrack *input* set to UDP. Use `--port`, and change OpenTrack's output port to match. |
| Packets from another PC or a phone don't arrive | Start with `--host 0.0.0.0` and allow incoming UDP on the port in your firewall. |
| Cursor moves on the desktop but not in the game | The game must use the mouse for camera control. Some anti-cheat systems block injected input. |
| Movement feels accelerated (Windows) | In the desktop and games without raw input, Windows *Enhance pointer precision* applies to injected moves. Turn it off under Mouse settings → Additional mouse options → Pointer Options. |
| `PermissionError` on `/dev/uinput` (Linux) | See [Linux setup](#linux-setup). |

## Development

The tests use only the standard library:

```sh
python -m unittest discover -s tests -v
```

They cover the angle math (deadzone, yaw wraparound, sub-pixel carry, idle reset) and an end-to-end run over a real UDP socket with a fake mouse.

## License

[MIT](LICENSE) © 2025 Krodity
