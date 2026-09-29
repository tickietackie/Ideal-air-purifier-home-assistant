#!/usr/bin/env python3
"""Offline tests for fan mode and LED brightness control (IdealProAPI).

Key behaviours covered:

- mode commands on a powered-off device power it on first (the device
  ignores S* while off - this is the HomeKit "toggle does nothing" bug),
- picking a mode restores/overrides correctly,
- verification, retries and flaky reads for modes and brightness,
- brightness changes never power the purifier on.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ha_test_utils import DeviceAPI, FakeDevice, run


def test_set_speed_when_on_sends_command():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        api = DeviceAPI.build(dev)
        assert await api.async_set_fan_speed_verified("speed_3") is True
        assert dev.commands == ["S3"]
        assert dev.fan_speed == "speed_3"

    run(scenario())


def test_set_speed_already_at_target_sends_nothing():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="speed_2")
        api = DeviceAPI.build(dev)
        assert await api.async_set_fan_speed_verified("speed_2") is True
        assert dev.commands == []

    run(scenario())


def test_set_speed_when_off_powers_on_first():
    """The device ignores S* while off, so power on first, then set the mode."""
    async def scenario():
        dev = FakeDevice(power="off", last_mode="auto")
        api = DeviceAPI.build(dev)
        assert await api.async_set_fan_speed_verified("speed_3") is True
        assert dev.commands == ["ON", "S3"]
        assert dev.power == "on"
        assert dev.fan_speed == "speed_3"

    run(scenario())


def test_set_speed_when_off_and_restored_mode_already_matches():
    async def scenario():
        dev = FakeDevice(power="off", last_mode="speed_1")
        api = DeviceAPI.build(dev)
        assert await api.async_set_fan_speed_verified("speed_1") is True
        # Power-on already restored speed_1, no extra mode command needed.
        assert dev.commands == ["ON"]
        assert dev.power == "on"
        assert dev.fan_speed == "speed_1"

    run(scenario())


def test_set_speed_unknown_power_does_not_blind_toggle():
    """If power cannot be read, proceed without a risky power toggle."""
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        api = DeviceAPI.build(dev)
        reads = {"n": 0}
        original = dev.status

        def status():
            reads["n"] += 1
            return "" if reads["n"] == 1 else original()

        dev.status = status
        assert await api.async_set_fan_speed_verified("quiet") is True
        assert "ON" not in dev.commands
        assert dev.commands == ["SQ"]

    run(scenario())


def test_set_speed_retries_lost_command():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        seen = {"n": 0}

        def filt(command):
            if command == "S1":
                seen["n"] += 1
                return seen["n"] > 1
            return True

        dev.command_filter = filt
        api = DeviceAPI.build(dev)
        assert await api.async_set_fan_speed_verified("speed_1") is True
        assert dev.commands == ["S1", "S1"]
        assert dev.fan_speed == "speed_1"

    run(scenario())


def test_set_speed_fails_when_device_never_changes():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        dev.ignore_commands.add("S2")
        api = DeviceAPI.build(dev)
        assert await api.async_set_fan_speed_verified("speed_2") is False
        assert dev.commands == ["S2"] * 5

    run(scenario())


def test_set_speed_power_on_failure_returns_false():
    async def scenario():
        dev = FakeDevice(power="off")
        dev.ignore_commands.add("ON")
        api = DeviceAPI.build(dev)
        assert await api.async_set_fan_speed_verified("auto") is False
        assert dev.power == "off"

    run(scenario())


def test_set_brightness_changes_level():
    async def scenario():
        dev = FakeDevice(power="on", led_level=5)
        api = DeviceAPI.build(dev)
        assert await api.async_set_brightness_verified(7) is True
        assert dev.commands == ["D7"]
        assert dev.led_level == 7

    run(scenario())


def test_set_brightness_already_at_target_sends_nothing():
    async def scenario():
        dev = FakeDevice(power="on", led_level=3)
        api = DeviceAPI.build(dev)
        assert await api.async_set_brightness_verified(3) is True
        assert dev.commands == []

    run(scenario())


def test_set_brightness_does_not_power_on_device():
    async def scenario():
        dev = FakeDevice(power="off", led_level=0)
        api = DeviceAPI.build(dev)
        assert await api.async_set_brightness_verified(4) is True
        assert dev.commands == ["D4"]
        assert dev.power == "off"

    run(scenario())


def test_set_brightness_retries_lost_command():
    async def scenario():
        dev = FakeDevice(power="on", led_level=0)
        seen = {"n": 0}

        def filt(command):
            if command == "D9":
                seen["n"] += 1
                return seen["n"] > 1
            return True

        dev.command_filter = filt
        api = DeviceAPI.build(dev)
        assert await api.async_set_brightness_verified(9) is True
        assert dev.commands == ["D9", "D9"]
        assert dev.led_level == 9

    run(scenario())


def test_set_brightness_fails_when_device_never_changes():
    async def scenario():
        dev = FakeDevice(power="on", led_level=2)
        dev.ignore_commands.add("D8")
        api = DeviceAPI.build(dev)
        assert await api.async_set_brightness_verified(8) is False
        assert dev.commands == ["D8"] * 5

    run(scenario())


def test_all_modes_have_commands_and_roundtrip():
    async def scenario():
        api_mod = DeviceAPI.build(FakeDevice())
        expected = {
            "quiet": "SQ",
            "auto": "SA",
            "speed_1": "S1",
            "speed_2": "S2",
            "speed_3": "S3",
            "turbo": "ST",
        }
        assert api_mod.FAN_SPEED_COMMANDS == {
            key: value.encode() for key, value in expected.items()
        }
        for mode in expected:
            dev = FakeDevice(power="on", fan_speed="auto")
            api = DeviceAPI.build(dev)
            assert await api.async_set_fan_speed_verified(mode) is True
            assert dev.fan_speed == mode, mode

    run(scenario())


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} tests passed.")


if __name__ == "__main__":
    main()
