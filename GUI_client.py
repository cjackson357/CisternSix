import socket
import tkinter as tk
from PIL import Image, ImageTk
import cv2
import numpy as np
import threading
import time
from inputs import get_gamepad
import urllib.request

PI_IP = "192.168.1.3"
PORT = 5005

DEADZONE = 0.2

def apply_deadzone(val):
    return val if abs(val) > DEADZONE else 0

# Controller state
lx = 0
ly = 0
rx = 0
lt = 0
rt = 0
dpad_up = 0
dpad_down = 0

# -------------------------------
# 🎮 INPUT THREAD
# -------------------------------
def input_thread():
    global lx, ly, rx, lt, rt, dpad_up, dpad_down
    while True:
        events = get_gamepad()
        for event in events:
            if event.code == 'ABS_X':
                lx = apply_deadzone(event.state / 32768)
            elif event.code == 'ABS_Y':
                ly = apply_deadzone(-event.state / 32768)
            elif event.code == 'ABS_RX':
                rx = apply_deadzone(event.state / 32768)
            elif event.code == 'ABS_Z':
                lt = event.state / 255
            elif event.code == 'ABS_RZ':
                rt = event.state / 255
            elif event.code == 'ABS_HAT0Y':
                dpad_up = 1 if event.state == -1 else 0
                dpad_down = 1 if event.state == 1 else 0

# -------------------------------
# 🌐 NETWORK THREAD
# -------------------------------
def network_thread():
    global lx, ly, rx, lt, rt, dpad_up, dpad_down

    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((PI_IP, PORT))
            print("Connected to Pi (control)")

            sock.setblocking(False)
            buffer = ""

            while True:
                msg = f"{lx},{ly},{rx},{lt},{rt},{dpad_up},{dpad_down}\n"
                sock.sendall(msg.encode())

                try:
                    data = sock.recv(1024)
                    if data:
                        buffer += data.decode()
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            if line.startswith("IMU:"):
                                print(f"Sensor Data -> {line}")
                except BlockingIOError:
                    pass
                except Exception as e:
                    print(f"Connection error: {e}")
                    break

                time.sleep(0.02)

        except:
            time.sleep(1)

# -------------------------------
# 📷 CAMERA STREAM
# -------------------------------
class CameraStream:
    def __init__(self, url):
        self.url = url
        self.cap = None
        self.frame = np.zeros((240, 320, 3), dtype=np.uint8)
        self.running = False

        # Test connection BEFORE opening
        if self.check_stream():
            self.cap = cv2.VideoCapture(url)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.running = True
            self.thread = threading.Thread(target=self.update, daemon=True)
            self.thread.start()
            print(f"Camera connected: {url}")
        else:
            print(f"Camera unavailable: {url}")

    def check_stream(self):
        try:
            snapshot_url = self.url.replace("?action=stream", "?action=snapshot")
            urllib.request.urlopen(snapshot_url, timeout=3)
            return True
        except:
            return False

    def update(self):
        while self.running:
            if self.cap and self.cap.isOpened():
                self.cap.grab()
                ret, frame = self.cap.read()
                if ret:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.frame = cv2.resize(frame, (320, 240))

    def get_frame(self):
        return self.frame

    def stop(self):
        self.running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()

# -------------------------------
# 🧠 MAIN DASHBOARD
# -------------------------------
class ROVDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("ROV Command Station")
        self.root.configure(bg="#1e1e1e")

        self.running = True

        self.setup_ui()

        # Camera URLs
        urls = [
            f"http://{PI_IP}:8080/?action=stream",
            f"http://{PI_IP}:8081/?action=stream",
            f"http://{PI_IP}:8082/?action=stream",
            f"http://{PI_IP}:8083/?action=stream"
        ]

        # Only keep working cameras
        self.cams = []
        for url in urls:
            cam = CameraStream(url)
            if cam.running:
                self.cams.append(cam)

        threading.Thread(target=input_thread, daemon=True).start()
        threading.Thread(target=network_thread, daemon=True).start()

        self.update_video()
        self.update_ui_loop()

    def setup_ui(self):
        self.video_label = tk.Label(self.root, bg="black")
        self.video_label.grid(row=0, column=0, padx=10, pady=10)

        self.panel = tk.Frame(self.root, bg="#1e1e1e")
        self.panel.grid(row=0, column=1, padx=10, pady=10, sticky="n")

        self.canvas = tk.Canvas(self.panel, width=400, height=600, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack()

        self.controller_img = Image.open("controller.png")
        self.controller_img = self.controller_img.resize((400, 300))
        self.controller_tk = ImageTk.PhotoImage(self.controller_img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.controller_tk)

        self.lt_rect = self.canvas.create_rectangle(50, 310, 150, 340, outline="white")
        self.rt_rect = self.canvas.create_rectangle(250, 310, 350, 340, outline="white")

        self.canvas.create_text(100, 355, text="LT", fill="white", font=("Arial", 12, "bold"))
        self.canvas.create_text(300, 355, text="RT", fill="white", font=("Arial", 12, "bold"))

        self.joy_center = (200, 420)
        self.joy_radius = 40

        self.canvas.create_oval(
            self.joy_center[0] - self.joy_radius,
            self.joy_center[1] - self.joy_radius,
            self.joy_center[0] + self.joy_radius,
            self.joy_center[1] + self.joy_radius,
            outline="white"
        )

        self.joy_dot = self.canvas.create_oval(0, 0, 0, 0, fill="white")

        self.dpad_up_rect = self.canvas.create_rectangle(190, 500, 210, 520, fill="white")
        self.dpad_down_rect = self.canvas.create_rectangle(190, 540, 210, 560, fill="white")
        self.canvas.create_rectangle(170, 520, 230, 540, fill="white")

    def update_video(self):
        if not self.running:
            return

        if len(self.cams) == 0:
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            img = Image.fromarray(blank)
        else:
            frames = [cam.get_frame() for cam in self.cams]

            # Pad to 4 cameras if fewer exist
            while len(frames) < 4:
                frames.append(np.zeros((240, 320, 3), dtype=np.uint8))

            top = cv2.hconcat([frames[0], frames[1]])
            bottom = cv2.hconcat([frames[2], frames[3]])
            grid = cv2.vconcat([top, bottom])

            img = Image.fromarray(grid)

        imgtk = ImageTk.PhotoImage(image=img)
        self.video_label.imgtk = imgtk
        self.video_label.configure(image=imgtk)

        self.root.after(30, self.update_video)

    def update_ui_loop(self):
        global lx, ly, rx, lt, rt, dpad_up, dpad_down

        self.canvas.itemconfig(self.lt_rect, fill="lime" if lt > 0.2 else "")
        self.canvas.itemconfig(self.rt_rect, fill="lime" if rt > 0.2 else "")

        cx, cy = self.joy_center
        r = self.joy_radius

        x = cx + lx * r
        y = cy + ly * r

        color = "lime" if abs(lx) > 0.1 or abs(ly) > 0.1 else "white"

        self.canvas.coords(self.joy_dot, x-8, y-8, x+8, y+8)
        self.canvas.itemconfig(self.joy_dot, fill=color)

        self.canvas.itemconfig(self.dpad_up_rect, fill="lime" if dpad_up else "white")
        self.canvas.itemconfig(self.dpad_down_rect, fill="lime" if dpad_down else "white")

        self.root.after(50, self.update_ui_loop)

    def on_closing(self):
        self.running = False
        for cam in self.cams:
            cam.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ROVDashboard(root)
    print("Client running. Press Ctrl+C to quit.")
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()