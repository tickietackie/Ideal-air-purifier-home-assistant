# Ideal Pro Home Assistant Integration

This repository contains a custom Home Assistant integration for Ideal Pro devices, such as air purifiers. It allows users to control and monitor their Ideal Pro devices directly from Home Assistant.

## Features

*   **Smart Fan Control**: Control fan speed with presets: `Quiet`, `Auto`, `Speed 1`, `Speed 2`, `Speed 3`, and `Turbo`.
*   **Power Control**: Turn the device on or off. The integration automatically handles device state toggling.
*   **Robust State Synchronization**:
    *   **Auto-Polling**: Automatically updates device state in Home Assistant every 30 seconds.
    *   **State Recovery**: If the device is unplugged or loses power, Home Assistant will correctly mark it as `Unavailable` and recover connection automatically when it returns.
    *   **Verification**: Commands (like changing speed) are verified by checking the device's response, ensuring the action actually happened.
*   **LED Control**: Turn the LED off/on and set brightness (via automated scripts or potentially exposed entities).
*   **Air Quality**: PM2.5 sensor based on the purifier's built-in particle sensor (device field `D`, reported as µg/m³ with two decimals).
*   **Easy Setup**: Configurable via Home Assistant's UI.

## Supported Devices

This integration is designed for Ideal Pro devices (e.g., air purifiers like AP30, AP40, AP60, AP80, AP140) that communicate via TCP/IP on port `8899`. It relies on a "GD" handshake for status retrieval and an "ON" command for toggling power.

## Installation

### Option 1: HACS (Recommended)

1.  Open HACS in Home Assistant.
2.  Go to **Integrations** > Top right menu (3 dots) > **Custom repositories**.
3.  Add the URL of this repository.
4.  Category: **Integration**.
5.  Click **Add** -> **Download**.
6.  Restart Home Assistant.

### Option 2: Manual Installation

1.  Using the File Editor or SSH, go to your Home Assistant `config` directory.
2.  Create a folder `custom_components/idealpro` if it doesn't exist.
3.  Copy all files from the `custom_components/idealpro/` folder in this repository to that new directory.
4.  Restart Home Assistant.

### Configuration

1.  In the Home Assistant frontend, navigate to **Settings** -> **Devices & Services**.
2.  Click the **+ Add Integration** button.
3.  Search for "Ideal Pro" and select it.
4.  Enter the **IP address** of your device (port 8899 is default).
5.  Submit.

## Usage

Once configured, the following entities will appear in your Home Assistant instance (e.g., `ideal_pro`):

*   **Fan Entity** (`fan.ideal_pro_fan`):
    *   Turn on/off.
    *   Set preset modes: `Auto`, `Quiet`, `Turbo`, `Speed 1-3`.
*   **Switch Entity** (`switch.ideal_pro`):
    *   Simple on/off toggle for the main power.
*   **PM2.5 Sensor** (`sensor.ideal_pro_pm2_5`):
    *   Current PM2.5 concentration in µg/m³ from the purifier's particle sensor.
    *   Extra attributes: raw gas sensor value and full raw status.
*   **Diagnostic Sensors** (hidden under the device's Diagnostic section):
    *   `sensor.ideal_pro_fan_rpm`: motor speed in RPM.
    *   `sensor.ideal_pro_auto_stage`: stage selected by auto mode (`off`/`low`/`medium`/`high`).
    *   `sensor.ideal_pro_boost_remaining`: seconds left of the current auto boost.
    *   `sensor.ideal_pro_operating_hours`: total operating hours (useful for filter maintenance).

**Note:** If you change the device settings externally (e.g., via the physical remote or another app), Home Assistant will update its state within 30 seconds.

## For Developers / Standalone Usage

The `test/` directory contains useful scripts for testing device connectivity and API behavior without needing a full Home Assistant installation.

### Testing Tools

1.  **Fan Control Test** (`test/test_fan.py`):
    *   Interactive tool to test all fan speeds and read status.
    *   Run: `python3 test/test_fan.py` for an interactive menu.
    *   Run: `python3 test/test_fan.py status` to see just the current status.

2.  **Power Control Test** (`test/test_power.py`):
    *   Tests reliable power toggling with verification.
    *   Run: `python3 test/test_power.py` for interactve menu.

3.  **Parser Unit Tests** (`test/test_parse_status.py`):
    *   Validates `parse_status` against real status frames captured from a device (see `captures/`).
    *   Run: `python3 test/test_parse_status.py` (also works with `pytest test/test_parse_status.py`).

### API Usage Example

The `custom_components/idealpro/api.py` file provides the core asynchronous API.

```python
import asyncio
import sys

sys.path.insert(0, "custom_components/idealpro")
from api import IdealProAPI

async def main():
    api = IdealProAPI("192.168.178.112")
    
    # Get current status
    status = await api.async_get_power_state()
    print(f"Device is: {status}")
    
    # Turn on reliably
    await api.async_turn_on()
    
    # Set Fan Speed
    await api.async_set_fan_speed_verified("auto")

if __name__ == "__main__":
    asyncio.run(main())
```

## Reverse Engineered API Documentation

The following information has been reverse-engineered from network captures and device behavior.

### Protocol Overview

*   **Protocol**: TCP
*   **Port**: 8899
*   **Handshake**: The client must send `GD` to wake up the device or request a status update. The device may push status updates spontaneously after connection or in response to commands.

### Commands

All commands are sent as ASCII strings. A `GD` handshake is recommended before sending commands.

| Action | Command | Description |
| :--- | :--- | :--- |
| **Handshake/Status** | `GD` | Requests current status. |
| **Toggle Power** | `ON` | Toggles power on/off (state dependent). |
| **Quiet Mode** | `SQ` | Sets fan to Quiet mode. |
| **Auto Mode** | `SA` | Sets fan to Auto mode. |
| **Speed 1** | `S1` | Sets fan to Speed 1. |
| **Speed 2** | `S2` | Sets fan to Speed 2. |
| **Speed 3** | `S3` | Sets fan to Speed 3. |
| **Turbo Mode** | `ST` | Sets fan to Turbo mode. |
| **Set Brightness** | `D0` - `D9` | Sets LED brightness (0=Off, 9=Max). |

### Status Response Format

The device returns a status string enclosed in curly braces, typically comma-separated.
Example: `{A1,FO,C00000,S1,KI,L9,D1417,V0249,R0249,N00000,O00000,Y0674,Z01771,P094,W01,HD0N1,I0275,J0000,U0540,T40,X006}`

#### Parsing Key Fields:

1.  **First Token (Power & Mode)**:
    *   `A-`, `A0`: Device is **OFF**.
    *   `A1`, `A2`, `A3`: **Auto Mode** (running at speed 1, 2, or 3).
    *   `M1`, `M2`, `M3`: **Manual Mode** (Speed 1, 2, or 3).
    *   `MQ`: **Quiet Mode**.
    *   `MT`: **Turbo Mode**.

2.  **LED Brightness**:
    *   Look for a token starting with `HD` followed by a digit.
    *   Example: `HD0...` -> Brightness 0 (Off), `HD9...` -> Brightness 9 (Max).