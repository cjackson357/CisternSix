import socket
import RPi.GPIO as GPIO
import subprocess
import time
from motor_control import write_to_motors

PORT = 5005

# -------------------------------
# 🔹 START CAMERA SUBPROCESSES
# -------------------------------
print("Starting camera streams in the background...")

# Define the 4 ustreamer commands
camera_commands = [
    ["./ustreamer/ustreamer", "--device", "/dev/video0", "--resolution", "320x240", "--format", "YUYV", "--host", "0.0.0.0", "--port", "8080"],
    ["./ustreamer/ustreamer", "--device", "/dev/video2", "--resolution", "320x240", "--format", "YUYV", "--host", "0.0.0.0", "--port", "8081"],
    ["./ustreamer/ustreamer", "--device", "/dev/video4", "--resolution", "320x240", "--format", "YUYV", "--host", "0.0.0.0", "--port", "8082"],
    ["./ustreamer/ustreamer", "--device", "/dev/video6", "--resolution", "320x240", "--format", "YUYV", "--host", "0.0.0.0", "--port", "8083"]
]

camera_procs = []

# Launch each camera and hide the massive wall of text it usually prints
for cmd in camera_commands:
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        camera_procs.append(proc)
    except Exception as e:
        print(f"Failed to start camera on port {cmd[-1]}: {e}")

# Give the cameras a brief second to warm up
time.sleep(1) 

# -------------------------------
# 🔹 GPIO SETUP
# -------------------------------
GPIO.setmode(GPIO.BCM)

# -------------------------------
# 🔹 SOCKET SERVER SETUP
# -------------------------------
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Prevents "Port in use" errors if you restart quickly
server.bind(("0.0.0.0", PORT))
server.listen(1)

print("Waiting for connection from Mac...")

conn, addr = server.accept()
print("Connected from:", addr)

buffer = ""

speed = 12

try:
    while True:
        data = conn.recv(1024)

        if not data:
            break

        buffer += data.decode()

        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)

            try:
                w, a, s, d, q, e, r, f = [int(x) for x in line.strip().split(",")]

                write_to_motors(w, a, s, d, q, e, r, f, speed)

            except:
                pass

finally:
    print("\nShutting down ROV systems...")
    
    # Close the socket
    conn.close()
    server.close()
    
    # Kill the camera streams (crucial!)
    for proc in camera_procs:
        proc.terminate()
        
    print("Cleanup complete.")
