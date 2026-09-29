import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IdealProAPI
from .const import DOMAIN, DEFAULT_PORT, PLATFORMS

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host = entry.data[CONF_HOST]
    api = IdealProAPI(host, port=DEFAULT_PORT)

    async def async_update():
        try:
            raw = await api.async_handshake_and_read()
            status = api.parse_status(raw or "")
            # An unreadable status must never overwrite the last known state:
            # it would flip the switch to "off" until the next good poll.
            if status.get("power") == "unknown":
                raise UpdateFailed(f"unreadable status: {raw!r}"
                )
            return status
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(err)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN} coordinator {host}",
        update_method=async_update,
        update_interval=timedelta(seconds=30),
    )

    # first refresh
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
