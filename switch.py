from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import callback
import asyncio
import logging
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)   

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    coordinator = data["coordinator"]
    async_add_entities([IdealProSwitch(api, coordinator)], True)

class IdealProSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, api, coordinator):
        super().__init__(coordinator)
        self._api = api
        self._attr_name = "Ideal Pro"
        self._attr_unique_id = f"idealpro_{api.host}"

    @property
    def is_on(self):
        data = self.coordinator.data or {}
        return data.get("power") == "on"

    async def async_turn_on(self, **kwargs):
        _LOGGER.debug("Starting turning on device...")
        
        # Use state-aware turn_on with verification and retries
        success = await self._api.async_turn_on()
        
        if success:
            _LOGGER.debug("Device confirmed ON, updating UI")
            if self.coordinator.data:
                self.coordinator.data["power"] = "on"
            self.async_write_ha_state()
        else:
            _LOGGER.warning("Failed to turn on device after retries")
        
        # Request a coordinator refresh to sync state
        await asyncio.sleep(0.3)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        _LOGGER.debug("Starting turning off device...")
        
        # Use state-aware turn_off with verification and retries
        success = await self._api.async_turn_off()
        
        if success:
            _LOGGER.debug("Device confirmed OFF, updating UI")
            if self.coordinator.data:
                self.coordinator.data["power"] = "off"
            self.async_write_ha_state()
        else:
            _LOGGER.warning("Failed to turn off device after retries")
        
        # Request a coordinator refresh to sync state
        await asyncio.sleep(0.3)
        await self.coordinator.async_request_refresh()
