import serial
import time

def uart_handshake():
    print("Opening serial port...")
    try:
        ser = serial.Serial('/dev/serial0', baudrate=115200, timeout=1)
    except Exception as e:
        print(f"Failed to open port: {e}")
        return None

    print("Pinging Arduino...")
    while True:
        ser.write(b"PING\n")
        if ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line == "PONG":
                print("Handshake successful!")
                return ser
        time.sleep(1)

if __name__ == "__main__":
    ser = uart_handshake()
    if ser:
        print("UART ready.")
        ser.close()