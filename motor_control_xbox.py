import numpy as np
import serial
import time

ser = serial.Serial(
    port='/dev/serial0',
    baudrate=115200,
    timeout=0
)

def do_handshake():
    while True:
        ser.write(b"PING\n")
        time.sleep(0.5)
        if ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line == "PONG":
                print("Handshake restored!")
                return
        print("Waiting for Arduino...")

def send_all_motors(values):
    ser.reset_input_buffer()
    parts = [f"M{i+1}:{int(v)}" for i, v in enumerate(values)]
    cmd = ",".join(parts) + "\n"
    ser.write(cmd.encode('utf-8'))

    if ser.in_waiting:
        echo = ser.readline().decode('utf-8', errors='ignore').strip()
        if echo == "READY":
            print("Arduino reset detected — redoing handshake...")
            do_handshake()
        elif echo.startswith("DRIVING:"):
            pass  # valid echo, no need to print
        elif echo == "BUFFER_OVERFLOW":
            print("Arduino buffer overflow — flushing...")
            ser.reset_output_buffer()
            time.sleep(0.1)

current_thrusters = 128 * np.ones(6)

def write_to_motors(w, a, s, d, turn_left, turn_right, q, e, r, f, speed):
    global current_thrusters

    thrusters = 128 * np.ones(6)
    if w:
        thrusters[0:2] += speed
        thrusters[2:4] -= 1.3 * speed
    if a:
        thrusters[0] -= 1.3 * speed
        thrusters[2] -= 1.3 * speed
        thrusters[1] += speed
        thrusters[3] += speed
    if s:
        thrusters[0:2] -= 1.3 * speed
        thrusters[2:4] += speed
    if d:
        thrusters[0] += speed
        thrusters[2] += speed
        thrusters[1] -= 1.3 * speed
        thrusters[3] -= 1.3 * speed
    if turn_left:
        thrusters[0] -= 1.3 * speed
        thrusters[2] += speed
        thrusters[1] += speed
        thrusters[3] -= 1.3 * speed
    if turn_right:
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
        thrusters[5] -= speed

    index = [4, 2, 0, 3, 1, 5]
    thrusters = thrusters[index]
    thrusters = np.clip(thrusters, 0, 255)

    crossing = (current_thrusters - 128) * (thrusters - 128) < 0

    effective_target = thrusters.copy()
    effective_target[crossing] = 128

    diff = effective_target - current_thrusters
    step = np.clip(np.abs(diff) * 0.3, 2, 15)

    current_thrusters = np.where(
        diff > 0,
        np.minimum(current_thrusters + step, effective_target),
        np.maximum(current_thrusters - step, effective_target)
    )

    send_all_motors(current_thrusters)