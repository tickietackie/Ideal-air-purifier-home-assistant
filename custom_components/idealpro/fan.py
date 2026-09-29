"""Ideal Pro Fan Entity for Home Assistant."""
import asyncio
import logging
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)
from .const import DOMAIN, build_device_info

_LOGGER = logging.getLogger(__name__)

# Auto is the only preset. HomeKit maps a single fan preset to its native
# Auto/Manual characteristic instead of creating a separate switch per mode.
PRESET_AUTO = "auto"
PRESET_MODES = [PRESET_AUTO]

# All fixed fan speeds are exposed on the speed slider. The single Auto preset
# remains a separate Auto/Manual control in HomeKit.
SPEED_QUIET = "quiet"
SPEED_1 = "speed_1"
SPEED_2 = "speed_2"
SPEED_3 = "speed_3"
SPEED_TURBO = "turbo"
SPEED_ORDER = [SPEED_QUIET, SPEED_1, SPEED_2, SPEED_3, SPEED_TURBO]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Ideal Pro Fan entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    coordinator = data["coordinator"]
    device_info = build_device_info(api.host)
    async_add_entities([IdealProFan(api, coordinator, device_info)], True)


class IdealProFan(CoordinatorEntity, FanEntity):
    """Representation of the Ideal Pro air purifier fan with preset modes."""

    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_preset_modes = PRESET_MODES
    _attr_speed_count = len(SPEED_ORDER)
    _attr_name = "Ideal Pro Fan"
    _attr_icon = "mdi:fan"

    def __init__(self, api, coordinator, device_info):
        """Initialize the fan."""
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = f"idealpro_{api.host}_fan"
        self._attr_device_info = device_info

    # -------------------------
    # --- STATE PROPERTIES ---
    # -------------------------

    @property
    def is_on(self):
        """Return True if the fan is on, None if unknown."""
        data = self.coordinator.data or {}
        power = data.get("power")
        if power == "off":
            return False
        if power == "on":
            # any active mode: auto or manual
            return True
        # None -> HA renders "unknown" instead of showing off
        return None

    @property
    def preset_mode(self):
        """Return the current preset mode, or None if unknown."""
        data = self.coordinator.data or {}
        mode = data.get("fan_speed")
        return mode if mode in PRESET_MODES else None

    # -------------------------
    # --- SPEED (percentage) ---
    # -------------------------

    @property
    def percentage(self):
        """Return the current fixed-speed position, including live Auto stage."""
        data = self.coordinator.data or {}
        level = data.get("speed_level")
        if isinstance(level, int) and 1 <= level <= len(SPEED_ORDER):
            return ordered_list_item_to_percentage(SPEED_ORDER, SPEED_ORDER[level - 1])
        return None

    @property
    def extra_state_attributes(self):
        """Extra debug attributes."""
        data = self.coordinator.data or {}
        return {
            "fan_speed": data.get("fan_speed"),
            "speed_level": data.get("speed_level"),
            "power": data.get("power"),
        }

    # -------------------------
    # --- CONTROL METHODS -----
    # -------------------------

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs):
        """Turn on the fan, optionally setting a preset or a manual speed."""
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
            return

        if percentage is not None:
            await self.async_set_percentage(percentage)
            return

        # No speed/mode given: just power on, keeping the current mode
        # (device remembers its last fan mode when toggled on).
        _LOGGER.debug("Turning fan on")
        success = await self._api.async_turn_on()
        if success:
            if self.coordinator.data:
                self.coordinator.data["power"] = "on"
            self.async_write_ha_state()

        await asyncio.sleep(0.3)
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int):
        """Select a fixed speed from the five-step percentage scale."""
        if percentage <= 0:
            # HomeKit/HA may send 0 when the speed slider is dragged to the
            # bottom, which means "off" for a fan.
            await self.async_turn_off()
            return
        target = percentage_to_ordered_list_item(SPEED_ORDER, percentage)
        _LOGGER.debug("Fan speed %d%% -> mode %s", percentage, target)
        await self._async_apply_fan_mode(target)

    async def async_turn_off(self, **kwargs):
        """Turn off the fan."""
        _LOGGER.debug("Turning fan off")
        success = await self._api.async_turn_off()
        if success:
            if self.coordinator.data:
                self.coordinator.data["power"] = "off"
                self.coordinator.data["fan_speed"] = "off"
                self.coordinator.data["speed_level"] = 0
            self.async_write_ha_state()

        await asyncio.sleep(0.3)
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str):
        """Set the fan preset mode."""
        if preset_mode not in PRESET_MODES:
            _LOGGER.error("Invalid preset mode: %s", preset_mode)
            return

        _LOGGER.debug("Setting fan preset mode to: %s", preset_mode)
        await self._async_apply_fan_mode(preset_mode)

    async def _async_apply_fan_mode(self, mode: str):
        """Apply and publish a device mode (preset or fixed speed)."""
        success = await self._api.async_set_fan_speed_verified(mode)

        if success:
            _LOGGER.debug("Fan confirmed at mode %s, updating UI", mode)
            if self.coordinator.data:
                # Setting a mode on this device also powers it on; keep the
                # UI state in sync until the next coordinator refresh.
                self.coordinator.data["power"] = "on"
                self.coordinator.data["fan_speed"] = mode
                self.coordinator.data["speed_level"] = (
                    SPEED_ORDER.index(mode) + 1 if mode in SPEED_ORDER else None
                )
            self.async_write_ha_state()
        else:
            _LOGGER.warning("Failed to set fan mode to %s after retries", mode)

        await asyncio.sleep(0.3)
        await self.coordinator.async_request_refresh()
