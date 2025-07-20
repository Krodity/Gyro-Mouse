import socket
import struct
import time
import threading
import ctypes
from ctypes import wintypes

# Configure UDP socket
UDP_IP = "127.0.0.1"
UDP_PORT = 4242
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print(f"GyroMouse started! Listening on {UDP_IP}:{UDP_PORT}")
print("Waiting for UDP data...")
print("Press Ctrl+C to stop")

# Settings - controlled movement
DEADZONE = 0.2  # Small deadzone to prevent drift
YAW_SCALE_FACTOR = 40  # Reduced scale factor
PITCH_SCALE_FACTOR = 40  # Reduced scale factor
MIN_MOVEMENT = 1  # Minimum pixels to move
MOUSE_UPDATE_RATE = 0.01  # 5ms between mouse updates

# Thread-safe variables
running = True
current_movement = (0, 0)  # (x, y) movement to apply

# Previous values for delta calculation
prev_yaw = None
prev_pitch = None

# Windows API for mouse movement
user32 = ctypes.windll.user32
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("mi", MOUSEINPUT)
    ]

def move_mouse_relative(dx, dy):
    """Move mouse using Windows API SendInput"""
    try:
        extra = ctypes.c_ulong(0)
        ii_ = INPUT()
        ii_.type = INPUT_MOUSE
        ii_.mi.dx = dx
        ii_.mi.dy = dy
        ii_.mi.mouseData = 0
        ii_.mi.dwFlags = MOUSEEVENTF_MOVE
        ii_.mi.time = 0
        ii_.mi.dwExtraInfo = ctypes.pointer(extra)
        user32.SendInput(1, ctypes.pointer(ii_), ctypes.sizeof(ii_))
        return True
    except Exception as e:
        return False

def udp_receiver():
    """Thread for receiving UDP data and calculating deltas"""
    global prev_yaw, prev_pitch, running, current_movement
    
    while running:
        try:
            data, addr = sock.recvfrom(1024)
            unpacked_data = struct.unpack('dddddd', data)
            
            # Get current values
            yaw = unpacked_data[3]
            pitch = unpacked_data[4]
            roll = unpacked_data[5]

            # Calculate deltas (change from previous reading)
            if prev_yaw is not None and prev_pitch is not None:
                yaw_delta = yaw - prev_yaw
                pitch_delta = pitch - prev_pitch

                # Apply deadzone to prevent drift
                if abs(yaw_delta) < DEADZONE:
                    yaw_delta = 0
                if abs(pitch_delta) < DEADZONE:
                    pitch_delta = 0

                # Map deltas directly to mouse movements
                # Invert yaw direction: negative yaw = right, positive yaw = left
                # Invert pitch direction: positive pitch = up, negative pitch = down
                x_move = int(-yaw_delta * YAW_SCALE_FACTOR)
                y_move = int(pitch_delta * PITCH_SCALE_FACTOR)

                # Only set movement if there's significant change
                if abs(x_move) >= MIN_MOVEMENT or abs(y_move) >= MIN_MOVEMENT:
                    current_movement = (x_move, y_move)
                else:
                    current_movement = (0, 0)

            # Store current values for next iteration
            prev_yaw = yaw
            prev_pitch = pitch
            
        except Exception as e:
            print(f"UDP receiver error: {e}")
            break

def mouse_controller():
    """Thread for controlling mouse movement"""
    global running, current_movement
    
    last_mouse_update = 0
    
    while running:
        try:
            current_time = time.time()
            
            # Only update mouse at controlled rate
            if (current_time - last_mouse_update) >= MOUSE_UPDATE_RATE:
                x_move, y_move = current_movement
                
                # Move mouse if there's any movement
                if x_move != 0 or y_move != 0:
                    move_mouse_relative(x_move, y_move)
                    last_mouse_update = current_time
                
        except Exception as e:
            print(f"Mouse controller error: {e}")
            break

try:
    # Start threads
    udp_thread = threading.Thread(target=udp_receiver, daemon=True)
    mouse_thread = threading.Thread(target=mouse_controller, daemon=True)
    
    udp_thread.start()
    mouse_thread.start()
    
    print("Threads started. Press Ctrl+C to stop...")
    
    # Keep main thread alive with minimal delay
    while True:
        time.sleep(0.0001)  # 0.1ms delay - almost no delay
        
except KeyboardInterrupt:
    print("\nStopping GyroMouse...")
    running = False
    
    # Wait for threads to finish
    udp_thread.join(timeout=1)
    mouse_thread.join(timeout=1)
    
    print("GyroMouse stopped by user")
    sock.close()
    
except Exception as e:
    print(f"Error: {e}")
    running = False
    sock.close()