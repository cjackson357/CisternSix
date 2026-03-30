import socket
import RPi.GPIO as GPIO

PORT = 5005

PIN_W = 17
PIN_A = 27
PIN_S = 22
PIN_D = 23

GPIO.setmode(GPIO.BCM)

GPIO.setup(PIN_W, GPIO.OUT)
GPIO.setup(PIN_A, GPIO.OUT)
GPIO.setup(PIN_S, GPIO.OUT)
GPIO.setup(PIN_D, GPIO.OUT)

GPIO.output(PIN_W, GPIO.LOW)
GPIO.output(PIN_A, GPIO.LOW)
GPIO.output(PIN_S, GPIO.LOW)
GPIO.output(PIN_D, GPIO.LOW)

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("0.0.0.0", PORT))
server.listen(1)

print("Waiting for connection...")

conn, addr = server.accept()
print("Connected from:", addr)

buffer = ""

try:
    while True:

        data = conn.recv(1024)

        if not data:
            break

        buffer += data.decode()

        while "\n" in buffer:

            line, buffer = buffer.split("\n", 1)

            try:
                w, a, s, d = line.strip().split(",")

                GPIO.output(PIN_W, int(w))
                GPIO.output(PIN_A, int(a))
                GPIO.output(PIN_S, int(s))
                GPIO.output(PIN_D, int(d))

            except:
                pass

finally:

    GPIO.output(PIN_W, GPIO.LOW)
    GPIO.output(PIN_A, GPIO.LOW)
    GPIO.output(PIN_S, GPIO.LOW)
    GPIO.output(PIN_D, GPIO.LOW)

    conn.close()
    GPIO.cleanup()
