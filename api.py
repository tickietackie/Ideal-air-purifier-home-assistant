import asyncio
import logging
import re
from typing import Dict, Optional

_LOGGER = logging.getLogger(__name__)

STATUS_RE = re.compile(r"\{(.+?)\}")

class IdealProAPI:
    def __init__(self, host: str, port: int = 8899):
        self.host = host
        self.port = port

    async def _open(self):
        return await asyncio.open_connection(self.host, self.port)

    async def async_handshake_and_read(self, timeout: float = 2.0) -> Optional[str]:
        """Connect, send GD handshake and read the status block (if any)."""
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
        except Exception as err:
            _LOGGER.debug("connect error: %s", err)
            raise

        try:
            writer.write(b"GD")
            await writer.drain()
            # small pause to let the device send its data
            await asyncio.sleep(0.3)
            try:
                data = await asyncio.wait_for(reader.read(1024), timeout=timeout)
            except asyncio.TimeoutError:
                data = b""
            text = data.decode(errors="ignore").strip() if data else ""
            return text
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def async_toggle(self):
        """
        Send the toggle command (device uses 'ON' as toggle).
        We still send the handshake first for reliability.
        """
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
        except Exception as err:
            _LOGGER.debug("connect error for toggle: %s", err)
            raise

        try:
            writer.write(b"GD")
            await writer.drain()
            await asyncio.sleep(0.2)
            writer.write(b"ON")
            await writer.drain()
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def parse_status(self, raw: str) -> Dict:
        """
        Parse a status string like:
        {A1,FR,C00000,S1,KI,L9,D1410,V0261,R0261,N00000,...,HD4N1,...}

        Returns:
            {
              "raw": "...",         # original text
              "power": "on"/"off"/"unknown",
              "led_level": int(0–9), # brightness parsed from HDx...
              "body": "...",         # most recent {...} block
              ... other parsed tokens ...
            }
        """

        _LOGGER.debug("Start parsing status: %r", raw)
        out: Dict[str, any] = {"raw": raw, "power": "unknown"}

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

        # Determine power
        first = tokens[0]
        if first.startswith(("A1", "A2")):
            out["power"] = "on"
        elif first.startswith(("A-", "A0")):
            out["power"] = "off"
        else:
            out["power"] = "unknown"
        _LOGGER.debug("Parsed power=%s", out["power"])

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

        out["body"] = body
        return out

    
    async def async_set_brightness(self, level: int):
        """
        Set LED brightness level (0–9).
        The device expects the command in the form 'D0'...'D9'.
        """
        if not 0 <= level <= 9:
            raise ValueError(f"Brightness level must be 0–9, got {level}")

        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
        except Exception as err:
            _LOGGER.debug("connect error for brightness: %s", err)
            raise

        try:
            writer.write(b"GD")
            await writer.drain()
            await asyncio.sleep(0.2)
            cmd = f"D{level}".encode()
            _LOGGER.debug("Sending brightness command: %s", cmd)
            writer.write(cmd)
            await writer.drain()
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass