import asyncio
import logging
from homeassistant.components.light import (
    LightEntity,
    ColorMode,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Ideal Pro LED light entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    coordinator = data["coordinator"]
    async_add_entities([IdealProLight(api, coordinator)], True)


class IdealProLight(CoordinatorEntity, LightEntity):
    """Representation of the Ideal Pro LED light with brightness control."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_name = "Ideal Pro LED"
    _attr_icon = "mdi:lightbulb"

    def __init__(self, api, coordinator):
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = f"idealpro_{api.host}_led"

    # -------------------------
    # --- STATE PROPERTIES ---
    # -------------------------

    @property
    def _level(self) -> int:
        """Return the current LED level as an int (0 if unknown)."""
        data = self.coordinator.data or {}
        try:
            return int(data.get("led_level", 0))
        except (ValueError, TypeError):
            return 0

    @property
    def is_on(self):
        """Return True if brightness > 0."""
        return self._level > 0

    @property
    def brightness(self):
        """Return the LED brightness in HA's 0–255 range."""
        # scale 0–9 -> 0–255
        return int(self._level * 255 / 9)

    @property
    def extra_state_attributes(self):
        """Extra debug attributes."""
        data = self.coordinator.data or {}
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

        # Use state-aware brightness control with verification and retries
        success = await self._api.async_set_brightness_verified(level)
        
        if success:
            _LOGGER.debug("LED confirmed at level %d, updating UI", level)
            if self.coordinator.data is not None:
                self.coordinator.data["led_level"] = level
            self.async_write_ha_state()
        else:
            _LOGGER.warning("Failed to set LED brightness to %d after retries", level)

        await asyncio.sleep(0.3)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the LED light off (set brightness to 0)."""
        _LOGGER.debug("Turning LED OFF")
        
        # Use state-aware brightness control with verification and retries
        success = await self._api.async_set_brightness_verified(0)
        
        if success:
            _LOGGER.debug("LED confirmed OFF, updating UI")
            if self.coordinator.data is not None:
                self.coordinator.data["led_level"] = 0
            self.async_write_ha_state()
        else:
            _LOGGER.warning("Failed to turn LED off after retries")

        await asyncio.sleep(0.3)
        await self.coordinator.async_request_refresh()