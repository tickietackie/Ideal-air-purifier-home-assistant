import asyncio
import logging
import re
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)

STATUS_RE = re.compile(r"\{(.+?)\}")

# Timeout for establishing a TCP connection (seconds)
CONNECT_TIMEOUT = 5.0
# Maximum retries for state-aware commands
MAX_RETRIES = 5
# Delay between retry attempts (seconds)
RETRY_DELAY = 0.5
# Delay after sending toggle before checking state (device needs time to update)
POST_TOGGLE_DELAY = 1.0
# Delay between the GD handshake and a command sent on the same connection (seconds)
COMMAND_PRE_DELAY = 0.2
# Delay to let the device process a command before closing the connection (seconds)
COMMAND_POST_DELAY = 0.1


class IdealProAPI:
    def __init__(self, host: str, port: int = 8899):
        self.host = host
        self.port = port

    async def _connect(self):
        """Open a TCP connection to the device."""
        return await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=CONNECT_TIMEOUT
        )

    @staticmethod
    async def _close(writer) -> None:
        """Close a connection, ignoring errors during teardown."""
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

    @staticmethod
    async def _read_status(reader, timeout: float) -> str:
        """Read until a complete {...} status block arrives or timeout expires."""
        data = b""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while b"}" not in data:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                chunk = await asyncio.wait_for(reader.read(1024), timeout=remaining)
            except asyncio.TimeoutError:
                break
            if not chunk:
                break
            data += chunk
        return data.decode(errors="ignore").strip()

    async def _send(self, command: bytes) -> None:
        """Send a command, prefixed by a GD handshake, on a fresh connection."""
        _LOGGER.debug("Sending command: %s", command)
        reader, writer = await self._connect()
        try:
            writer.write(b"GD")
            await writer.drain()
            await asyncio.sleep(COMMAND_PRE_DELAY)
            writer.write(command)
            await writer.drain()
            # Wait a bit to ensure device processes the command
            await asyncio.sleep(COMMAND_POST_DELAY)
        finally:
            await self._close(writer)

    async def async_handshake_and_read(self, timeout: float = 2.0) -> Optional[str]:
        """Connect, send GD handshake and read the status block (if any)."""
        reader, writer = await self._connect()
        try:
            writer.write(b"GD")
            await writer.drain()
            return await self._read_status(reader, timeout)
        finally:
            await self._close(writer)

    async def async_get_power_state(self) -> Optional[str]:
        """
        Query current power state.
        Returns: "on", "off", or None if unable to determine.
        """
        try:
            raw = await self.async_handshake_and_read()
            if raw:
                status = self.parse_status(raw)
                return status.get("power")
        except Exception as err:
            _LOGGER.debug("Error getting power state: %s", err)
        return None

    async def async_toggle(self):
        """Send the toggle command (device uses 'ON' as toggle)."""
        await self._send(b"ON")

    async def async_turn_on(self, max_retries: int = MAX_RETRIES) -> bool:
        """
        Turn the device ON with state verification.
        
        This method:
        1. Checks current state first
        2. Only sends toggle if device is currently OFF
        3. Verifies the state changed to ON
        4. Retries if necessary
        
        Returns: True if device is confirmed ON, False otherwise
        """
        for attempt in range(max_retries):
            _LOGGER.debug("async_turn_on attempt %d/%d", attempt + 1, max_retries)
            
            # Check current state
            current_state = await self.async_get_power_state()
            _LOGGER.debug("Current power state: %s", current_state)
            
            if current_state == "on":
                _LOGGER.debug("Device already ON, no action needed")
                return True
            
            if attempt > 0 and current_state not in ("on", "off"):
                # State cannot be read reliably; don't keep toggling blindly
                _LOGGER.warning("Power state unknown, stopping ON retries")
                break
            
            # Device is off or unknown, send toggle
            _LOGGER.debug("Sending toggle command to turn ON")
            try:
                await self.async_toggle()
            except Exception as err:
                _LOGGER.warning("Toggle command failed: %s", err)
                if attempt < max_retries - 1:
                    await asyncio.sleep(RETRY_DELAY)
                continue
            
            # Wait for device to process
            await asyncio.sleep(POST_TOGGLE_DELAY)
            
            # Verify state changed
            new_state = await self.async_get_power_state()
            _LOGGER.debug("State after toggle: %s", new_state)
            
            if new_state == "on":
                _LOGGER.debug("Successfully turned ON")
                return True
            
            # State didn't change as expected, retry
            _LOGGER.warning("State verification failed, expected ON but got %s", new_state)
            if attempt < max_retries - 1:
                await asyncio.sleep(RETRY_DELAY)
        
        _LOGGER.error("Failed to turn ON after %d attempts", max_retries)
        return False

    async def async_turn_off(self, max_retries: int = MAX_RETRIES) -> bool:
        """
        Turn the device OFF with state verification.
        
        This method:
        1. Checks current state first
        2. Only sends toggle if device is currently ON
        3. Verifies the state changed to OFF
        4. Retries if necessary
        
        Returns: True if device is confirmed OFF, False otherwise
        """
        for attempt in range(max_retries):
            _LOGGER.debug("async_turn_off attempt %d/%d", attempt + 1, max_retries)
            
            # Check current state
            current_state = await self.async_get_power_state()
            _LOGGER.debug("Current power state: %s", current_state)
            
            if current_state == "off":
                _LOGGER.debug("Device already OFF, no action needed")
                return True
            
            if attempt > 0 and current_state not in ("on", "off"):
                # State cannot be read reliably; don't keep toggling blindly
                _LOGGER.warning("Power state unknown, stopping OFF retries")
                break
            
            # Device is on or unknown, send toggle
            _LOGGER.debug("Sending toggle command to turn OFF")
            try:
                await self.async_toggle()
            except Exception as err:
                _LOGGER.warning("Toggle command failed: %s", err)
                if attempt < max_retries - 1:
                    await asyncio.sleep(RETRY_DELAY)
                continue
            
            # Wait for device to process
            await asyncio.sleep(POST_TOGGLE_DELAY)
            
            # Verify state changed
            new_state = await self.async_get_power_state()
            _LOGGER.debug("State after toggle: %s", new_state)
            
            if new_state == "off":
                _LOGGER.debug("Successfully turned OFF")
                return True
            
            # State didn't change as expected, retry
            _LOGGER.warning("State verification failed, expected OFF but got %s", new_state)
            if attempt < max_retries - 1:
                await asyncio.sleep(RETRY_DELAY)
        
        _LOGGER.error("Failed to turn OFF after %d attempts", max_retries)
        return False

    def parse_status(self, raw: str) -> Dict:
        """
        Parse a status string like:
        {A1,FR,C00000,S1,KI,L9,D1410,V0261,R0261,N00000,...,HD4N1,...}

        Returns:
            {
              "raw": "...",         # original text
              "power": "on"/"off"/"unknown",
              "led_level": int(0–9), # brightness parsed from HDx...
              "fan_speed": "quiet"/"auto"/"speed_1"/"speed_2"/"speed_3"/"turbo"/"unknown",
              "body": "...",         # most recent {...} block
              ... other parsed tokens ...
            }
        """

        _LOGGER.debug("Start parsing status: %r", raw)
        out: Dict[str, Any] = {"raw": raw, "power": "unknown", "fan_speed": "unknown"}

        if not raw:
            _LOGGER.error("Raw input missing, cannot parse status.")
            return out

        # Prefer last { ... } block if multiple responses arrived at once
        matches = STATUS_RE.findall(raw)
        body = matches[-1] if matches else raw.strip("{}")

        # Split into tokens
        tokens = [t.strip() for t in body.split(",") if t.strip()]
        if not tokens:
            return out

        # The first token indicates power state AND fan mode:
        # - A0, A- = Power OFF
        # - M1, M2, M3 = MANUAL speed 1/2/3
        # - A1, A2, A3 = AUTO mode running at speed 1/2/3
        # - MQ = Quiet mode
        # - MT = Turbo mode
        first = tokens[0]
        
        # Determine power and fan speed from first token
        if first.startswith("MQ"):
            out["power"] = "on"
            out["fan_speed"] = "quiet"
        elif first.startswith("MT"):
            out["power"] = "on"
            out["fan_speed"] = "turbo"
        elif first.startswith("M1"):
            out["power"] = "on"
            out["fan_speed"] = "speed_1"
        elif first.startswith("M2"):
            out["power"] = "on"
            out["fan_speed"] = "speed_2"
        elif first.startswith("M3"):
            out["power"] = "on"
            out["fan_speed"] = "speed_3"
        elif first.startswith(("A1", "A2", "A3")):
            out["power"] = "on"
            out["fan_speed"] = "auto"
        elif first.startswith(("A-", "A0")):
            out["power"] = "off"
            out["fan_speed"] = "off"
        else:
            out["power"] = "unknown"
            out["fan_speed"] = "unknown"
            _LOGGER.warning("Unknown first token in status: %s", first)
        
        _LOGGER.debug("Parsed power=%s, fan_speed=%s from first token=%s", 
                     out["power"], out["fan_speed"], first)

        # Tokenize everything into key->value
        for token in tokens[1:]:
            m = re.match(r"([A-Z]+)(.*)", token)
            if m:
                key, val = m.group(1), m.group(2)
                out[key] = val
            else:
                out.setdefault("misc", []).append(token)

        # Detect LED brightness from HDx... (only first digits after HD)
        hd_token = next((t for t in tokens if t.startswith("HD")), None)
        if hd_token:
            m = re.match(r"HD(\d+)", hd_token)
            if m:
                out["led_level"] = int(m.group(1))
                _LOGGER.debug("Detected LED level: %s", out["led_level"])

        # PM2.5 is reported in D as µg/m³ x 100 (e.g. D1420 -> 14.20)
        try:
            out["pm25"] = int(out["D"]) / 100
        except (KeyError, TypeError, ValueError):
            pass

        out["body"] = body
        return out

    
    async def async_set_brightness(self, level: int):
        """
        Set LED brightness level (0–9).
        The device expects the command in the form 'D0'...'D9'.
        """
        if not 0 <= level <= 9:
            raise ValueError(f"Brightness level must be 0–9, got {level}")

        await self._send(f"D{level}".encode())

    async def async_get_led_level(self) -> Optional[int]:
        """
        Query current LED brightness level.
        Returns: 0-9, or None if unable to determine.
        """
        try:
            raw = await self.async_handshake_and_read()
            if raw:
                status = self.parse_status(raw)
                return status.get("led_level")
        except Exception as err:
            _LOGGER.debug("Error getting LED level: %s", err)
        return None

    async def async_set_brightness_verified(self, target_level: int, max_retries: int = MAX_RETRIES) -> bool:
        """
        Set LED brightness with state verification.
        
        This method:
        1. Checks current LED level first
        2. Only sends command if current level differs from target
        3. Verifies the level changed correctly
        4. Retries if necessary
        
        Args:
            target_level: Target brightness level (0-9)
            max_retries: Maximum number of retry attempts
        
        Returns: True if LED level is confirmed at target, False otherwise
        """
        if not 0 <= target_level <= 9:
            raise ValueError(f"Brightness level must be 0–9, got {target_level}")
        
        for attempt in range(max_retries):
            _LOGGER.debug("async_set_brightness_verified attempt %d/%d, target=%d", 
                         attempt + 1, max_retries, target_level)
            
            # Check current level
            current_level = await self.async_get_led_level()
            _LOGGER.debug("Current LED level: %s", current_level)
            
            if current_level == target_level:
                _LOGGER.debug("LED already at target level %d, no action needed", target_level)
                return True
            
            # Level is different, send brightness command
            _LOGGER.debug("Sending brightness command for level %d", target_level)
            try:
                await self.async_set_brightness(target_level)
            except Exception as err:
                _LOGGER.warning("Brightness command failed: %s", err)
                if attempt < max_retries - 1:
                    await asyncio.sleep(RETRY_DELAY)
                continue
            
            # Wait for device to process
            await asyncio.sleep(POST_TOGGLE_DELAY)
            
            # Verify level changed
            new_level = await self.async_get_led_level()
            _LOGGER.debug("LED level after command: %s", new_level)
            
            if new_level == target_level:
                _LOGGER.debug("Successfully set LED to level %d", target_level)
                return True
            
            # Level didn't change as expected, retry
            _LOGGER.warning("LED verification failed, expected %d but got %s", target_level, new_level)
            if attempt < max_retries - 1:
                await asyncio.sleep(RETRY_DELAY)
        
        _LOGGER.error("Failed to set LED level to %d after %d attempts", target_level, max_retries)
        return False

    # Fan speed mode mapping: internal name -> command bytes
    FAN_SPEED_COMMANDS = {
        "quiet": b"SQ",
        "auto": b"SA",
        "speed_1": b"S1",
        "speed_2": b"S2",
        "speed_3": b"S3",
        "turbo": b"ST",
    }
    
    FAN_SPEED_MODES = list(FAN_SPEED_COMMANDS.keys())

    async def async_get_fan_speed(self) -> Optional[str]:
        """
        Query current fan speed mode.
        Returns: "quiet", "auto", "speed_1", "speed_2", "speed_3", "turbo", or None if unable to determine.
        """
        try:
            raw = await self.async_handshake_and_read()
            if raw:
                status = self.parse_status(raw)
                return status.get("fan_speed")
        except Exception as err:
            _LOGGER.debug("Error getting fan speed: %s", err)
        return None

    async def async_set_fan_speed(self, mode: str):
        """
        Set fan speed mode.
        Mode must be one of: "quiet", "auto", "speed_1", "speed_2", "speed_3", "turbo"
        """
        if mode not in self.FAN_SPEED_COMMANDS:
            raise ValueError(f"Invalid fan speed mode: {mode}. Valid modes: {list(self.FAN_SPEED_COMMANDS.keys())}")

        await self._send(self.FAN_SPEED_COMMANDS[mode])

    # All modes are now verifiable from status response:
    # MQ=quiet, M1/M2/M3=speed_1/2/3 (MANUAL), A1/A2/A3=auto (AUTO), MT=turbo
    VERIFIABLE_MODES = {"quiet", "speed_1", "speed_2", "speed_3", "auto", "turbo"}
    # No unverifiable modes anymore!
    UNVERIFIABLE_MODES = set()

    async def async_set_fan_speed_verified(self, target_mode: str, max_retries: int = MAX_RETRIES) -> bool:
        """
        Set fan speed with state verification.
        
        This method:
        1. Checks current fan speed first
        2. Only sends command if current speed differs from target
        3. Verifies the speed changed correctly (for verifiable modes)
        4. Retries if necessary
        
        Note: "auto" and "turbo" modes cannot be verified because the device
        reports the current speed level, not the mode. For these modes,
        we send the command and assume success.
        
        Args:
            target_mode: Target fan speed mode ("quiet", "auto", "speed_1", "speed_2", "speed_3", "turbo")
            max_retries: Maximum number of retry attempts
        
        Returns: True if fan speed command was sent successfully, False otherwise
        """
        if target_mode not in self.FAN_SPEED_COMMANDS:
            raise ValueError(f"Invalid fan speed mode: {target_mode}. Valid modes: {list(self.FAN_SPEED_COMMANDS.keys())}")
        
        # For unverifiable modes (auto, turbo), just send command and assume success
        if target_mode in self.UNVERIFIABLE_MODES:
            _LOGGER.debug("Mode %s is unverifiable, sending command without verification", target_mode)
            for attempt in range(max_retries):
                try:
                    await self.async_set_fan_speed(target_mode)
                    await asyncio.sleep(POST_TOGGLE_DELAY)
                    _LOGGER.debug("Successfully sent %s command (unverified)", target_mode)
                    return True
                except Exception as err:
                    _LOGGER.warning("Fan speed command failed (attempt %d/%d): %s", 
                                   attempt + 1, max_retries, err)
                    if attempt < max_retries - 1:
                        await asyncio.sleep(RETRY_DELAY)
            _LOGGER.error("Failed to send %s command after %d attempts", target_mode, max_retries)
            return False
        
        # For verifiable modes (quiet, speed_1, speed_2, speed_3)
        for attempt in range(max_retries):
            _LOGGER.debug("async_set_fan_speed_verified attempt %d/%d, target=%s", 
                         attempt + 1, max_retries, target_mode)
            
            # Check current speed
            current_speed = await self.async_get_fan_speed()
            _LOGGER.debug("Current fan speed: %s", current_speed)
            
            if current_speed == target_mode:
                _LOGGER.debug("Fan already at target speed %s, no action needed", target_mode)
                return True
            
            # Speed is different, send command
            _LOGGER.debug("Sending fan speed command for mode %s", target_mode)
            try:
                await self.async_set_fan_speed(target_mode)
            except Exception as err:
                _LOGGER.warning("Fan speed command failed: %s", err)
                if attempt < max_retries - 1:
                    await asyncio.sleep(RETRY_DELAY)
                continue
            
            # Wait for device to process
            await asyncio.sleep(POST_TOGGLE_DELAY)
            
            # Verify speed changed
            new_speed = await self.async_get_fan_speed()
            _LOGGER.debug("Fan speed after command: %s", new_speed)
            
            if new_speed == target_mode:
                _LOGGER.debug("Successfully set fan speed to %s", target_mode)
                return True
            
            # Speed didn't change as expected, retry
            _LOGGER.warning("Fan speed verification failed, expected %s but got %s", target_mode, new_speed)
            if attempt < max_retries - 1:
                await asyncio.sleep(RETRY_DELAY)
        
        _LOGGER.error("Failed to set fan speed to %s after %d attempts", target_mode, max_retries)
        return False