#!/usr/bin/env python3
"""Offline tests for all Home Assistant entities exposed by the integration.

Covers the switch, fan, light and sensor platforms using the Home Assistant
stubs in ha_test_utils (no HA installation or device required).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ha_test_utils import FakeAPI, FakeCoordinator, load_component, run

switch_mod = load_component("switch")
fan_mod = load_component("fan")
light_mod = load_component("light")
sensor_mod = load_component("sensor")


def make(factory, api=None, data=None):
    return factory(api or FakeAPI(), FakeCoordinator(data), {})


# --- switch ---------------------------------------------------------------


def test_switch_is_on_maps_states():
    assert make(switch_mod.IdealProSwitch, data={"power": "on"}).is_on is True
    assert make(switch_mod.IdealProSwitch, data={"power": "off"}).is_on is False
    assert make(switch_mod.IdealProSwitch, data={"power": "unknown"}).is_on is None
    assert make(switch_mod.IdealProSwitch, data={}).is_on is None


def test_switch_turn_on_success_updates_state():
    async def scenario():
        api = FakeAPI()
        coord = FakeCoordinator({"power": "off"})
        entity = switch_mod.IdealProSwitch(api, coord, {})
        await entity.async_turn_on()
        assert api.calls == ["turn_on"]
        assert coord.data["power"] == "on"
        assert coord.refreshes == 1
        assert entity.state_writes >= 1

    run(scenario())


def test_switch_turn_on_failure_keeps_state():
    async def scenario():
        api = FakeAPI()
        api.turn_on_result = False
        coord = FakeCoordinator({"power": "off"})
        entity = switch_mod.IdealProSwitch(api, coord, {})
        await entity.async_turn_on()
        assert coord.data["power"] == "off"
        assert entity.state_writes == 0
        assert coord.refreshes == 1

    run(scenario())


def test_switch_turn_off_success_updates_state():
    async def scenario():
        api = FakeAPI()
        coord = FakeCoordinator({"power": "on"})
        entity = switch_mod.IdealProSwitch(api, coord, {})
        await entity.async_turn_off()
        assert api.calls == ["turn_off"]
        assert coord.data["power"] == "off"
        assert coord.refreshes == 1

    run(scenario())


# --- fan ------------------------------------------------------------------


def test_fan_state_mappings():
    auto = make(
        fan_mod.IdealProFan,
        data={"power": "on", "fan_speed": "auto", "speed_level": 3},
    )
    assert auto.is_on is True
    assert auto.preset_mode == "auto"
    assert auto.percentage == 60

    manual = make(
        fan_mod.IdealProFan,
        data={"power": "on", "fan_speed": "speed_2", "speed_level": 3},
    )
    assert manual.is_on is True
    assert manual.preset_mode is None
    assert manual.percentage == 60

    quiet = make(
        fan_mod.IdealProFan,
        data={"power": "on", "fan_speed": "quiet", "speed_level": 1},
    )
    assert quiet.percentage == 20

    turbo = make(
        fan_mod.IdealProFan,
        data={"power": "on", "fan_speed": "turbo", "speed_level": 5},
    )
    assert turbo.percentage == 100

    off = make(fan_mod.IdealProFan, data={"power": "off", "fan_speed": "off"})
    assert off.is_on is False
    assert off.preset_mode is None
    assert off.percentage is None

    unknown = make(fan_mod.IdealProFan, data={"power": "unknown"})
    assert unknown.is_on is None


def test_fan_percentage_values():
    for mode, level, pct in (
        ("quiet", 1, 20),
        ("speed_1", 2, 40),
        ("speed_2", 3, 60),
        ("speed_3", 4, 80),
        ("turbo", 5, 100),
    ):
        fan = make(
            fan_mod.IdealProFan,
            data={"power": "on", "fan_speed": mode, "speed_level": level},
        )
        assert fan.percentage == pct, mode
    assert make(fan_mod.IdealProFan).percentage_step == 20


def test_fan_set_percentage_maps_to_manual_modes():
    cases = {
        1: "quiet",
        20: "quiet",
        40: "speed_1",
        50: "speed_2",
        60: "speed_2",
        80: "speed_3",
        100: "turbo",
    }
    for pct, mode in cases.items():
        async def scenario(pct=pct, mode=mode):
            api = FakeAPI()
            coord = FakeCoordinator({"power": "off", "fan_speed": "off"})
            fan = fan_mod.IdealProFan(api, coord, {})
            await fan.async_set_percentage(pct)
            assert api.calls == [("set_speed", mode)], (pct, api.calls)
            assert coord.data["power"] == "on"
            assert coord.data["fan_speed"] == mode
            assert coord.data["speed_level"] == fan_mod.SPEED_ORDER.index(mode) + 1

        run(scenario())


def test_fan_set_percentage_zero_turns_off():
    async def scenario():
        api = FakeAPI()
        coord = FakeCoordinator({"power": "on", "fan_speed": "speed_1"})
        fan = fan_mod.IdealProFan(api, coord, {})
        await fan.async_set_percentage(0)
        assert api.calls == ["turn_off"]
        assert coord.data["power"] == "off"

    run(scenario())


def test_fan_turn_on_plain_keeps_mode_via_power_toggle():
    async def scenario():
        api = FakeAPI()
        coord = FakeCoordinator({"power": "off", "fan_speed": "off"})
        fan = fan_mod.IdealProFan(api, coord, {})
        await fan.async_turn_on()
        assert api.calls == ["turn_on"]
        assert coord.data["power"] == "on"

    run(scenario())


def test_fan_turn_on_with_preset_mode():
    async def scenario():
        api = FakeAPI()
        coord = FakeCoordinator({"power": "off", "fan_speed": "off"})
        fan = fan_mod.IdealProFan(api, coord, {})
        await fan.async_turn_on(preset_mode="auto")
        assert api.calls == [("set_speed", "auto")]
        assert coord.data["power"] == "on"
        assert coord.data["fan_speed"] == "auto"

    run(scenario())


def test_fan_turn_on_with_percentage():
    async def scenario():
        api = FakeAPI()
        coord = FakeCoordinator({"power": "off", "fan_speed": "off"})
        fan = fan_mod.IdealProFan(api, coord, {})
        await fan.async_turn_on(percentage=60)
        assert api.calls == [("set_speed", "speed_2")]

    run(scenario())


def test_fan_turn_off():
    async def scenario():
        api = FakeAPI()
        coord = FakeCoordinator({"power": "on", "fan_speed": "auto"})
        fan = fan_mod.IdealProFan(api, coord, {})
        await fan.async_turn_off()
        assert api.calls == ["turn_off"]
        assert coord.data["power"] == "off"
        assert coord.data["fan_speed"] == "off"
        assert coord.data["speed_level"] == 0

    run(scenario())


def test_fan_preset_mode_failure_does_not_update_state():
    async def scenario():
        api = FakeAPI()
        api.set_speed_result = False
        coord = FakeCoordinator({"power": "off", "fan_speed": "off"})
        fan = fan_mod.IdealProFan(api, coord, {})
        await fan.async_set_preset_mode("auto")
        assert coord.data["power"] == "off"
        assert coord.data["fan_speed"] == "off"
        assert fan.state_writes == 0

    run(scenario())


def test_homekit_model_has_auto_manual_and_speed_controls():
    """A single auto preset maps to HomeKit's Auto/Manual characteristic."""
    fan = make(fan_mod.IdealProFan)
    assert fan._attr_preset_modes == ["auto"]
    assert fan._attr_speed_count == 5


def test_auto_percentage_follows_live_stage():
    for level, expected in ((2, 40), (3, 60), (4, 80)):
        fan = make(
            fan_mod.IdealProFan,
            data={"power": "on", "fan_speed": "auto", "speed_level": level},
        )
        assert fan.percentage == expected


# --- light ----------------------------------------------------------------


def test_light_state_and_brightness_mapping():
    on = make(light_mod.IdealProLight, data={"led_level": 9})
    assert on.is_on is True
    assert on.brightness == 255

    mid = make(light_mod.IdealProLight, data={"led_level": 3})
    assert mid.is_on is True
    assert mid.brightness == int(3 * 255 / 9)

    off = make(light_mod.IdealProLight, data={"led_level": 0})
    assert off.is_on is False
    assert off.brightness == 0

    missing = make(light_mod.IdealProLight, data={})
    assert missing.is_on is False

    bad = make(light_mod.IdealProLight, data={"led_level": "nope"})
    assert bad.is_on is False


def test_light_turn_on_default_brightness():
    async def scenario():
        api = FakeAPI()
        coord = FakeCoordinator({"led_level": 0})
        light = light_mod.IdealProLight(api, coord, {})
        await light.async_turn_on()
        assert api.calls == [("set_brightness", 9)]
        assert coord.data["led_level"] == 9
        assert coord.refreshes == 1

    run(scenario())


def test_light_turn_on_custom_brightness():
    async def scenario():
        api = FakeAPI()
        coord = FakeCoordinator({"led_level": 0})
        light = light_mod.IdealProLight(api, coord, {})
        await light.async_turn_on(brightness=100)
        assert api.calls == [("set_brightness", 4)]

    run(scenario())


def test_light_turn_on_minimum_is_level_one():
    async def scenario():
        api = FakeAPI()
        coord = FakeCoordinator({"led_level": 0})
        light = light_mod.IdealProLight(api, coord, {})
        await light.async_turn_on(brightness=1)
        assert api.calls == [("set_brightness", 1)]

    run(scenario())


def test_light_turn_off():
    async def scenario():
        api = FakeAPI()
        coord = FakeCoordinator({"led_level": 5})
        light = light_mod.IdealProLight(api, coord, {})
        await light.async_turn_off()
        assert api.calls == [("set_brightness", 0)]
        assert coord.data["led_level"] == 0

    run(scenario())


def test_light_failure_does_not_update_state():
    async def scenario():
        api = FakeAPI()
        api.set_brightness_result = False
        coord = FakeCoordinator({"led_level": 5})
        light = light_mod.IdealProLight(api, coord, {})
        await light.async_turn_on(brightness=255)
        assert coord.data["led_level"] == 5
        assert light.state_writes == 0

    run(scenario())


# --- sensors ---------------------------------------------------------------


def test_pm25_sensor_value_and_attributes():
    sensor = make(sensor_mod.IdealProPM25Sensor, data={"D": "1424", "V": "0283"})
    assert sensor.native_value == 14.24
    assert sensor.extra_state_attributes["gas_sensor_raw"] == "0283"
    assert make(sensor_mod.IdealProPM25Sensor, data={"D": "junk"}).native_value is None
    assert make(sensor_mod.IdealProPM25Sensor, data={}).native_value is None


def test_fan_rpm_sensor():
    assert make(sensor_mod.IdealProFanRPMSensor, data={"U": "0540"}).native_value == 540
    assert make(sensor_mod.IdealProFanRPMSensor, data={}).native_value is None
    assert make(sensor_mod.IdealProFanRPMSensor, data={"U": "x"}).native_value is None


def test_auto_stage_sensor():
    cases = {0: "off", 1: "low", 2: "medium", 3: "high"}
    for raw, expected in cases.items():
        sensor = make(sensor_mod.IdealProAutoStageSensor, data={"S": str(raw)})
        assert sensor.native_value == expected, raw
    assert make(sensor_mod.IdealProAutoStageSensor, data={"S": "9"}).native_value is None
    assert make(sensor_mod.IdealProAutoStageSensor, data={}).native_value is None


def test_boost_sensor():
    sensor = make(sensor_mod.IdealProBoostSensor, data={"O": "00333"})
    assert sensor.native_value == 333
    assert make(sensor_mod.IdealProBoostSensor, data={}).native_value is None


def test_operating_hours_sensor():
    sensor = make(sensor_mod.IdealProOperatingHoursSensor, data={"Z": "01770"})
    assert sensor.native_value == 1770
    assert make(sensor_mod.IdealProOperatingHoursSensor, data={}).native_value is None


def test_fan_extra_state_attributes():
    fan = make(
        fan_mod.IdealProFan,
        data={"power": "on", "fan_speed": "turbo", "speed_level": 5},
    )
    attrs = fan.extra_state_attributes
    assert attrs["power"] == "on"
    assert attrs["fan_speed"] == "turbo"
    assert attrs["speed_level"] == 5


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} tests passed.")


if __name__ == "__main__":
    main()
