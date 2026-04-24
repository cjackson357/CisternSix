import socket
import tkinter as tk
from PIL import Image, ImageTk
import cv2
import numpy as np
import threading
import time
try:
    from inputs import get_gamepad
except Exception:
    def get_gamepad():
        raise Exception("inputs library unavailable")
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
ry = 0
lt = 0
rt = 0
dpad_up = 0
dpad_down = 0

# Keyboard state
kb_state = {
    'w': False, 'a': False, 's': False, 'd': False,
    'q': False, 'e': False, 'r': False, 'f': False,
    'space': False, 'shift': False
}

# Active input mode: 'controller' or 'keyboard'
input_mode = 'controller'

# -------------------------------
# 🧭 3D VECTOR VISUALIZATION WIDGET
# -------------------------------
import math

class ROV3DVector:
    """
    Draws an isometric 3D grid with a movement vector arrow.
    Axes:
      X = strafe  (right stick X / A-D keys)
      Y = forward (left stick Y / W-S keys)
      Z = vertical (RT/LT or Space/Shift)
    Yaw ring shows rotation (left stick X / Q-E keys).
    """

    SIZE = 200          # canvas width & height
    SCALE = 60          # unit length in pixels
    LABEL_OFFSET = 14

    # Isometric projection angles
    ANG_X = math.radians(210)   # points down-left
    ANG_Y = math.radians(330)   # points down-right
    ANG_Z = math.radians(90)    # points up

    def __init__(self, parent):
        self.canvas = tk.Canvas(
            parent, width=self.SIZE, height=self.SIZE,
            bg="#1e1e1e", highlightthickness=0
        )
        self.cx = self.SIZE // 2
        self.cy = self.SIZE // 2 + 10   # shift centre down a touch

        self._build_static()
        self._vec_items = []    # dynamic items to erase each frame
        self._last = (0, 0, 0, 0)

    # ── geometry helpers ──────────────────────────────────────────────
    def _iso(self, x, y, z):
        """Convert 3D (x,y,z) → 2D canvas (px, py)."""
        px = self.cx + x * self.SCALE * math.cos(self.ANG_X) \
                     + y * self.SCALE * math.cos(self.ANG_Y) \
                     + z * self.SCALE * math.cos(self.ANG_Z)
        py = self.cy + x * self.SCALE * math.sin(self.ANG_X) \
                     + y * self.SCALE * math.sin(self.ANG_Y) \
                     + z * self.SCALE * math.sin(self.ANG_Z)
        return px, py

    def _arrow(self, x0, y0, x1, y1, color, width=2, head=8):
        """Draw an arrow from (x0,y0) to (x1,y1) on the canvas."""
        self.canvas.create_line(x0, y0, x1, y1, fill=color, width=width, tags="vec")
        # arrowhead
        angle = math.atan2(y1 - y0, x1 - x0)
        for da in (0.45, -0.45):
            ax = x1 - head * math.cos(angle - da)
            ay = y1 - head * math.sin(angle - da)
            self.canvas.create_line(x1, y1, ax, ay, fill=color, width=width, tags="vec")

    # ── static grid ───────────────────────────────────────────────────
    def _build_static(self):
        c = self.canvas
        dim = 0.55   # half-size of grid cube

        def axis_line(x0, y0, z0, x1, y1, z1, color, dash=()):
            p0 = self._iso(x0, y0, z0)
            p1 = self._iso(x1, y1, z1)
            c.create_line(*p0, *p1, fill=color, width=1, dash=dash)

        GRID = "#2a2a3a"
        DARK  = "#222230"

        # Floor grid (XY plane, z=0)
        steps = 2
        for i in range(-steps, steps + 1):
            t = i * dim / steps
            axis_line(-dim, t, 0,  dim, t, 0, GRID)
            axis_line( t, -dim, 0, t,  dim, 0, GRID)

        # Vertical edges at corners
        for sx in (-1, 1):
            for sy in (-1, 1):
                axis_line(sx*dim, sy*dim, 0, sx*dim, sy*dim, dim, DARK)

        # Top face
        for i in range(-steps, steps + 1):
            t = i * dim / steps
            axis_line(-dim, t, dim,  dim, t, dim, DARK)
            axis_line( t, -dim, dim, t,  dim, dim, DARK)

        # Axis arrows (unit length)
        AXES = [
            ((1, 0, 0), "#e05555", "X\nstrafe"),
            ((0, 1, 0), "#55aaff", "Y\nfwd"),
            ((0, 0, 1), "#55e055", "Z\nup"),
        ]
        for (ax, ay, az), col, lbl in AXES:
            o = self._iso(0, 0, 0)
            t = self._iso(ax * dim, ay * dim, az * dim)
            c.create_line(*o, *t, fill=col, width=2, arrow=tk.LAST,
                          arrowshape=(8, 10, 4))
            c.create_text(t[0] + ax*self.LABEL_OFFSET + az*4,
                          t[1] + ay*self.LABEL_OFFSET - az*self.LABEL_OFFSET,
                          text=lbl, fill=col, font=("Arial", 7, "bold"),
                          justify="center")

        # Origin dot
        ox, oy = self._iso(0, 0, 0)
        c.create_oval(ox-3, oy-3, ox+3, oy+3, fill="white", outline="")

        # Title
        c.create_text(self.SIZE // 2, 8, text="MOVEMENT VECTOR",
                      fill="#666688", font=("Arial", 8, "bold"))

    # ── dynamic update ────────────────────────────────────────────────
    def update(self, vx, vy, vz, yaw):
        """
        vx   = strafe  (-1 … +1)
        vy   = forward (-1 … +1)
        vz   = vertical(-1 … +1)   positive = up
        yaw  = rotation(-1 … +1)   shown as ring highlight
        """
        if (vx, vy, vz, yaw) == self._last:
            return
        self._last = (vx, vy, vz, yaw)
        self.canvas.delete("vec")

        mag = math.sqrt(vx**2 + vy**2 + vz**2)
        moving = mag > 0.01

        # ── yaw ring ─────────────────────────────────────────────────
        ox, oy = self._iso(0, 0, 0)
        if abs(yaw) > 0.05:
            ring_r = 28
            yaw_col = "#ffaa00"
            # draw arc segment to indicate rotation direction
            start_a = -90
            extent  = yaw * 180
            self.canvas.create_arc(
                ox - ring_r, oy - ring_r * 0.55,
                ox + ring_r, oy + ring_r * 0.55,
                start=start_a, extent=extent,
                style=tk.ARC, outline=yaw_col, width=3, tags="vec"
            )
            # arrowhead at arc end
            end_a = math.radians(start_a + extent)
            ax = ox + ring_r * math.cos(end_a)
            ay = oy + ring_r * 0.55 * math.sin(end_a)
            self.canvas.create_oval(ax-4, ay-4, ax+4, ay+4,
                                    fill=yaw_col, outline="", tags="vec")
            self.canvas.create_text(ox, oy + ring_r * 0.55 + 10,
                                    text=f"YAW {'↻' if yaw > 0 else '↺'}",
                                    fill=yaw_col, font=("Arial", 7, "bold"),
                                    tags="vec")

        # ── movement vector ───────────────────────────────────────────
        if moving:
            # clamp to unit sphere for display
            scale = min(mag, 1.0) * 0.85
            nx, ny, nz = (vx/mag)*scale, (vy/mag)*scale, (vz/mag)*scale

            tip = self._iso(nx, ny, nz)

            # colour: blend red↔green based on z component
            r = int(80 + 175 * (0.5 - vz * 0.5))
            g = int(200 + 55  * (vz * 0.5 + 0.5))
            b = int(100 + 100 * abs(vx))
            r, g, b = max(0,min(255,r)), max(0,min(255,g)), max(0,min(255,b))
            vec_col = f"#{r:02x}{g:02x}{b:02x}"

            # glow: slightly thicker behind
            self._arrow(ox, oy, tip[0], tip[1], "#3a3a3a", width=6)
            self._arrow(ox, oy, tip[0], tip[1], vec_col, width=3, head=10)

            # dashed projection lines to each plane
            # project onto floor (z=0)
            floor = self._iso(nx, ny, 0)
            self.canvas.create_line(*floor, *tip, fill="#555566",
                                    dash=(3,4), width=1, tags="vec")
            self.canvas.create_line(ox, oy, *floor, fill="#444455",
                                    dash=(2,5), width=1, tags="vec")

            # speed label
            self.canvas.create_text(
                self.SIZE // 2, self.SIZE - 8,
                text=f"spd {mag:.2f}  vx{vx:+.1f} vy{vy:+.1f} vz{vz:+.1f}",
                fill="#aaaacc", font=("Arial", 7), tags="vec"
            )
        else:
            # idle — show pulsing "IDLE" text
            self.canvas.create_text(
                self.SIZE // 2, self.SIZE - 8,
                text="IDLE — no input",
                fill="#444466", font=("Arial", 8, "italic"), tags="vec"
            )

    def pack(self, **kw):
        self.canvas.pack(**kw)


# -------------------------------
# 🎮 INPUT THREAD
# -------------------------------
def input_thread():
    global lx, ly, rx, ry, lt, rt, dpad_up, dpad_down, input_mode

    # Test whether a controller is actually present before looping
    try:
        get_gamepad()
    except Exception:
        print("No controller detected — defaulting to keyboard mode.")
        input_mode = 'keyboard'
        return  # keyboard events are handled by tkinter bindings; nothing more to do

    # Controller is present — poll continuously
    while True:
        try:
            events = get_gamepad()
            for event in events:
                if event.code == 'ABS_X':
                    lx = apply_deadzone(event.state / 32768)
                elif event.code == 'ABS_Y':
                    ly = apply_deadzone(-event.state / 32768)
                elif event.code == 'ABS_RX':
                    rx = apply_deadzone(event.state / 32768)
                elif event.code == 'ABS_RY':
                    ry = apply_deadzone(-event.state / 32768)
                elif event.code == 'ABS_Z':
                    lt = event.state / 255
                elif event.code == 'ABS_RZ':
                    rt = event.state / 255
                elif event.code == 'ABS_HAT0Y':
                    dpad_up = 1 if event.state == -1 else 0
                    dpad_down = 1 if event.state == 1 else 0
        except Exception as e:
            print(f"Controller disconnected ({e}) — switching to keyboard mode.")
            lx = ly = rx = ry = lt = rt = dpad_up = dpad_down = 0
            input_mode = 'keyboard'
            break  # stop polling; tkinter keyboard bindings take over

# -------------------------------
# 🌐 NETWORK THREAD
# -------------------------------
def network_thread():
    global lx, ly, rx, lt, rt, dpad_up, dpad_down
    global kb_state, input_mode

    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((PI_IP, PORT))
            print("Connected to Pi (control)")

            sock.setblocking(False)
            buffer = ""

            while True:
                if input_mode == 'keyboard':
                    # Map keyboard keys to the same 7-value format the server expects:
                    # lx, ly, rx, lt, rt, dpad_up, dpad_down
                    kb_lx = (1.0 if kb_state['d'] else 0.0) - (1.0 if kb_state['a'] else 0.0)
                    kb_ly = (1.0 if kb_state['w'] else 0.0) - (1.0 if kb_state['s'] else 0.0)
                    kb_rx = (1.0 if kb_state['e'] else 0.0) - (1.0 if kb_state['q'] else 0.0)
                    kb_lt = 1.0 if kb_state['shift'] else 0.0
                    kb_rt = 1.0 if kb_state['space'] else 0.0
                    kb_dpad_up = 1.0 if kb_state['r'] else 0.0
                    kb_dpad_down = 1.0 if kb_state['f'] else 0.0
                    msg = f"{kb_lx},{kb_ly},{kb_rx},{kb_lt},{kb_rt},{kb_dpad_up},{kb_dpad_down}\n"
                else:
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

        # -------------------------------
        # Tab buttons
        # -------------------------------
        self.tab_frame = tk.Frame(self.panel, bg="#1e1e1e")
        self.tab_frame.pack(anchor="w", pady=(0, 6))

        self.tab_controller_btn = tk.Button(
            self.tab_frame, text="Controller", font=("Arial", 11, "bold"),
            bg="#3a3a3a", fg="white", relief="flat", padx=14, pady=4,
            command=self.switch_to_controller
        )
        self.tab_controller_btn.pack(side="left", padx=(0, 4))

        self.tab_keyboard_btn = tk.Button(
            self.tab_frame, text="Keyboard", font=("Arial", 11, "bold"),
            bg="#2a2a2a", fg="#888888", relief="flat", padx=14, pady=4,
            command=self.switch_to_keyboard
        )
        self.tab_keyboard_btn.pack(side="left")

        # -------------------------------
        # Controller panel
        # -------------------------------
        self.controller_frame = tk.Frame(self.panel, bg="#1e1e1e")
        self.controller_frame.pack()

        self.canvas = tk.Canvas(self.controller_frame, width=400, height=600, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack()

        self.controller_img = Image.open("controller.png")
        self.controller_img = self.controller_img.resize((400, 300))
        self.controller_tk = ImageTk.PhotoImage(self.controller_img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.controller_tk)

        self.lt_rect = self.canvas.create_rectangle(50, 310, 150, 340, outline="white")
        self.rt_rect = self.canvas.create_rectangle(250, 310, 350, 340, outline="white")

        self.canvas.create_text(100, 355, text="LT", fill="white", font=("Arial", 12, "bold"))
        self.canvas.create_text(300, 355, text="RT", fill="white", font=("Arial", 12, "bold"))

        self.joy_center = (150, 420)
        self.joy2_center = (250, 420)
        self.joy_radius = 40

        self.canvas.create_oval(
            self.joy_center[0] - self.joy_radius,
            self.joy_center[1] - self.joy_radius,
            self.joy_center[0] + self.joy_radius,
            self.joy_center[1] + self.joy_radius,
            outline="white"
        )
        self.canvas.create_oval(
            self.joy2_center[0] - self.joy_radius,
            self.joy2_center[1] - self.joy_radius,
            self.joy2_center[0] + self.joy_radius,
            self.joy2_center[1] + self.joy_radius,
            outline="white"
        )

        self.canvas.create_text(self.joy_center[0], self.joy_center[1] + self.joy_radius + 15,
                                text="L", fill="white", font=("Arial", 14, "bold"))
        self.canvas.create_text(self.joy2_center[0], self.joy2_center[1] + self.joy_radius + 15,
                                text="R", fill="white", font=("Arial", 14, "bold"))

        self.joy_dot = self.canvas.create_oval(0, 0, 0, 0, fill="white")
        self.joy2_dot = self.canvas.create_oval(0, 0, 0, 0, fill="white")

        # 3D vector widget — controller panel
        self.vec3d_ctrl = ROV3DVector(self.controller_frame)
        self.vec3d_ctrl.pack(pady=(6, 0))

        self.dpad_up_rect = self.canvas.create_rectangle(190, 500, 210, 520, fill="white")
        self.dpad_down_rect = self.canvas.create_rectangle(190, 540, 210, 560, fill="white")
        self.canvas.create_rectangle(170, 520, 230, 540, fill="white")

        # -------------------------------
        # Keyboard panel
        # -------------------------------
        self.keyboard_frame = tk.Frame(self.panel, bg="#1e1e1e")
        # (not packed yet — shown only when keyboard tab is active)

        kb_canvas_w, kb_canvas_h = 400, 560
        self.kb_canvas = tk.Canvas(self.keyboard_frame, width=kb_canvas_w, height=kb_canvas_h,
                                   bg="#1e1e1e", highlightthickness=0)
        self.kb_canvas.pack()

        # Key size and helpers
        KS = 52   # key size
        GAP = 6   # gap between keys

        def key_x(col): return 20 + col * (KS + GAP)
        def key_y(row): return 20 + row * (KS + GAP)

        def draw_key(canvas, x, y, label, size=KS, label2=None):
            rect = canvas.create_rectangle(x, y, x + size, y + KS,
                                           fill="#2e2e2e", outline="#555555", width=2)
            txt = canvas.create_text(x + size // 2, y + KS // 2,
                                     text=label, fill="white",
                                     font=("Arial", 13, "bold"))
            sub = None
            if label2:
                sub = canvas.create_text(x + size // 2, y + KS // 2 + 14,
                                         text=label2, fill="#aaaaaa",
                                         font=("Arial", 8))
            return rect, txt, sub

        # Row 0: Q  W  E  (turn left | forward | turn right)
        self.kb_items = {}

        r0y = key_y(0)
        rect, txt, sub = draw_key(self.kb_canvas, key_x(0), r0y, "Q", label2="turn L")
        self.kb_items['q'] = (rect, txt, sub)

        rect, txt, sub = draw_key(self.kb_canvas, key_x(1), r0y, "W", label2="forward")
        self.kb_items['w'] = (rect, txt, sub)

        rect, txt, sub = draw_key(self.kb_canvas, key_x(2), r0y, "E", label2="turn R")
        self.kb_items['e'] = (rect, txt, sub)

        # Row 1: A  S  D  (strafe L | backward | strafe R)
        r1y = key_y(1)
        rect, txt, sub = draw_key(self.kb_canvas, key_x(0), r1y, "A", label2="strafe L")
        self.kb_items['a'] = (rect, txt, sub)

        rect, txt, sub = draw_key(self.kb_canvas, key_x(1), r1y, "S", label2="backward")
        self.kb_items['s'] = (rect, txt, sub)

        rect, txt, sub = draw_key(self.kb_canvas, key_x(2), r1y, "D", label2="strafe R")
        self.kb_items['d'] = (rect, txt, sub)

        # Row 2: R  F  (depth gauge up | depth gauge down)
        r2y = key_y(2)
        rect, txt, sub = draw_key(self.kb_canvas, key_x(0), r2y, "R", label2="gauge ↑")
        self.kb_items['r'] = (rect, txt, sub)

        rect, txt, sub = draw_key(self.kb_canvas, key_x(1), r2y, "F", label2="gauge ↓")
        self.kb_items['f'] = (rect, txt, sub)

        # Row 3: Shift (wide) and Space (wide)
        r3y = key_y(3)
        shift_w = KS * 2 + GAP
        rect, txt, sub = draw_key(self.kb_canvas, key_x(0), r3y, "L-Shift", size=shift_w, label2="down")
        self.kb_items['shift'] = (rect, txt, sub)

        space_w = KS * 3 + GAP * 2
        rect, txt, sub = draw_key(self.kb_canvas, key_x(0), key_y(4), "Space", size=space_w, label2="up")
        self.kb_items['space'] = (rect, txt, sub)

        # Legend
        self.kb_canvas.create_text(kb_canvas_w // 2, key_y(5) + 10,
                                   text="Keys glow green when pressed",
                                   fill="#666666", font=("Arial", 10))

        # 3D vector widget — keyboard panel
        self.vec3d_kb = ROV3DVector(self.keyboard_frame)
        self.vec3d_kb.pack(pady=(6, 0))

        # Bind keyboard events to root
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)

        # Start in controller mode
        self.current_tab = 'controller'

    # -------------------------------
    # Tab switching
    # -------------------------------
    def switch_to_controller(self):
        global input_mode
        input_mode = 'controller'
        self.current_tab = 'controller'
        self.keyboard_frame.pack_forget()
        self.controller_frame.pack()
        self.tab_controller_btn.config(bg="#3a3a3a", fg="white")
        self.tab_keyboard_btn.config(bg="#2a2a2a", fg="#888888")

    def switch_to_keyboard(self):
        global input_mode
        input_mode = 'keyboard'
        self.current_tab = 'keyboard'
        self.controller_frame.pack_forget()
        self.keyboard_frame.pack()
        self.tab_keyboard_btn.config(bg="#3a3a3a", fg="white")
        self.tab_controller_btn.config(bg="#2a2a2a", fg="#888888")

    # -------------------------------
    # Keyboard event handlers
    # -------------------------------
    def on_key_press(self, event):
        key = event.keysym.lower()
        if key in ('w', 'a', 's', 'd', 'q', 'e', 'r', 'f'):
            kb_state[key] = True
        elif key == 'space':
            kb_state['space'] = True
        elif key in ('shift_l', 'shift_r', 'shift'):
            kb_state['shift'] = True

    def on_key_release(self, event):
        key = event.keysym.lower()
        if key in ('w', 'a', 's', 'd', 'q', 'e', 'r', 'f'):
            kb_state[key] = False
        elif key == 'space':
            kb_state['space'] = False
        elif key in ('shift_l', 'shift_r', 'shift'):
            kb_state['shift'] = False

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

        # ── compute movement vector from active input ─────────────────
        if input_mode == 'keyboard':
            v_x   = (1.0 if kb_state['d'] else 0.0) - (1.0 if kb_state['a'] else 0.0)
            v_y   = (1.0 if kb_state['w'] else 0.0) - (1.0 if kb_state['s'] else 0.0)
            v_z   = (1.0 if kb_state['space'] else 0.0) - (1.0 if kb_state['shift'] else 0.0)
            v_yaw = (1.0 if kb_state['e'] else 0.0) - (1.0 if kb_state['q'] else 0.0)
        else:
            v_x   = lx
            v_y   = ly
            v_z   = rt - lt
            v_yaw = rx

        # update whichever vector widget is visible
        if self.current_tab == 'controller':
            self.vec3d_ctrl.update(v_x, v_y, v_z, v_yaw)
        else:
            self.vec3d_kb.update(v_x, v_y, v_z, v_yaw)

        if self.current_tab == 'controller':
            self.canvas.itemconfig(self.lt_rect, fill="lime" if lt > 0.2 else "")
            self.canvas.itemconfig(self.rt_rect, fill="lime" if rt > 0.2 else "")

            cx, cy = self.joy_center
            r = self.joy_radius

            x = cx + lx * r
            y = cy + ly * r

            right_cx, right_cy = self.joy2_center
            x2 = right_cx + rx * r
            y2 = right_cy + ry * r

            color = "lime" if abs(lx) > 0.1 or abs(ly) > 0.1 else "white"
            color2 = "lime" if abs(rx) > 0.1 or abs(ry) > 0.1 else "white"

            self.canvas.coords(self.joy_dot, x-8, y-8, x+8, y+8)
            self.canvas.itemconfig(self.joy_dot, fill=color)
            self.canvas.coords(self.joy2_dot, x2-8, y2-8, x2+8, y2+8)
            self.canvas.itemconfig(self.joy2_dot, fill=color2)

            self.canvas.itemconfig(self.dpad_up_rect, fill="lime" if dpad_up else "white")
            self.canvas.itemconfig(self.dpad_down_rect, fill="lime" if dpad_down else "white")

        elif self.current_tab == 'keyboard':
            for key, (rect, txt, sub) in self.kb_items.items():
                pressed = kb_state.get(key, False)
                self.kb_canvas.itemconfig(rect, fill="#00cc44" if pressed else "#2e2e2e",
                                          outline="#00ff55" if pressed else "#555555")
                self.kb_canvas.itemconfig(txt, fill="#003311" if pressed else "white")
                if sub:
                    self.kb_canvas.itemconfig(sub, fill="#005522" if pressed else "#aaaaaa")

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
