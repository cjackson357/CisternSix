import socket
import keyboard
import time
import cv2
import numpy as np
import threading

PI_IP = "192.168.1.3"
PORT = 5005

# -------------------------------
# 🔹 SOCKET CONTROL THREAD
# -------------------------------
def control_thread():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((PI_IP, PORT))
    print("Connected to Pi (control)")

    try:
        while True:
            w = int(keyboard.is_pressed("w"))
            a = int(keyboard.is_pressed("a"))
            s = int(keyboard.is_pressed("s"))
            d = int(keyboard.is_pressed("d"))

            message = f"{w},{a},{s},{d}\n"
            sock.sendall(message.encode())

            time.sleep(0.01)

    except:
        sock.close()


# -------------------------------
# 🔹 CAMERA THREAD CLASS
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
# 🔹 START EVERYTHING
# -------------------------------

# Camera URLs
urls = [
    f"http://{PI_IP}:8080/?action=stream",
    f"http://{PI_IP}:8081/?action=stream",
    f"http://{PI_IP}:8082/?action=stream",
    f"http://{PI_IP}:8083/?action=stream"
]

# Start control thread
threading.Thread(target=control_thread, daemon=True).start()

# Start camera streams
cams = [CameraStream(url) for url in urls]

print("All camera threads started")

# -------------------------------
# 🔹 DISPLAY LOOP (MAIN THREAD)
# -------------------------------
try:
    while True:

        frames = [cam.get_frame() for cam in cams]

        # Combine into 2x2 grid
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