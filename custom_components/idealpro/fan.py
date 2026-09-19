"""Ideal Pro Fan Entity for Home Assistant."""
import asyncio
import logging
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Preset mode names for HA UI
PRESET_QUIET = "quiet"
PRESET_AUTO = "auto"
PRESET_SPEED_1 = "speed_1"
PRESET_SPEED_2 = "speed_2"
PRESET_SPEED_3 = "speed_3"
PRESET_TURBO = "turbo"

PRESET_MODES = [
    PRESET_QUIET,
    PRESET_AUTO,
    PRESET_SPEED_1,
    PRESET_SPEED_2,
    PRESET_SPEED_3,
    PRESET_TURBO,
]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Ideal Pro Fan entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    coordinator = data["coordinator"]
    async_add_entities([IdealProFan(api, coordinator)], True)


class IdealProFan(CoordinatorEntity, FanEntity):
    """Representation of the Ideal Pro air purifier fan with preset modes."""

    _attr_supported_features = FanEntityFeature.PRESET_MODE | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    _attr_preset_modes = PRESET_MODES
    _attr_name = "Ideal Pro Fan"
    _attr_icon = "mdi:fan"

    def __init__(self, api, coordinator):
        """Initialize the fan."""
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = f"idealpro_{api.host}_fan"

    # -------------------------
    # --- STATE PROPERTIES ---
    # -------------------------

    @property
    def is_on(self):
        """Return True if the fan is on."""
        data = self.coordinator.data or {}
        return data.get("power") == "on"

    @property
    def preset_mode(self):
        """Return the current preset mode, or None if unknown."""
        data = self.coordinator.data or {}
        mode = data.get("fan_speed")
        return mode if mode in PRESET_MODES else None

    @property
    def extra_state_attributes(self):
        """Extra debug attributes."""
        data = self.coordinator.data or {}
        return {
            "fan_speed": data.get("fan_speed"),
            "power": data.get("power"),
        }

    # -------------------------
    # --- CONTROL METHODS -----
    # -------------------------

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs):
        """Turn on the fan. If preset_mode provided, set that mode."""
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
            return
            
        # Just turn on the power
        _LOGGER.debug("Turning fan on")
        success = await self._api.async_turn_on()
        if success:
            if self.coordinator.data:
                self.coordinator.data["power"] = "on"
            self.async_write_ha_state()
            
        await asyncio.sleep(0.3)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn off the fan."""
        _LOGGER.debug("Turning fan off")
        success = await self._api.async_turn_off()
        if success:
            if self.coordinator.data:
                self.coordinator.data["power"] = "off"
            self.async_write_ha_state()
            
        await asyncio.sleep(0.3)
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str):
        """Set the fan preset mode."""
        if preset_mode not in PRESET_MODES:
            _LOGGER.error("Invalid preset mode: %s", preset_mode)
            return

        _LOGGER.debug("Setting fan preset mode to: %s", preset_mode)

        # Use state-aware fan speed control with verification and retries
        success = await self._api.async_set_fan_speed_verified(preset_mode)

        if success:
            _LOGGER.debug("Fan confirmed at mode %s, updating UI", preset_mode)
            if self.coordinator.data:
                self.coordinator.data["fan_speed"] = preset_mode
            self.async_write_ha_state()
        else:
            _LOGGER.warning("Failed to set fan mode to %s after retries", preset_mode)

        await asyncio.sleep(0.3)
        await self.coordinator.async_request_refresh()
