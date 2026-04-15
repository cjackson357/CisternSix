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

class ROVDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("ROV Command Station")
        self.root.configure(bg="#1e1e1e")

        self.running = True
        self.setup_ui()

        threading.Thread(target=input_thread, daemon=True).start()
        self.update_ui_loop()

    def setup_ui(self):
        self.panel = tk.Frame(self.root, bg="#1e1e1e")
        self.panel.pack(padx=20, pady=20)

        # --- Controller Image ---
        self.canvas = tk.Canvas(self.panel, width=400, height=300, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack()

        self.controller_img = Image.open("controller.png")  # user-provided
        self.controller_img = self.controller_img.resize((400, 300))
        self.controller_tk = ImageTk.PhotoImage(self.controller_img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.controller_tk)

        # --- Trigger Rectangles ---
        self.lt_rect = self.canvas.create_rectangle(50, 310, 150, 340, outline="white")
        self.rt_rect = self.canvas.create_rectangle(250, 310, 350, 340, outline="white")

        # Labels
        self.canvas.create_text(100, 355, text="LT", fill="white", font=("Arial", 12, "bold"))
        self.canvas.create_text(300, 355, text="RT", fill="white", font=("Arial", 12, "bold"))

        # --- Joystick ---
        self.joy_center = (200, 420)
        self.joy_radius = 40

        self.canvas.config(height=500)

        self.canvas.create_oval(
            self.joy_center[0] - self.joy_radius,
            self.joy_center[1] - self.joy_radius,
            self.joy_center[0] + self.joy_radius,
            self.joy_center[1] + self.joy_radius,
            outline="white"
        )

        self.joy_dot = self.canvas.create_oval(0, 0, 0, 0, fill="white")

        # --- D-Pad Cross ---
        self.dpad_center = (200, 520)
        self.dpad_size = 20

        self.canvas.config(height=600)

        # Up
        self.dpad_up_rect = self.canvas.create_rectangle(190, 500, 210, 520, fill="white")
        # Down
        self.dpad_down_rect = self.canvas.create_rectangle(190, 540, 210, 560, fill="white")
        # Center horizontal
        self.canvas.create_rectangle(170, 520, 230, 540, fill="white")

    def update_ui_loop(self):
        global lx, ly, lt, rt, dpad_up, dpad_down

        # --- Triggers ---
        lt_color = "lime" if lt > 0.2 else ""
        rt_color = "lime" if rt > 0.2 else ""

        self.canvas.itemconfig(self.lt_rect, fill=lt_color)
        self.canvas.itemconfig(self.rt_rect, fill=rt_color)

        # --- Joystick ---
        cx, cy = self.joy_center
        r = self.joy_radius

        x = cx + lx * r
        y = cy + ly * r

        color = "lime" if abs(lx) > 0.1 or abs(ly) > 0.1 else "white"

        self.canvas.coords(self.joy_dot, x-8, y-8, x+8, y+8)
        self.canvas.itemconfig(self.joy_dot, fill=color)

        # --- D-Pad ---
        self.canvas.itemconfig(self.dpad_up_rect, fill="lime" if dpad_up else "white")
        self.canvas.itemconfig(self.dpad_down_rect, fill="lime" if dpad_down else "white")

        self.root.after(50, self.update_ui_loop)

if __name__ == "__main__":
    root = tk.Tk()
    app = ROVDashboard(root)
    root.mainloop()
