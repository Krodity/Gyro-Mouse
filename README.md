# GyroMouse

GyroMouse is a Python script that allows you to control your mouse cursor using gyroscope data sent over UDP. It is designed for use with devices or applications that stream orientation data (yaw, pitch, roll) to your computer.

## Features
- Receives gyroscope data via UDP
- Maps yaw and pitch changes to mouse movement
- Adjustable deadzone and sensitivity
- Threaded for smooth, real-time control

## Requirements
- Python 3.7 or higher
- Windows OS (uses Windows API for mouse control)

## Installation
1. Clone or download this repository.
2. Install Python 3 if you haven't already: [Download Python](https://www.python.org/downloads/)
3. (Optional) Create a virtual environment:
   ```sh
   python -m venv venv
   venv\Scripts\activate
   ```
4. No external packages are required; only the Python standard library is used.

## Usage
1. Place `GyroMouse.py` in your desired directory.
2. Open a terminal or command prompt in that directory.
3. Run the script:
   ```sh
   python GyroMouse.py
   ```
4. The script will start listening for UDP packets on the default IP and port (`127.0.0.1:4242`).
5. Send UDP packets containing six double-precision floats (e.g., from your device or another script) to this address.
6. Move your device to control the mouse cursor.
7. Press `Ctrl+C` in the terminal to stop the script.

## Adjusting IP and Port
By default, the script listens on `127.0.0.1` (localhost) and port `4242`. To change these settings:

1. Open `GyroMouse.py` in a text editor.
2. Locate the following lines near the top of the script:
   ```python
   UDP_IP = "127.0.0.1"
   UDP_PORT = 4242
   ```
3. Change `UDP_IP` to the desired IP address (e.g., your local network IP or `0.0.0.0` for all interfaces).
4. Change `UDP_PORT` to your preferred port number.
5. Save the file and restart the script.

**Example:**
```python
UDP_IP = "0.0.0.0"  # Listen on all network interfaces
UDP_PORT = 5555      # Use port 5555
```

## Customization
- **Deadzone:** Adjust the `DEADZONE` variable to change the minimum movement threshold.
- **Sensitivity:** Change `YAW_SCALE_FACTOR` and `PITCH_SCALE_FACTOR` to increase or decrease mouse movement speed.
- **Minimum Movement:** Set `MIN_MOVEMENT` to control the smallest pixel movement applied.

## Data Format
The script expects UDP packets containing six double-precision floats (8 bytes each, 48 bytes total), packed using Python's `struct.pack('dddddd', ...)` format. The relevant values are:
- Index 3: Yaw
- Index 4: Pitch
- Index 5: Roll

## Troubleshooting
- Make sure your firewall allows UDP traffic on the chosen port.
- Ensure your device is sending data to the correct IP and port.
- The script must be run as a regular user (no admin required), but must have permission to control the mouse.

## License
MIT License 

## Adjusting Deadzone and Sensitivity

You can fine-tune the mouse movement behavior by changing the following variables at the top of `GyroMouse.py`:

- **Deadzone**
  - Variable: `DEADZONE`
  - Description: Sets the minimum change in yaw or pitch required to register movement. Increases in this value will make the mouse less sensitive to small, unintended device movements (reducing drift), but may also require larger movements to move the cursor.
  - Example:
    ```python
    DEADZONE = 0.2  # Increase for less sensitivity to small movements
    ```

- **Yaw Sensitivity**
  - Variable: `YAW_SCALE_FACTOR`
  - Description: Controls how much horizontal mouse movement is generated per unit of yaw change. Higher values make the mouse move faster left/right.
  - Example:
    ```python
    YAW_SCALE_FACTOR = 40  # Increase for faster horizontal movement
    ```

- **Pitch Sensitivity**
  - Variable: `PITCH_SCALE_FACTOR`
  - Description: Controls how much vertical mouse movement is generated per unit of pitch change. Higher values make the mouse move faster up/down.
  - Example:
    ```python
    PITCH_SCALE_FACTOR = 40  # Increase for faster vertical movement
    ```

- **Minimum Movement**
  - Variable: `MIN_MOVEMENT`
  - Description: The minimum number of pixels the mouse must move before an update is sent. Increasing this can help filter out jitter, but may make small movements less responsive.
  - Example:
    ```python
    MIN_MOVEMENT = 1  # Increase to filter out small jitters
    ```

After making changes, save the file and restart the script for the new settings to take effect. 
