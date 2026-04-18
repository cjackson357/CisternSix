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

current_thrusters = 128 * np.ones(6)

def write_to_motors(w, a, s, d, turn_left, turn_right, q, e, r, f, speed):
    global current_thrusters
    
    target = 128 * np.ones(6)
    if w:
        target[0:2] += speed
        target[2:4] -= 1.3 * speed
    if a:
        target[0] -= 1.3 * speed
        target[2] -= 1.3 * speed
        target[1] += speed
        target[3] += speed
    if s:
        target[0:2] -= 1.3 * speed
        target[2:4] += speed
    if d:
        target[0] += speed
        target[2] += speed
        target[1] -= 1.3 * speed
        target[3] -= 1.3 * speed
    if turn_left:
        target[0] -= 1.3 * speed
        target[2] += speed
        target[1] += speed
        target[3] -= 1.3 * speed
    if turn_right:
        target[0] += speed
        target[2] -= 1.3 * speed
        target[1] -= 1.3 * speed
        target[3] += speed
    if q:
        target[4] += speed
    if e:
        target[4] -= 1.3 * speed
    if r:
        target[5] += speed
    if f:
        target[5] -= 1.3 * speed

    index = [4, 2, 0, 3, 1]
    target = target[index]

    target = np.clip(target, 0, 255)

    step = 5
    current_thrusters = np.clip(
        target,
        current_thrusters - step,
        current_thrusters + step
    )

    send_all_motors(current_thrusters)