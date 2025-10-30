import socket
import time
import re

DEVICE_IP = "192.168.178.112"
DEVICE_PORT = 8899

# Regexes for parsing
STATUS_REGEX = re.compile(r"\{(A[1\-]),.*?\}")
BRIGHTNESS_REGEX = re.compile(r"HD(\d+)")

# ---------------------------
#  Low-level command functions
# ---------------------------

def send_handshake(sock):
    """Send 'GD' handshake."""
    print("→ Sending handshake: 'GD'")
    sock.sendall(b"GD")
    time.sleep(0.3)


def send_brightness(level):
    """Send D0–D9 brightness command to the device."""
    assert 0 <= level <= 9, f"Brightness {level} invalid (must be 0–9)"
    cmd = f"D{level}".encode()
    print(f"→ Sending brightness command: {cmd!r}")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((DEVICE_IP, DEVICE_PORT))
            send_handshake(s)
            time.sleep(0.2)
            s.sendall(cmd)
            time.sleep(1.0)
            try:
                data = s.recv(512)
                if data:
                    msg = data.decode(errors="ignore").strip()
                    print("← Received:", msg)
                else:
                    print("← No data received.")
            except socket.timeout:
                print("⏱ No data within 5s.")
    except Exception as e:
        print("❌ Error sending brightness command:", e)


def read_status():
    """Poll current device status and parse key info."""
    print(f"→ Polling status from {DEVICE_IP}:{DEVICE_PORT}")
    raw_text = ""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((DEVICE_IP, DEVICE_PORT))
            send_handshake(s)
            time.sleep(1.0)
            try:
                data = s.recv(512)
                if data:
                    raw_text = data.decode(errors="ignore").strip()
                    print("← Received:", raw_text)
                else:
                    print("← No data received.")
            except socket.timeout:
                print("⏱ No data within 5s.")
    except Exception as e:
        print("❌ Connection error:", e)
        return {"power": "unknown", "brightness": None, "raw": None}

    # Power parsing (A1=on, A-=off)
    m_power = STATUS_REGEX.search(raw_text)
    power = "on" if (m_power and m_power.group(1) == "A1") else "off"

    # Brightness parsing (HDx...)
    m_bright = BRIGHTNESS_REGEX.search(raw_text)
    brightness = int(m_bright.group(1)) if m_bright else None

    return {"power": power, "brightness": brightness, "raw": raw_text}


# ---------------------------
#  Test scenario
# ---------------------------

def test_brightness_cycle(level: int):
    """
    Test setting a brightness twice, verify status each time,
    then set brightness to 0 to turn off and verify again.
    """
    print("\n==============================")
    print(f" TEST: Set brightness level {level}")
    print("==============================")

    # 1️⃣ First write
    send_brightness(level)
    time.sleep(3.0)
    state1 = read_status()
    print(f"→ After 1st set: brightness={state1['brightness']} power={state1['power']}\n")

    # 2️⃣ Second write (level +1)
    send_brightness(level +1)
    time.sleep(3.0)
    state2 = read_status()
    print(f"→ After 2nd set: brightness={state2['brightness']} power={state2['power']}\n")

    # 3️⃣ Turn off
    send_brightness(0)
    time.sleep(3.0)
    state3 = read_status()
    print(f"→ After OFF: brightness={state3['brightness']} power={state3['power']}\n")

    print("------------------------------")
    print("SUMMARY:")
    print(f"  1st read: {state1}")
    print(f"  2nd read: {state2}")
    print(f"  Off read: {state3}")
    print("==============================\n")


if __name__ == "__main__":
    # Example run: set brightness to 5, verify, then off
    test_brightness_cycle(level=5)