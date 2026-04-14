import socket
import RPi.GPIO as GPIO
import subprocess
import time
import sys
import qwiic_icm20948
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
# 🔹 IMU SETUP
# -------------------------------
print("Initializing SparkFun ICM-20948 IMU...")
try:
    imu = qwiic_icm20948.QwiicIcm20948()
    if not imu.connected:
        print("IMU not connected. Check I2C wiring.", file=sys.stderr)
        imu = None
    else:
        imu.begin()
        print("IMU initialized!")
except Exception as e:
    print(f"IMU Initialization failed: {e}")
    imu = None


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

conn.setblocking(False) # Set socket to non-blocking mode for smoother control loop

buffer = ""
speed = 25
last_imu_time = time.time()
imu_send_rate = 0.1 # send data to laptop every 0.1s (10Hz)

try:
    while True:
        try:
            data = conn.recv(1024)

            if not data:
                break #laptop disconnected

            buffer += data.decode()

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)

                try:
                    w, a, s, d, q, e, r, f = [int(x) for x in line.strip().split(",")]

                    write_to_motors(w, a, s, d, q, e, r, f, speed)

                except ValueError:
                    pass
        except BlockingIOError:
            pass # no data this millisecond, keep looping
        except ConnectionResetError:
            break
        
        if imu and (time.time() - last_imu_time) >= imu_send_rate:
            try:
                if imu.dataReady():
                    imu.getAgmt()

                    telemetry = f"IMU:{imu.axRaw},{imu.ayRaw},{imu.azRaw},{imu.gxRaw},{imu.gyRaw},{imu.gzRaw}\n"
                    
                    conn.sendall(telemetry.encode())
                    last_imu_time = time.time()
                    
                    # 🔹 NEW: Print the exact string being sent to the Mac
                    print(f"Successfully read and sent: {telemetry.strip()}")
                    
            except Exception as e:
                # 🔹 NEW: Instead of 'pass', print the error so you know exactly why it failed
                print(f"IMU Read Error: {e}")
        

finally:
    print("\nShutting down ROV systems...")

    try:
        write_to_motors(0, 0, 0, 0, 0, 0, 0, 0, speed) # Stop all motors
    except:
        pass
    
    # Close the socket
    conn.close()
    server.close()
    
    # Kill the camera streams (crucial!)
    for proc in camera_procs:
        proc.terminate()
        
    print("Cleanup complete.")
