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

current_thrusters = 128 * np.ones(6)  # global state

def write_to_motors(w, a, s, d, turn_left, turn_right,q, e, r, f, speed):
    global current_thrusters

    thrusters = 128 * np.ones(6)
    if w:
        thrusters[0:2] += speed
        thrusters[2:4] -= 1.3 * speed
    if a: # Strafe Left (Motors on each side the same)
        thrusters[0] -= 1.3 * speed
        thrusters[2] -= 1.3 * speed
        thrusters[1] += speed
        thrusters[3] += speed
    if s:
        thrusters[0:2] -= 1.3 * speed
        thrusters[2:4] += speed
    if d: # Strafe Right (Motors on each side the same)
        thrusters[0] += speed
        thrusters[2] += speed
        thrusters[1] -= 1.3 * speed
        thrusters[3] -= 1.3 * speed
    if turn_left: # Turn Left (Motors on each side opposite)
        thrusters[0] -= 1.3 * speed
        thrusters[2] += speed
        thrusters[1] += speed
        thrusters[3] -= 1.3 * speed
    if turn_right: # Turn Right (Motors on each side opposite)
        thrusters[0] += speed
        thrusters[2] -= 1.3 * speed
        thrusters[1] -= 1.3 * speed
        thrusters[3] += speed
    if q:
        thrusters[4] += speed
    if e:
        thrusters[4] -= 1.3 * speed
    if r:
        thrusters[5] += speed
    if f:
        thrusters[5] -= 1.3 * speed

    index = [4, 2, 0, 3, 1, 5]
    thrusters = thrusters[index]

    thrusters = np.clip(thrusters, 0, 255)

    # Ramp toward target instead of jumping instantly
    step = 1  # max change per update — tune this
    current_thrusters = np.clip(
        thrusters,
        current_thrusters - step,
        current_thrusters + step
    )
    send_all_motors(thrusters)

    