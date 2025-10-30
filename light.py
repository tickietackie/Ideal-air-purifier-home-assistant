import asyncio
import logging
from homeassistant.components.light import (
    LightEntity,
    ColorMode,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Ideal Pro LED light entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    coordinator = data["coordinator"]
    async_add_entities([IdealProLight(api, coordinator)], True)


class IdealProLight(LightEntity):
    """Representation of the Ideal Pro LED light with brightness control."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_name = "Ideal Pro LED"
    _attr_icon = "mdi:lightbulb"

    def __init__(self, api, coordinator):
        self._api = api
        self._coordinator = coordinator
        self._attr_unique_id = f"idealpro_{api.host}_led"

    # -------------------------
    # --- STATE PROPERTIES ---
    # -------------------------

    @property
    def is_on(self):
        """Return True if brightness > 0."""
        data = self._coordinator.data or {}
        level = data.get("led_level", 0)
        try:
            level = int(level)
        except (ValueError, TypeError):
            level = 0
        return level > 0

    @property
    def brightness(self):
        """Return the LED brightness in HA's 0–255 range."""
        data = self._coordinator.data or {}
        level = data.get("led_level", 0)
        try:
            level = int(level)
        except (ValueError, TypeError):
            level = 0
        # scale 0–9 -> 0–255
        return int(level * 255 / 9)

    @property
    def extra_state_attributes(self):
        """Extra debug attributes."""
        data = self._coordinator.data or {}
        return {
            "led_level": data.get("led_level"),
            "raw_status": data.get("raw", "")[:100],
        }

    # -------------------------
    # --- CONTROL METHODS -----
    # -------------------------

    async def async_turn_on(self, **kwargs):
        """Turn the LED light on, optionally setting brightness."""
        brightness = kwargs.get("brightness", 255)
        level = max(1, int(round(brightness * 9 / 255)))  # 1–9 range
        _LOGGER.debug("Turning LED ON at level %d", level)

        try:
            await self._api.async_set_brightness(level)
        except Exception as err:
            _LOGGER.error("Error setting LED brightness: %s", err)
            return

        # Optimistic state: update before next poll
        self._coordinator.data["led_level"] = level
        self.async_write_ha_state()

        await asyncio.sleep(0.3)
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the LED light off (set brightness to 0)."""
        _LOGGER.debug("Turning LED OFF")
        try:
            await self._api.async_set_brightness(0)
        except Exception as err:
            _LOGGER.error("Error turning LED off: %s", err)
            return

        # Optimistic state
        self._coordinator.data["led_level"] = 0
        self.async_write_ha_state()

        await asyncio.sleep(0.3)
        await self._coordinator.async_request_refresh()

    async def async_update(self):
        """Ask coordinator to refresh device state."""
        await self._coordinator.async_request_refresh()