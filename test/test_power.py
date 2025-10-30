import socket
import time
import re

DEVICE_IP = "192.168.178.112"
DEVICE_PORT = 8899

STATUS_REGEX = re.compile(r"\{(A[1\-]),.*?\}")

def send_command():
    """
    Toggle purifier power.
    The device expects 'ON' and doesn't send a reply.
    """
    print(f"→ Sending toggle 'ON' to {DEVICE_IP}:{DEVICE_PORT}")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((DEVICE_IP, DEVICE_PORT))

            # 1️⃣ Send the wake-up / handshake command
            print("→ Sending handshake: 'GD'")
            s.sendall(b"GD")
            time.sleep(0.5)

            # 2️⃣ Send the ON toggle command
            print("→ Sending command: 'ON'")
            s.sendall(b"ON")

            # 2️⃣ Wait briefly for device to respond
            time.sleep(1.5)

            try:
                data = s.recv(512)
                if data:
                    data_str = data.decode(errors="ignore").strip()
                    print("← Received:", data_str)
                else:
                    print("← No data received.")
            except socket.timeout:
                print("⏱ No data within 5s.")

    except Exception as e:
        print("❌ Error sending command:", e)


def get_status():
    """
    Connects, waits for automatic data, and parses it.
    Returns a dict like {'power': 'on', 'raw': '{A1,...}'}
    """
    print(f"→ Polling status from {DEVICE_IP}:{DEVICE_PORT}")
    data_str = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((DEVICE_IP, DEVICE_PORT))

            # 1️⃣ Send the wake-up / handshake command
            print("→ Sending handshake: 'GD'")
            s.sendall(b"GD")

            # 2️⃣ Wait briefly for device to respond
            time.sleep(1.5)

            try:
                data = s.recv(512)
                if data:
                    data_str = data.decode(errors="ignore").strip()
                    print("← Received:", data_str)
                else:
                    print("← No data received.")
            except socket.timeout:
                print("⏱ No data within 5s.")
    except Exception as e:
        print("❌ Connection error:", e)

    if not data_str:
        return {"power": "unknown", "raw": None}

    # parse A1 (on) or A- (off)
    m = STATUS_REGEX.search(data_str)
    if m:
        power = "on" if m.group(1) == "A1" else "off"
    else:
        power = "unknown"

    return {"power": power, "raw": data_str}


if __name__ == "__main__":
    # Example: toggle power, then check state
    send_command()
    time.sleep(0)
    state = get_status()
    print("Current state:", state)
