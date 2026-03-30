import socket
import keyboard
import time

PI_IP = "192.168.1.2"   # CHANGE to your Pi's IP
PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((PI_IP, PORT))

try:

    while True:

        w = int(keyboard.is_pressed("w"))
        a = int(keyboard.is_pressed("a"))
        s = int(keyboard.is_pressed("s"))
        d = int(keyboard.is_pressed("d"))

        message = f"{w},{a},{s},{d}\n"

        sock.sendall(message.encode())

        time.sleep(0.02)

except KeyboardInterrupt:
    sock.close()