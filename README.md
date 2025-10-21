# Ideal Pro Home Assistant Integration

This repository contains a custom Home Assistant integration for Ideal Pro devices, such as air purifiers. It allows users to control and monitor their Ideal Pro devices directly from Home Assistant.

## Features

*   **Power Control**: Turn the Ideal Pro device on or off.
*   **Status Monitoring**: Retrieve the current power status (on/off) and other operational parameters from the device.
*   **Easy Setup**: Configurable via Home Assistant's UI.

## Supported Devices

This integration is designed for Ideal Pro devices (e.g., air purifiers like AP30, AP40, AP60, AP80, AP140) that communicate via TCP/IP on port `8899`. It relies on a "GD" handshake for status retrieval and an "ON" command for toggling power.

## Installation (Home Assistant Custom Component)

To install this integration, follow these steps:

1.  **Manual Installation**:
    *   Create a folder named `ideal_pro` inside your Home Assistant `custom_components` directory.
        *   The `custom_components` directory is typically located at `/config/custom_components/`. If it doesn't exist, create it.
    *   Copy all files from the `Ideal-Pro-Home-Assistant` repository (specifically `api.py`, `__init__.py`, `config_flow.py`, `const.py`, `switch.py`) into the newly created `/config/custom_components/ideal_pro/` folder.
    *   The final structure should look like:
        ```
        <homeassistant_config_dir>/
        └── custom_components/
            └── ideal_pro/
                ├── __init__.py
                ├── api.py
                ├── config_flow.py
                ├── const.py
                └── switch.py
        ```

2.  **Restart Home Assistant**: After placing the files, restart your Home Assistant instance to ensure the new component is loaded.

3.  **Add Integration**:
    *   In the Home Assistant frontend, navigate to `Configuration` -> `Integrations`.
    *   Click the `+ Add Integration` button.
    *   Search for "Ideal Pro" and select it from the list.
    *   You will be prompted to enter the **IP address** of your Ideal Pro device.
    *   Follow any further prompts to complete the setup.

## Usage

Once configured, a new `switch` entity will appear in your Home Assistant instance (e.g., `switch.ideal_pro`). You can use this entity to:

*   Turn your Ideal Pro device **on** or **off**.
*   View the current **power status** of the device.

## For Developers / Standalone Usage

The `api.py` file provides the core asynchronous API for interacting with Ideal Pro devices.

### `IdealProAPI` Class

*   `__init__(self, host: str, port: int = 8899)`: Initializes the API client with the device's host and port.
*   `async_handshake_and_read(self, timeout: float = 2.0) -> Optional[str]`: Connects to the device, sends a "GD" handshake command, and attempts to read a status block within the specified timeout.
*   `async_toggle(self)`: Sends the "GD" handshake followed by the "ON" command to toggle the device's power state. Note that "ON" acts as a toggle for these devices.
*   `parse_status(self, raw: str) -> Dict`: Parses a raw status string received from the device (e.g., `{A1,FR,C00000,...}`) into a dictionary, extracting the power state (`"on"` or `"off"`) and other key-value pairs.

### Example Standalone Script

The `test_ideal_pro_on_off.py` script demonstrates how to interact with an Ideal Pro device using a synchronous socket connection, outside of Home Assistant. This can be useful for testing or debugging.

```python
import socket
import time
import re

DEVICE_IP = "192.168.178.112" # <<< IMPORTANT: Replace with your Ideal Pro device's IP address
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
    print("--- Toggling Device ---")
    send_command()
    time.sleep(2) # Give device time to change state
    print("\n--- Getting Status After Toggle ---")
    state = get_status()
    print("Current state:", state)
```