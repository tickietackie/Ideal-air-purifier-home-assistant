"""Shared helpers for the offline test-suite.

Provides:
- minimal Home Assistant stubs so the entity modules can be imported
  without a full HA installation,
- a component loader that imports the integration modules as a package,
- a simulated Ideal Pro device (status + command semantics) and an API
  subclass that talks to it instead of the network,
- instant ``asyncio.sleep`` so verification/back-off logic runs fast.
"""

import asyncio
import enum
import importlib
import logging
import math
import os
import sys
import types

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPONENT_DIR = os.path.join(REPO_ROOT, "custom_components", "idealpro")

# Keep test output readable; the API is intentionally chatty about retries.
logging.disable(logging.CRITICAL)

# --- speed up all retry/back-off delays ---------------------------------
_real_sleep = asyncio.sleep


async def _fast_sleep(delay, *args, **kwargs):
    """Make API/entity delays instant in tests."""
    await _real_sleep(0)


asyncio.sleep = _fast_sleep


def run(coro):
    """Run an async scenario in its own event loop."""
    return asyncio.run(coro)


# --- Home Assistant stubs -------------------------------------------------


class _Entity:
    _attr_name = None
    _attr_unique_id = None
    _attr_icon = None
    _attr_device_info = None
    _attr_entity_category = None
    _attr_supported_features = 0
    _attr_preset_modes = None
    _attr_speed_count = 100
    _attr_supported_color_modes = set()
    _attr_color_mode = None
    _attr_native_unit_of_measurement = None
    _attr_device_class = None
    _attr_state_class = None
    _attr_options = None

    def __init__(self):
        self.state_writes = 0

    def async_write_ha_state(self):
        self.state_writes += 1

    async def async_added_to_hass(self):
        return None


class _ToggleEntity(_Entity):
    @property
    def is_on(self):
        return None


class _SwitchEntity(_ToggleEntity):
    pass


class _FanEntity(_ToggleEntity):
    _attr_percentage = 0
    _attr_preset_mode = None

    @property
    def percentage_step(self):
        return 100 / self._attr_speed_count

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs):
        raise NotImplementedError

    async def async_turn_off(self, **kwargs):
        raise NotImplementedError

    async def async_set_percentage(self, percentage):
        raise NotImplementedError

    async def async_set_preset_mode(self, preset_mode):
        raise NotImplementedError


class _LightEntity(_ToggleEntity):
    pass


class _SensorEntity(_Entity):
    @property
    def native_value(self):
        return None


class _CoordinatorEntity(_Entity):
    def __init__(self, coordinator):
        super().__init__()
        self.coordinator = coordinator

    @property
    def available(self):
        return True


class _DeviceInfo(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class _FanEntityFeature(enum.IntFlag):
    PRESET_MODE = 1
    SET_SPEED = 2
    OSCILLATE = 4
    DIRECTION = 8
    TURN_ON = 16
    TURN_OFF = 32


class _ColorMode:
    ONOFF = "onoff"
    BRIGHTNESS = "brightness"


class _SensorDeviceClass:
    PM25 = "pm25"
    ENUM = "enum"
    DURATION = "duration"


class _SensorStateClass:
    MEASUREMENT = "measurement"
    TOTAL_INCREASING = "total_increasing"


class _EntityCategory:
    CONFIG = "config"
    DIAGNOSTIC = "diagnostic"


def _callback(func):
    return func


def _stub_module(name):
    mod = types.ModuleType(name)
    mod.__path__ = []
    sys.modules[name] = mod
    parent, _, child = name.rpartition(".")
    if parent and parent in sys.modules:
        setattr(sys.modules[parent], child, mod)
    return mod


def ordered_list_item_to_percentage(ordered_list, item):
    """Mirror of homeassistant.util.percentage."""
    if item not in ordered_list:
        raise ValueError(f'The item "{item}" is not in "{ordered_list}"')
    return 100 * (ordered_list.index(item) + 1) // len(ordered_list)


def percentage_to_ordered_list_item(ordered_list, percentage):
    """Mirror of homeassistant.util.percentage."""
    if percentage <= 0:
        raise ValueError("Percentage must be greater than 0")
    index = max(
        1, min(len(ordered_list), math.ceil(percentage / (100 / len(ordered_list))))
    )
    return ordered_list[index - 1]


def _install_ha_stubs():
    """Install minimal homeassistant modules if the real package is absent."""
    try:
        import homeassistant  # noqa: F401
        return False
    except ImportError:
        pass

    _stub_module("homeassistant")
    const = _stub_module("homeassistant.const")
    core = _stub_module("homeassistant.core")
    _stub_module("homeassistant.helpers")
    _stub_module("homeassistant.util")
    _stub_module("homeassistant.components")

    updater = _stub_module("homeassistant.helpers.update_coordinator")
    updater.CoordinatorEntity = _CoordinatorEntity
    updater.DataUpdateCoordinator = object
    updater.UpdateFailed = Exception

    device_registry = _stub_module("homeassistant.helpers.device_registry")
    device_registry.DeviceInfo = _DeviceInfo

    percentage = _stub_module("homeassistant.util.percentage")
    percentage.ordered_list_item_to_percentage = ordered_list_item_to_percentage
    percentage.percentage_to_ordered_list_item = percentage_to_ordered_list_item

    switch = _stub_module("homeassistant.components.switch")
    switch.SwitchEntity = _SwitchEntity

    fan = _stub_module("homeassistant.components.fan")
    fan.FanEntity = _FanEntity
    fan.FanEntityFeature = _FanEntityFeature

    light = _stub_module("homeassistant.components.light")
    light.LightEntity = _LightEntity
    light.ColorMode = _ColorMode

    sensor = _stub_module("homeassistant.components.sensor")
    sensor.SensorEntity = _SensorEntity
    sensor.SensorDeviceClass = _SensorDeviceClass
    sensor.SensorStateClass = _SensorStateClass

    const.EntityCategory = _EntityCategory
    core.callback = _callback
    return True


def load_component(name):
    """Import an integration module as ``idealpro.<name>``."""
    _install_ha_stubs()
    if "idealpro" not in sys.modules:
        pkg = types.ModuleType("idealpro")
        pkg.__path__ = [COMPONENT_DIR]
        sys.modules["idealpro"] = pkg
    return importlib.import_module(f"idealpro.{name}")


# --- simulated device ------------------------------------------------------


class FakeDevice:
    """Behavioural model of the Ideal Pro device backed by captures.

    Command semantics:
    - ``ON`` toggles power; when switching off the current mode is
      remembered and restored on the next power-on,
    - ``S*`` mode commands are ignored while the device is off,
    - ``D*`` LED commands always apply.
    """

    COMMAND_TO_MODE = {
        "SQ": "quiet",
        "SA": "auto",
        "S1": "speed_1",
        "S2": "speed_2",
        "S3": "speed_3",
        "ST": "turbo",
    }
    MODE_TO_FIRST = {
        "quiet": "MQ",
        "auto": "A1",
        "speed_1": "M1",
        "speed_2": "M2",
        "speed_3": "M3",
        "turbo": "MT",
    }

    def __init__(self, power="off", fan_speed=None, led_level=0, last_mode=None):
        self.power = power
        self.fan_speed = fan_speed or ("off" if power == "off" else "auto")
        self.led_level = led_level
        self.last_mode = last_mode or ("auto" if power == "off" else self.fan_speed)
        self.commands = []
        self.respond = True
        self.ignore_commands = set()
        self.command_filter = None

    def status(self):
        if not self.respond:
            return ""
        if self.power == "off":
            first = "A-"
        else:
            first = self.MODE_TO_FIRST[self.fan_speed]
        return (
            f"{{{first},FO,C00000,S1,KI,L9,D1424,V0283,R0281,N00000,O00000,"
            f"Y0673,Z01770,P094,W01,HD{self.led_level}N1,I0275,J0000,U0540,"
            f"T40,X006}}"
        )

    def execute(self, command):
        self.commands.append(command)
        if command in self.ignore_commands:
            return
        if self.command_filter is not None and not self.command_filter(command):
            return

        if command == "ON":
            if self.power == "off":
                self.power = "on"
                self.fan_speed = self.last_mode
            else:
                self.power = "off"
                self.last_mode = self.fan_speed
                self.fan_speed = "off"
        elif command in self.COMMAND_TO_MODE:
            if self.power == "on":
                self.fan_speed = self.COMMAND_TO_MODE[command]
                self.last_mode = self.fan_speed
        elif len(command) == 2 and command[0] == "D" and command[1].isdigit():
            self.led_level = int(command[1])


class DeviceAPI:
    """IdealProAPI wired to a FakeDevice instead of TCP."""

    @staticmethod
    def build(device):
        api_mod = load_component("api")

        class _DeviceAPI(api_mod.IdealProAPI):
            def __init__(self):
                super().__init__("fake-device")
                self.device = device

            async def _handshake_and_read(self, timeout=2.0):
                return self.device.status()

            async def _execute(self, command):
                self.device.execute(command.decode())

        return _DeviceAPI()


# --- fakes for entity tests ------------------------------------------------


class FakeCoordinator:
    def __init__(self, data=None):
        self.data = {} if data is None else data
        self.refreshes = 0

    async def async_request_refresh(self):
        self.refreshes += 1


class FakeAPI:
    """Records calls for entity-level tests."""

    def __init__(self, host="test-device"):
        self.host = host
        self.calls = []
        self.turn_on_result = True
        self.turn_off_result = True
        self.set_speed_result = True
        self.set_brightness_result = True

    async def async_turn_on(self):
        self.calls.append("turn_on")
        return self.turn_on_result

    async def async_turn_off(self):
        self.calls.append("turn_off")
        return self.turn_off_result

    async def async_set_fan_speed_verified(self, mode):
        self.calls.append(("set_speed", mode))
        return self.set_speed_result

    async def async_set_brightness_verified(self, level):
        self.calls.append(("set_brightness", level))
        return self.set_brightness_result
