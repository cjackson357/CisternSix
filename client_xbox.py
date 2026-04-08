import socket
import time
import threading
import cv2
import numpy as np
from inputs import get_gamepad

PI_IP = "192.168.1.2"
PORT = 5005

# Deadzone to avoid drift
DEADZONE = 0.1

def apply_deadzone(val):
    return val if abs(val) > DEADZONE else 0

# Controller state variables
lx = 0
ly = 0
lt = 0
rt = 0
dpad_up = 0
dpad_down = 0

def input_thread():
    global lx, ly, lt, rt, dpad_up, dpad_down

    while True:
        events = get_gamepad()

        for event in events:
            # Left stick
            if event.code == 'ABS_X':
                lx = apply_deadzone(event.state / 32768)

            elif event.code == 'ABS_Y':
                ly = apply_deadzone(-event.state / 32768)

            # Triggers
            elif event.code == 'ABS_Z':  # LT
                lt = event.state / 255

            elif event.code == 'ABS_RZ':  # RT
                rt = event.state / 255

            # D-pad
            elif event.code == 'ABS_HAT0Y':
                dpad_up = 1 if event.state == -1 else 0
                dpad_down = 1 if event.state == 1 else 0

def control_thread():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((PI_IP, PORT))
        print("Connected to Pi (control)")

        while True:
            # Convert to same format as before (w,a,s,d,q,e,r,f)
            w = 1 if ly > 0.2 else 0
            s = 1 if ly < -0.2 else 0
            a = 1 if lx < -0.2 else 0
            d = 1 if lx > 0.2 else 0

            q = 1 if rt > 0.2 else 0  # up
            e = 1 if lt > 0.2 else 0  # down

            r = dpad_up
            f = dpad_down

            print(
                f"LX:{lx:.2f} LY:{ly:.2f} "
                f"LT:{lt:.2f} RT:{rt:.2f} "
                f"DPAD_UP:{dpad_up} DPAD_DOWN:{dpad_down}"
            )

            message = f"{w},{a},{s},{d},{q},{e},{r},{f}\n"
            sock.sendall(message.encode())

            time.sleep(0.02)

    except Exception as e:
        print(f"Connection error: {e}")
        sock.close()

# -------------------------------
# 📷 CAMERA STREAM CLASS (UNCHANGED)
# -------------------------------
class CameraStream:
    def __init__(self, url):
        self.cap = cv2.VideoCapture(url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.frame = np.zeros((240, 320, 3), dtype=np.uint8)
        self.running = True

        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()

    def update(self):
        while self.running:
            if self.cap.isOpened():
                self.cap.grab()
                ret, frame = self.cap.read()
                if ret:
                    self.frame = cv2.resize(frame, (320, 240))

    def get_frame(self):
        return self.frame

    def stop(self):
        self.running = False
        self.cap.release()

# -------------------------------
# 📷 CAMERA URLS (UNCHANGED)
# -------------------------------
urls = [
    f"http://{PI_IP}:8080/?action=stream",
    f"http://{PI_IP}:8081/?action=stream",
    f"http://{PI_IP}:8082/?action=stream",
    f"http://{PI_IP}:8083/?action=stream"
]

# -------------------------------
# 🚀 START CONTROL THREAD
# -------------------------------

threading.Thread(target=input_thread, daemon=True).start()
threading.Thread(target=control_thread, daemon=True).start()

# -------------------------------
# 📷 CAMERA DISPLAY (COMMENTED VERSION)
# -------------------------------
"""
cams = [CameraStream(url) for url in urls]

print("All camera threads started")

try:
    while True:
        frames = [cam.get_frame() for cam in cams]
        top = cv2.hconcat([frames[0], frames[1]])
        bottom = cv2.hconcat([frames[2], frames[3]])
        grid = cv2.vconcat([top, bottom])
        cv2.imshow("ROV Camera System", grid)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
except KeyboardInterrupt:
    pass
finally:
    for cam in cams:
        cam.stop()
    cv2.destroyAllWindows()
"""

while True:
    time.sleep(1)