#!/usr/bin/env python3
"""Offline tests for the power state machine in IdealProAPI.

These tests use a simulated device (see ha_test_utils) so they run without
network access. They focus on the behaviours that made the HomeKit switch
misbehave:

- never report success from a stale/unreadable state,
- never send two blind toggles in a row (each ON command toggles power),
- restore the last mode after power cycling.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ha_test_utils import DeviceAPI, FakeDevice, run


def test_turn_on_from_off_sends_single_toggle():
    async def scenario():
        dev = FakeDevice(power="off")
        api = DeviceAPI.build(dev)
        assert await api.async_turn_on() is True
        assert dev.power == "on"
        assert dev.commands == ["ON"]

    run(scenario())


def test_turn_on_when_already_on_sends_nothing():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        api = DeviceAPI.build(dev)
        assert await api.async_turn_on() is True
        assert dev.commands == []

    run(scenario())


def test_turn_off_when_already_off_sends_nothing():
    async def scenario():
        dev = FakeDevice(power="off")
        api = DeviceAPI.build(dev)
        assert await api.async_turn_off() is True
        assert dev.commands == []

    run(scenario())


def test_turn_off_sends_single_toggle():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="speed_2")
        api = DeviceAPI.build(dev)
        assert await api.async_turn_off() is True
        assert dev.power == "off"
        assert dev.commands == ["ON"]

    run(scenario())


def test_turn_on_restores_last_mode():
    """Power-on must bring back the mode that was active before power-off."""
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="speed_2")
        api = DeviceAPI.build(dev)
        assert await api.async_turn_off() is True
        assert dev.power == "off"
        assert dev.last_mode == "speed_2"

        assert await api.async_turn_on() is True
        assert dev.power == "on"
        assert dev.fan_speed == "speed_2"

    run(scenario())


def test_turn_on_restores_auto_mode():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        api = DeviceAPI.build(dev)
        await api.async_turn_off()
        await api.async_turn_on()
        assert dev.fan_speed == "auto"

    run(scenario())


def test_turn_on_unknown_state_sends_single_toggle():
    async def scenario():
        dev = FakeDevice(power="off")
        dev.respond = False
        api = DeviceAPI.build(dev)
        assert await api.async_turn_on() is True
        assert dev.commands == ["ON"]
        assert dev.power == "on"

    run(scenario())


def test_turn_on_unreadable_verify_trusts_single_toggle():
    """A flaky verify read must not cause a second toggle (which would power off)."""
    async def scenario():
        dev = FakeDevice(power="off")
        api = DeviceAPI.build(dev)
        reads = {"n": 0}
        original = dev.status

        def status():
            reads["n"] += 1
            # First read is the pre-check; everything after is unreadable.
            return original() if reads["n"] == 1 else ""

        dev.status = status
        assert await api.async_turn_on() is True
        assert dev.commands == ["ON"]
        assert dev.power == "on"

    run(scenario())


def test_turn_off_unreadable_verify_trusts_single_toggle():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        api = DeviceAPI.build(dev)
        reads = {"n": 0}
        original = dev.status

        def status():
            reads["n"] += 1
            return original() if reads["n"] == 1 else ""

        dev.status = status
        assert await api.async_turn_off() is True
        assert dev.commands == ["ON"]
        assert dev.power == "off"

    run(scenario())


def test_turn_on_never_sends_two_blind_toggles():
    """While the state is unreadable the API must toggle at most once."""
    async def scenario():
        dev = FakeDevice(power="off")
        dev.respond = False
        api = DeviceAPI.build(dev)
        await api.async_turn_on()
        assert dev.commands == ["ON"]

        dev2 = FakeDevice(power="on")
        dev2.respond = False
        api2 = DeviceAPI.build(dev2)
        await api2.async_turn_off()
        assert dev2.commands == ["ON"]

    run(scenario())


def test_turn_on_retries_when_command_is_lost():
    """If the device verifiably stays off the command is retried."""
    async def scenario():
        dev = FakeDevice(power="off")
        dev.ignore_commands.add("ON")
        api = DeviceAPI.build(dev)
        assert await api.async_turn_on() is False
        assert dev.commands == ["ON"] * 5
        assert dev.power == "off"

    run(scenario())


def test_turn_off_retries_when_command_is_lost():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        dev.ignore_commands.add("ON")
        api = DeviceAPI.build(dev)
        assert await api.async_turn_off() is False
        assert dev.commands == ["ON"] * 5
        assert dev.power == "on"

    run(scenario())


def test_turn_on_recovers_after_flaky_first_toggle():
    """First toggle lost, second applied: overall success with two toggles."""
    async def scenario():
        dev = FakeDevice(power="off")
        seen = {"n": 0}

        def filt(command):
            if command == "ON":
                seen["n"] += 1
                return seen["n"] > 1
            return True

        dev.command_filter = filt
        api = DeviceAPI.build(dev)
        assert await api.async_turn_on() is True
        assert dev.commands == ["ON", "ON"]
        assert dev.power == "on"

    run(scenario())


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} tests passed.")


if __name__ == "__main__":
    main()
