"""Ideal Pro air quality and diagnostic sensors."""
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, build_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Ideal Pro sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    coordinator = data["coordinator"]
    device_info = build_device_info(api.host)
    async_add_entities(
        [
            IdealProPM25Sensor(api, coordinator, device_info),
            IdealProFanRPMSensor(api, coordinator, device_info),
            IdealProAutoStageSensor(api, coordinator, device_info),
            IdealProBoostSensor(api, coordinator, device_info),
            IdealProOperatingHoursSensor(api, coordinator, device_info),
        ],
        True,
    )


class IdealProPM25Sensor(CoordinatorEntity, SensorEntity):
    """PM2.5 reading from the purifier's built-in particle sensor.

    The device reports field D as PM2.5 in µg/m³ multiplied by 100
    (e.g. D1420 -> 14.20 µg/m³).
    """

    _attr_device_class = SensorDeviceClass.PM25
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "µg/m³"
    _attr_icon = "mdi:blur"
    _attr_name = "Ideal Pro PM2.5"

    def __init__(self, api, coordinator, device_info):
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = f"idealpro_{api.host}_pm25"
        self._attr_device_info = device_info

    @property
    def native_value(self):
        """Return PM2.5 in µg/m³."""
        data = self.coordinator.data or {}
        raw = data.get("D")
        try:
            return round(int(raw) / 100, 2)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self):
        """Expose the still undecoded raw fields for diagnostics."""
        data = self.coordinator.data or {}
        return {
            "gas_sensor_raw": data.get("V"),
            "raw_status": data.get("body"),
        }


class IdealProDiagnosticSensor(CoordinatorEntity, SensorEntity):
    """Base class for diagnostic sensors backed by a raw status token."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _field = ""

    def __init__(self, api, coordinator, device_info):
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = f"idealpro_{api.host}_{self._field.lower()}"
        self._attr_device_info = device_info

    def _raw(self):
        data = self.coordinator.data or {}
        return data.get(self._field)


class IdealProFanRPMSensor(IdealProDiagnosticSensor):
    """Fan motor speed in RPM (device field U)."""

    _field = "U"
    _attr_name = "Ideal Pro Fan RPM"
    _attr_icon = "mdi:fan"
    _attr_native_unit_of_measurement = "rpm"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        try:
            return int(self._raw())
        except (TypeError, ValueError):
            return None


class IdealProAutoStageSensor(IdealProDiagnosticSensor):
    """Stage selected by the automatic mode (device field S)."""

    _field = "S"
    _attr_name = "Ideal Pro Auto Stage"
    _attr_icon = "mdi:auto-mode"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["off", "low", "medium", "high"]

    @property
    def native_value(self):
        try:
            stage = int(self._raw())
        except (TypeError, ValueError):
            return None
        return ("off", "low", "medium", "high")[stage] if 0 <= stage <= 3 else None


class IdealProBoostSensor(IdealProDiagnosticSensor):
    """Remaining auto boost time in seconds (device field O)."""

    _field = "O"
    _attr_name = "Ideal Pro Boost Remaining"
    _attr_icon = "mdi:timer-sand"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "s"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        try:
            return int(self._raw())
        except (TypeError, ValueError):
            return None


class IdealProOperatingHoursSensor(IdealProDiagnosticSensor):
    """Total operating hours counter (device field Z)."""

    _field = "Z"
    _attr_name = "Ideal Pro Operating Hours"
    _attr_icon = "mdi:counter"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "h"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        try:
            return int(self._raw())
        except (TypeError, ValueError):
            return None
