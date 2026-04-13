import socket
import tkinter as tk
from PIL import Image, ImageTk
import cv2
import numpy as np
import threading
import time
from inputs import get_gamepad

PI_IP = "192.168.1.3"
PORT = 5005

# -------------------------------
# 🎮 CONTROLLER SETTINGS
# -------------------------------
DEADZONE = 0.1

def apply_deadzone(val):
    return val if abs(val) > DEADZONE else 0

# Controller state
lx = 0
ly = 0
lt = 0
rt = 0
dpad_up = 0
dpad_down = 0

# -------------------------------
# 🎮 INPUT THREAD
# -------------------------------
def input_thread():
    global lx, ly, lt, rt, dpad_up, dpad_down

    while True:
        events = get_gamepad()
        for event in events:
            if event.code == 'ABS_X':
                lx = apply_deadzone(event.state / 32768)
            elif event.code == 'ABS_Y':
                ly = apply_deadzone(-event.state / 32768)
            elif event.code == 'ABS_Z':
                lt = event.state / 255
            elif event.code == 'ABS_RZ':
                rt = event.state / 255
            elif event.code == 'ABS_HAT0Y':
                dpad_up = 1 if event.state == -1 else 0
                dpad_down = 1 if event.state == 1 else 0

# -------------------------------
# 📷 CAMERA STREAM
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
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.frame = cv2.resize(frame, (320, 240))

    def get_frame(self):
        return self.frame

    def stop(self):
        self.running = False
        if self.cap.isOpened():
            self.cap.release()

# -------------------------------
# 🧠 MAIN DASHBOARD
# -------------------------------
class ROVDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("ROV Command Station")
        self.root.configure(bg="#1e1e1e")

        self.connected = False
        self.running = True

        self.setup_ui()

        # Camera URLs
        urls = [
            f"http://{PI_IP}:8080/?action=stream",
            f"http://{PI_IP}:8081/?action=stream",
            f"http://{PI_IP}:8082/?action=stream",
            f"http://{PI_IP}:8083/?action=stream"
        ]

        self.cams = [CameraStream(url) for url in urls]

        # Start threads
        threading.Thread(target=self.network_loop, daemon=True).start()
        threading.Thread(target=input_thread, daemon=True).start()

        self.update_video()
        self.update_ui_loop()

    def setup_ui(self):
        self.video_label = tk.Label(self.root, bg="black")
        self.video_label.grid(row=0, column=0, padx=10, pady=10)

        self.panel = tk.Frame(self.root, bg="#1e1e1e")
        self.panel.grid(row=0, column=1, sticky="n", padx=10, pady=20)

        tk.Label(self.panel, text="STATUS", fg="white", bg="#1e1e1e", font=("Arial", 16, "bold")).pack()
        self.status_label = tk.Label(self.panel, text="DISCONNECTED", fg="red", bg="#1e1e1e")
        self.status_label.pack(pady=10)

        self.control_label = tk.Label(self.panel, text="Controller Active", fg="white", bg="#1e1e1e")
        self.control_label.pack(pady=10)

        self.estop_btn = tk.Button(self.panel, text="EMERGENCY STOP", bg="red", command=self.estop)
        self.estop_btn.pack(pady=40)

    def estop(self):
        global lx, ly, lt, rt
        lx = ly = lt = rt = 0
        print("EMERGENCY STOP")

    def network_loop(self):
        global lx, ly, lt, rt, dpad_up, dpad_down

        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((PI_IP, PORT))

                self.connected = True
                self.status_label.config(text="CONNECTED", fg="lime")

                while self.running:
                    w = 1 if ly < -0.2 else 0
                    s = 1 if ly > 0.2 else 0
                    a = 1 if lx < -0.2 else 0
                    d = 1 if lx > 0.2 else 0

                    q = 1 if rt > 0.2 else 0
                    e = 1 if lt > 0.2 else 0

                    r = dpad_up
                    f = dpad_down

                    msg = f"{w},{a},{s},{d},{q},{e},{r},{f}\n"
                    sock.sendall(msg.encode())

                    time.sleep(0.02)

            except Exception:
                self.connected = False
                self.status_label.config(text="DISCONNECTED", fg="red")
                time.sleep(1)

    def update_video(self):
        if not self.running:
            return

        frames = [cam.get_frame() for cam in self.cams]

        top = cv2.hconcat([frames[0], frames[1]])
        bottom = cv2.hconcat([frames[2], frames[3]])
        grid = cv2.vconcat([top, bottom])

        img = Image.fromarray(grid)
        imgtk = ImageTk.PhotoImage(image=img)

        self.video_label.imgtk = imgtk
        self.video_label.configure(image=imgtk)

        self.root.after(30, self.update_video)

    def update_ui_loop(self):
        global lx, ly, lt, rt

        text = f"LX:{lx:.2f} LY:{ly:.2f}\nLT:{lt:.2f} RT:{rt:.2f}"
        self.control_label.config(text=text)

        self.root.after(100, self.update_ui_loop)

    def on_closing(self):
        self.running = False
        for cam in self.cams:
            cam.stop()
        self.root.destroy()

# -------------------------------
# 🚀 START APP
# -------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = ROVDashboard(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
