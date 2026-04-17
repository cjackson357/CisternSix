import serial
import time

def test_uart_handshake():
    print("Opening serial port...")
    try:
        ser = serial.Serial('/dev/serial0', baudrate=115200, timeout=2)
    except Exception as e:
        print(f"Failed to open port: {e}")
        return False

    # Wait for Arduino to boot and send READY
    print("Waiting for Arduino READY signal...")
    start = time.time()
    ready = False
    while time.time() - start < 5:  # 5 second timeout
        if ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            print(f"Received: '{line}'")
            if line == "READY":
                ready = True
                break

    if not ready:
        print("No READY signal received within 5 seconds")
        ser.close()
        return False

    print("Arduino is READY — sending PING...")
    ser.write(b"PING\n")

    # Wait for PONG
    start = time.time()
    while time.time() - start < 3:
        if ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            print(f"Received: '{line}'")
            if line == "PONG":
                print("Handshake successful! UART is working.")
                ser.close()
                return True

    print("No PONG received — Arduino not responding to commands")
    ser.close()
    return False

if __name__ == "__main__":
    success = test_uart_handshake()
    if not success:
        print("\nDiagnosis: UART hardware or wiring issue")