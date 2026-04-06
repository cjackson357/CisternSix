import socket
from pynput import keyboard
import time
import cv2
import numpy as np
import threading

PI_IP = "192.168.1.3" 
PORT = 5005

key_state = {'w': 0, 'a': 0, 's': 0, 'd': 0, 'q': 0, 'e': 0, 'r': 0, 'f': 0}

def on_press(key):
    try:
        char = key.char.lower()
        if char in key_state:
            key_state[char] = 1
    except AttributeError:
        if key == keyboard.Key.space:
            key_state['space'] = 1
        elif key == keyboard.Key.shift:
            key_state['shift'] = 1

def on_release(key):
    try:
        char = key.char.lower()
        if char in key_state:
            key_state[char] = 0
    except AttributeError:
        if key == keyboard.Key.space:
            key_state['space'] = 0
        elif key == keyboard.Key.shift:
            key_state['shift'] = 0

listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()

def control_thread():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((PI_IP, PORT))
        print("Connected to Pi (control)")

        while True:
            w = key_state['w']
            a = key_state['a']
            s = key_state['s']
            d = key_state['d']
            q = key_state['q']
            e = key_state['e']
            r = key_state['r']
            f = key_state['f']

            message = f"{w},{a},{s},{d},{q},{e},{r},{f}\n"
            sock.sendall(message.encode())

            time.sleep(0.01)

    except Exception as e:
        print(f"Socket disconnected or failed: {e}")
        sock.close()


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


urls = [
    f"http://{PI_IP}:8080/?action=stream",
    f"http://{PI_IP}:8081/?action=stream",
    f"http://{PI_IP}:8082/?action=stream",
    f"http://{PI_IP}:8083/?action=stream"
]

threading.Thread(target=control_thread, daemon=True).start()

# cams = [CameraStream(url) for url in urls]

print("All camera threads started")

# try:
#     while True:
#         frames = [cam.get_frame() for cam in cams]
#         top = cv2.hconcat([frames[0], frames[1]])
#         bottom = cv2.hconcat([frames[2], frames[3]])
#         grid = cv2.vconcat([top, bottom])
#         cv2.imshow("ROV Camera System", grid)
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break
# except KeyboardInterrupt:
#     pass
# finally:
#     for cam in cams:
#         cam.stop()
#     cv2.destroyAllWindows()

while True:
    continue