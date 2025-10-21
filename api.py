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
        {A1,FR,C00000,S1,KI,L9,D1410,V0261,R0261,N00000,...}
        Return a dict with at least 'power' plus raw tokens.

        If multiple {...} blocks are present in `raw`, use the last one
        (this covers handshake + toggle returning two blocks).
        """
        _LOGGER.debug("Start parsing status: %r", raw)
        out = {"raw": raw, "power": "unknown"}
        if not raw:
            _LOGGER.error("Rar input is missing, failed to parse current status.",)
            return out

        # prefer the last matched {...} block if there are several
        matches = STATUS_RE.findall(raw)
        if matches:
            body = matches[-1]
        else:
            # maybe raw already is the body without braces
            body = raw.strip("{}")

        tokens = [t.strip() for t in body.split(",") if t.strip()]
        if not tokens:
            return out

        # first token is A1 or A- (power)
        first = tokens[0]
        if first.startswith("A1") or first.startswith("A2"):
            out["power"] = "on"
        elif first.startswith("A-") or first.startswith("A0"):
            out["power"] = "off"
        else:
            out["power"] = "unknown"

        _LOGGER.debug("Parsed status: %s", out["power"])

        # parse remaining tokens into key->value where possible
        for token in tokens[1:]:
            m = re.match(r"([A-Z]+)(.*)", token)
            if m:
                key, val = m.group(1), m.group(2)
                out[key] = val
            else:
                out.setdefault("misc", []).append(token)

        # expose the parsed body for convenience
        out["body"] = body
        return out