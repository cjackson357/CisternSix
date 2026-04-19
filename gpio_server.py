import os
import serial
import socket
import RPi.GPIO as GPIO
import subprocess
import time
import sys
import qwiic_icm20948
from motor_control_xbox import write_to_motors

PORT = 5005

# -------------------------------
# 🔹 GPIO & LED SETUP
# -------------------------------
D1, D2, D3 = 24, 23, 25
GPIO.setmode(GPIO.BCM)
GPIO.setup([D1, D2, D3], GPIO.OUT)

def update_leds(uart_status, imu_status, cam_status):
    blink_tick = int(time.time() * 5) % 2 == 0
    GPIO.output(D1, GPIO.HIGH if uart_status else (GPIO.HIGH if blink_tick else GPIO.LOW))
    GPIO.output(D2, GPIO.HIGH if imu_status else (GPIO.HIGH if blink_tick else GPIO.LOW))
    GPIO.output(D3, GPIO.HIGH if cam_status else (GPIO.HIGH if blink_tick else GPIO.LOW))


# -------------------------------
# 🔹 START CAMERA SUBPROCESSES
# -------------------------------
print("Starting camera streams in the background...")

camera_commands = [
    ["./ustreamer/ustreamer", "--device", "/dev/video0", "--resolution", "320x240", "--format", "YUYV", "--host", "0.0.0.0", "--port", "8080"],
    ["./ustreamer/ustreamer", "--device", "/dev/video2", "--resolution", "320x240", "--format", "YUYV", "--host", "0.0.0.0", "--port", "8081"],
    ["./ustreamer/ustreamer", "--device", "/dev/video4", "--resolution", "320x240", "--format", "YUYV", "--host", "0.0.0.0", "--port", "8082"],
]

camera_procs = []
for cmd in camera_commands:
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        camera_procs.append(proc)
    except Exception as e:
        print(f"Failed to start camera on port {cmd[-1]}: {e}")

cams_ok = True
for cmd in camera_commands:
    device_path = cmd[3]
    if not os.path.exists(device_path):
        cams_ok = False
        print(f"Hardware missing: {device_path} is not plugged in.")

time.sleep(1)


# -------------------------------
# 🔹 IMU SETUP
# -------------------------------
print("Initializing SparkFun ICM-20948 IMU...")
imu_ok = False
try:
    imu = qwiic_icm20948.QwiicIcm20948(address=0x68)
    if imu.connected:
        imu.begin()
        imu_ok = True
        print("IMU successfully connected!")
    else:
        imu = None
        print("IMU object created, but reports as disconnected.")
except Exception as e:
    imu = None
    print(f"IMU Initialization Error: {e}")


# -------------------------------
# 🔹 ARDUINO UART SETUP
# -------------------------------
print("Checking UART connection to Arduino...")
arduino_ok = False
try:
    from motor_control_xbox import ser
    print("Pinging Arduino...")
    while True:
        ser.write(b"PING\n")
        time.sleep(0.5)
        if ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line == "PONG":
                arduino_ok = True
                print("Arduino handshake successful!")
                break
            else:
                print(f"Unexpected response: '{line}', retrying...")
        else:
            print("No response, retrying...")
except Exception as e:
    print(f"UART Initialization Error: {e}")


# -------------------------------
# 🔹 SOCKET SERVER SETUP
# -------------------------------
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", PORT))
server.listen(1)

print("Waiting for connection from Laptop...")
while True:
    server.settimeout(0.1)
    update_leds(arduino_ok, imu_ok, cams_ok)
    try:
        conn, addr = server.accept()
        print("Connected from:", addr)
        conn.setblocking(False)
        break
    except socket.timeout:
        continue

buffer = ""
last_imu_time = time.time()
imu_send_rate = 0.1


# -------------------------------
# 🧠 STATUS HELPER FUNCTION
# -------------------------------
def get_status_string(lx, ly, rx, lt, rt, dpad_up, dpad_down):
    directions = []
    threshold = 0.2

    if ly > threshold:
        directions.append(f"FORWARD ({ly:.2f})")
    elif ly < -threshold:
        directions.append(f"BACKWARD ({-ly:.2f})")

    if lx < -threshold:
        directions.append(f"STRAFE LEFT ({-lx:.2f})")
    elif lx > threshold:
        directions.append(f"STRAFE RIGHT ({lx:.2f})")

    if rx < -threshold:
        directions.append(f"TURN LEFT ({-rx:.2f})")
    elif rx > threshold:
        directions.append(f"TURN RIGHT ({rx:.2f})")

    vertical = rt - lt
    if vertical > threshold:
        directions.append(f"UP ({vertical:.2f})")
    elif vertical < -threshold:
        directions.append(f"DOWN ({-vertical:.2f})")

    if dpad_up > 0.5:
        directions.append("M6 UP")
    elif dpad_down > 0.5:
        directions.append("M6 DOWN")

    if not directions:
        return "IDLE"

    return " | ".join(directions)


try:
    while True:
        time.sleep(0.005)
        update_leds(arduino_ok, imu_ok, cams_ok)

        try:
            data = conn.recv(1024)

            if not data:
                print("no data")
                break

            buffer += data.decode()

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                try:
                    lx, ly, rx, lt, rt, r, f = [float(x) for x in line.strip().split(",")]
                    write_to_motors(
                        w=ly > 0.2,
                        a=lx < -0.2,
                        s=ly < -0.2,
                        d=lx > 0.2,
                        turn_left=rx < -0.2,
                        turn_right=rx > 0.2,
                        q=lt > 0.2,
                        e=rt > 0.2,
                        r=r > 0.5,
                        f=f > 0.5,
                        speed=25
                    )
                    status = get_status_string(lx, ly, rx, lt, rt, r, f)
                    print(f"\rROV STATUS: {status}        ", end="", flush=True)

                except Exception as e:
                    print(f"An error occurred: {e}")

        except BlockingIOError:
            pass
        except ConnectionResetError:
            break

        if imu and (time.time() - last_imu_time) >= imu_send_rate:
            try:
                if imu.dataReady():
                    imu.getAgmt()
                    telemetry = f"IMU:{imu.axRaw},{imu.ayRaw},{imu.azRaw},{imu.gxRaw},{imu.gyRaw},{imu.gzRaw}\n"
                    conn.sendall(telemetry.encode())
                    last_imu_time = time.time()
            except Exception as e:
                print(f"IMU Read Error: {e}")

finally:
    print("\nShutting down ROV systems...")
    GPIO.cleanup()
    try:
        write_to_motors(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, speed)
    except:
        pass
    conn.close()
    server.close()
    for proc in camera_procs:
        proc.terminate()
    print("Cleanup complete.")