from homeassistant.components.switch import SwitchEntity
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

class IdealProSwitch(SwitchEntity):
    def __init__(self, api, coordinator):
        self._api = api
        self._coordinator = coordinator
        self._attr_name = "Ideal Pro"
        self._attr_unique_id = f"idealpro_{api.host}"

    @property
    def is_on(self):
        data = self._coordinator.data or {}
        return data.get("power") == "on"

    async def async_turn_on(self, **kwargs):
        _LOGGER.debug("Starting turning on device...")
        await self._api.async_toggle()

        # Optimistically assume ON, show immediately in UI
        _LOGGER.debug("Optimistically updating UI to on")
        self._coordinator.data["power"] = "on"
        self.async_write_ha_state()

        await asyncio.sleep(0.3)
        # request a coordinator refresh so UI updates from real state
        _LOGGER.debug("Requesting coordinator refresh so UI updates from real state")
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        # device uses ON as toggle, so we also call toggle (same command)
        _LOGGER.debug("Starting turning off device...")
        await self._api.async_toggle()
        
        # Optimistically assume OFF, show immediately in UI
        _LOGGER.debug("Optimistically updating UI to off")
        self._coordinator.data["power"] = "off"
        self.async_write_ha_state()

        await asyncio.sleep(0.3)
        # request a coordinator refresh so UI updates from real state
        _LOGGER.debug("Requesting coordinator refresh so UI updates from real state")
        await self._coordinator.async_request_refresh()

    async def async_update(self):
        # coordinator handles regular updates; this is optional
        await self._coordinator.async_request_refresh()
