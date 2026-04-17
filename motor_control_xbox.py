import numpy as np
import serial
import time

ser = serial.Serial(
    port='/dev/serial0',
    baudrate=115200,
    timeout=0  # non-blocking
)

def send_all_motors(values):
    ser.reset_input_buffer()
    parts = [f"M{i+1}:{int(v)}" for i, v in enumerate(values)]
    cmd = ",".join(parts) + "\n"
    ser.write(cmd.encode('utf-8'))

    # Non-blocking read — don't wait for echo, just grab it if it's there
    if ser.in_waiting:
        echo = ser.readline().decode('utf-8', errors='ignore').strip()
        if echo:
            print(f"Arduino confirms: {echo}", flush=True)

def write_to_motors(w, a, s, d, q, e, r, f, speed):
    thrusters = 128 * np.ones(6)
    if w:
        thrusters[0:2] += speed
        thrusters[2:4] -= 1.3 * speed
    if a:
        thrusters[0] += speed
        thrusters[2] += speed
        thrusters[1] -= 1.3 * speed
        thrusters[3] -= 1.3 * speed
    if s:
        thrusters[0:2] -= 1.3 * speed
        thrusters[2:4] += speed
    if d:
        thrusters[0] -= 1.3 * speed
        thrusters[2] -= 1.3 * speed
        thrusters[1] += speed
        thrusters[3] += speed
    if q:
        thrusters[4] += speed
    if e:
        thrusters[4] -= 1.3 * speed
    if r:
        thrusters[5] += speed
    if f:
        thrusters[5] -= 1.3 * speed

    thrusters = np.clip(thrusters, 0, 255)
    send_all_motors(thrusters)