import socket
import RPi.GPIO as GPIO
import subprocess
import time

PORT = 5005

PIN_W = 17
PIN_A = 27
PIN_S = 22
PIN_D = 23

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

GPIO.setup(PIN_W, GPIO.OUT)
GPIO.setup(PIN_A, GPIO.OUT)
GPIO.setup(PIN_S, GPIO.OUT)
GPIO.setup(PIN_D, GPIO.OUT)

GPIO.output(PIN_W, GPIO.LOW)
GPIO.output(PIN_A, GPIO.LOW)
GPIO.output(PIN_S, GPIO.LOW)
GPIO.output(PIN_D, GPIO.LOW)

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

try:
    while True:
        data = conn.recv(1024)

        if not data:
            break

        buffer += data.decode()

        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)

            try:
                w, a, s, d = line.strip().split(",")

                GPIO.output(PIN_W, int(w))
                GPIO.output(PIN_A, int(a))
                GPIO.output(PIN_S, int(s))
                GPIO.output(PIN_D, int(d))

            except:
                pass

finally:
    print("\nShutting down ROV systems...")
    
    # 1. Stop the thrusters
    GPIO.output(PIN_W, GPIO.LOW)
    GPIO.output(PIN_A, GPIO.LOW)
    GPIO.output(PIN_S, GPIO.LOW)
    GPIO.output(PIN_D, GPIO.LOW)
    GPIO.cleanup()
    
    # 2. Close the socket
    conn.close()
    server.close()
    
    # 3. Kill the camera streams (crucial!)
    for proc in camera_procs:
        proc.terminate()
        
    print("Cleanup complete.")