from homeassistant.helpers.device_registry import DeviceInfo

DOMAIN = "idealpro"
DEFAULT_PORT = 8899
PLATFORMS = ["switch", "light", "fan", "sensor"]


def build_device_info(host: str) -> DeviceInfo:
    """Return the shared device info for all entities of one config entry."""
    return DeviceInfo(
        identifiers={(DOMAIN, host)},
        name="Ideal Pro",
        manufacturer="Ideal",
        configuration_url=f"http://{host}",
    )
