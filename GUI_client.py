import socket
import tkinter as tk
from PIL import Image, ImageTk
import cv2
import numpy as np
import threading
import time

PI_IP = "192.168.1.3"
PORT = 5005

class CameraStream:
    """Fetches video frames in the background to prevent GUI lag"""
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
                    # Convert BGR (OpenCV) to RGB (Tkinter)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.frame = cv2.resize(frame, (320, 240))

    def get_frame(self):
        return self.frame

    def stop(self):
        self.running = False
        if self.cap.isOpened():
            self.cap.release()

class ROVDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Cistern ROV Command Station")
        self.root.configure(bg="#1e1e1e") # Dark mode looks more professional

        # ROV State
        self.key_state = {'w': 0, 'a': 0, 's': 0, 'd': 0}
        self.connected = False
        self.running = True

        # Setup GUI Layout
        self.setup_ui()

        # Bind Keyboard Events (Only works when window is in focus - safer!)
        self.root.bind("<KeyPress>", self.on_press)
        self.root.bind("<KeyRelease>", self.on_release)

        # Start Camera Streams
        urls = [
            f"http://{PI_IP}:8080/?action=stream",
            f"http://{PI_IP}:8081/?action=stream",
            f"http://{PI_IP}:8082/?action=stream",
            f"http://{PI_IP}:8083/?action=stream"
        ]
        self.cams = [CameraStream(url) for url in urls]

        # Start Background Threads
        threading.Thread(target=self.network_loop, daemon=True).start()
        
        # Start GUI Video Loop
        self.update_video()

    def setup_ui(self):
        # Left Side: Video Grid
        self.video_label = tk.Label(self.root, bg="black")
        self.video_label.grid(row=0, column=0, padx=10, pady=10)

        # Right Side: Control Panel
        self.panel = tk.Frame(self.root, bg="#1e1e1e")
        self.panel.grid(row=0, column=1, sticky="n", padx=10, pady=20)

        # Connection Status
        tk.Label(self.panel, text="TELEMETRY", fg="white", bg="#1e1e1e", font=("Arial", 16, "bold")).pack(pady=(0, 5))
        self.status_indicator = tk.Label(self.panel, text="DISCONNECTED", fg="red", bg="#1e1e1e", font=("Arial", 14))
        self.status_indicator.pack(pady=(0, 20))

        # Thruster Status
        tk.Label(self.panel, text="THRUSTER STATUS", fg="white", bg="#1e1e1e", font=("Arial", 16, "bold")).pack(pady=(0, 5))
        
        # Simple cross layout for WASD
        self.btn_w = tk.Label(self.panel, text="W", width=4, height=2, bg="gray", font=("Arial", 14, "bold"))
        self.btn_w.pack()
        
        mid_frame = tk.Frame(self.panel, bg="#1e1e1e")
        mid_frame.pack()
        self.btn_a = tk.Label(mid_frame, text="A", width=4, height=2, bg="gray", font=("Arial", 14, "bold"))
        self.btn_a.grid(row=0, column=0, padx=2)
        self.btn_s = tk.Label(mid_frame, text="S", width=4, height=2, bg="gray", font=("Arial", 14, "bold"))
        self.btn_s.grid(row=0, column=1, padx=2)
        self.btn_d = tk.Label(mid_frame, text="D", width=4, height=2, bg="gray", font=("Arial", 14, "bold"))
        self.btn_d.grid(row=0, column=2, padx=2)

        # Emergency Stop
        self.estop_btn = tk.Button(self.panel, text="EMERGENCY STOP", bg="red", fg="black", font=("Arial", 14, "bold"), 
                                   command=self.emergency_stop, height=3, width=15)
        self.estop_btn.pack(side="bottom", pady=50)

    def on_press(self, event):
        char = event.char.lower()
        if char in self.key_state:
            self.key_state[char] = 1
            self.update_ui_keys()

    def on_release(self, event):
        char = event.char.lower()
        if char in self.key_state:
            self.key_state[char] = 0
            self.update_ui_keys()

    def update_ui_keys(self):
        # Change color to green when active
        self.btn_w.config(bg="green" if self.key_state['w'] else "gray")
        self.btn_a.config(bg="green" if self.key_state['a'] else "gray")
        self.btn_s.config(bg="green" if self.key_state['s'] else "gray")
        self.btn_d.config(bg="green" if self.key_state['d'] else "gray")

    def emergency_stop(self):
        print("EMERGENCY STOP TRIGGERED")
        self.key_state = {'w': 0, 'a': 0, 's': 0, 'd': 0}
        self.update_ui_keys()

    def network_loop(self):
        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) # Prevents command lag
                sock.connect((PI_IP, PORT))
                
                self.connected = True
                self.status_indicator.config(text="CONNECTED", fg="lime green")
                print("Connected to Pi (control)")

                while self.running and self.connected:
                    msg = f"{self.key_state['w']},{self.key_state['a']},{self.key_state['s']},{self.key_state['d']}\n"
                    sock.sendall(msg.encode())
                    time.sleep(0.01) # 100Hz update rate

            except Exception as e:
                if self.connected:
                    print("Connection lost. Retrying...")
                self.connected = False
                self.status_indicator.config(text="DISCONNECTED", fg="red")
                time.sleep(1) # Wait before trying to reconnect

    def update_video(self):
        if not self.running:
            return

        frames = [cam.get_frame() for cam in self.cams]

        # Combine into 2x2 grid
        top = cv2.hconcat([frames[0], frames[1]])
        bottom = cv2.hconcat([frames[2], frames[3]])
        grid = cv2.vconcat([top, bottom])

        # Convert to Tkinter image
        img = Image.fromarray(grid)
        imgtk = ImageTk.PhotoImage(image=img)
        
        self.video_label.imgtk = imgtk
        self.video_label.configure(image=imgtk)

        # Call this function again in 30 milliseconds (~33 FPS)
        self.root.after(30, self.update_video)

    def on_closing(self):
        self.running = False
        for cam in self.cams:
            cam.stop()
        self.root.destroy()

# Start the application
if __name__ == "__main__":
    root = tk.Tk()
    app = ROVDashboard(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()