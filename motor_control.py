import numpy as np
import serial
import time

ser = serial.Serial(
    port='/dev/serial0',
    baudrate=115200,
    timeout=1
)

def send_all_motors(values):
    parts = [f"M{i+1}:{int(v)}" for i, v in enumerate(values)]
    cmd = ",".join(parts) + "\n"
    ser.write(cmd.encode('utf-8'))
    time.sleep(0.02)

def write_to_motors(lx, ly, lt, rt, dpad_up, dpad_down):
    thrusters = 128 * np.ones(6)

    gain = 10

    # Forward/back
    thrusters[0:2] += -ly * gain
    thrusters[2:4] += ly * gain

    # Turning
    thrusters[0] += lx * gain
    thrusters[2] += lx * gain
    thrusters[1] -= lx * gain
    thrusters[3] -= lx * gain

    # Vertical
    thrusters[4] += (rt - lt) * gain

    # D-pad
    if dpad_up > 0.5:
        thrusters[5] += gain
    elif dpad_down > 0.5:
        thrusters[5] -= gain

    np.clip(thrusters, 0, 255)

    send_all_motors(thrusters)