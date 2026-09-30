#!/usr/bin/env python3
"""Offline tests for rapid / concurrent command handling.

Home Assistant fires service calls concurrently (slider drags, HomeKit
bursts, automations). The device is a single TCP endpoint that handles one
request at a time, so the API must:

- serialize every device interaction (sessions never interleave),
- never leave a command behind: the last requested state always wins,
- coalesce a burst per control channel (power / speed / brightness) so the
  device receives the final target instead of every intermediate step,
- never flip-flop the power toggle while a burst is in flight,
- keep working when a command arrives while another is mid-flight.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ha_test_utils import (
    DeviceAPI,
    FakeCoordinator,
    FakeDevice,
    load_component,
    run,
)

fan_mod = load_component("fan")
light_mod = load_component("light")
switch_mod = load_component("switch")

TIMEOUT = 30


def _burst_timeout():
    return TIMEOUT


# --- API level --------------------------------------------------------------


def test_rapid_mode_burst_sends_only_last_command():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="speed_2")
        dev.delay = 0.01
        api = DeviceAPI.build(dev)

        modes = ["quiet", "speed_1", "speed_2", "speed_3", "turbo", "auto"]
        results = await asyncio.wait_for(
            asyncio.gather(*(api.async_set_fan_speed_verified(m) for m in modes)),
            timeout=_burst_timeout(),
        )

        assert results == [True] * len(modes), results
        assert dev.fan_speed == "auto", dev.commands
        # Only the newest command may reach the device.
        assert dev.commands == ["SA"], dev.commands
        assert api.max_active_calls == 1

    run(scenario())


def test_rapid_mode_burst_ending_at_current_speed_sends_nothing():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        dev.delay = 0.01
        api = DeviceAPI.build(dev)

        modes = ["quiet", "speed_1", "auto"]
        results = await asyncio.wait_for(
            asyncio.gather(*(api.async_set_fan_speed_verified(m) for m in modes)),
            timeout=_burst_timeout(),
        )

        assert results == [True] * len(modes), results
        assert dev.fan_speed == "auto"
        assert dev.commands == [], dev.commands

    run(scenario())


def test_rapid_mode_burst_from_off_powers_on_once():
    async def scenario():
        dev = FakeDevice(power="off", last_mode="auto")
        dev.delay = 0.01
        api = DeviceAPI.build(dev)

        modes = ["quiet", "speed_1", "speed_3", "turbo"]
        results = await asyncio.wait_for(
            asyncio.gather(*(api.async_set_fan_speed_verified(m) for m in modes)),
            timeout=_burst_timeout(),
        )

        assert results == [True] * len(modes), results
        assert dev.power == "on"
        assert dev.fan_speed == "turbo"
        # One power-on, one mode command - no intermediate speeds.
        assert dev.commands == ["ON", "ST"], dev.commands

    run(scenario())


def test_rapid_power_burst_when_already_on_sends_nothing():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        dev.delay = 0.01
        api = DeviceAPI.build(dev)

        results = await asyncio.wait_for(
            asyncio.gather(
                api.async_turn_on(),
                api.async_turn_off(),
                api.async_turn_on(),
                api.async_turn_off(),
                api.async_turn_on(),
            ),
            timeout=_burst_timeout(),
        )

        assert results == [True] * 5, results
        assert dev.power == "on"
        # The last intent was "on" and the device already was on.
        assert dev.commands == [], dev.commands
        assert api.max_active_calls == 1

    run(scenario())


def test_rapid_power_burst_ends_off_with_single_toggle():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        dev.delay = 0.01
        api = DeviceAPI.build(dev)

        await asyncio.wait_for(
            asyncio.gather(
                api.async_turn_off(),
                api.async_turn_on(),
                api.async_turn_off(),
            ),
            timeout=_burst_timeout(),
        )

        assert dev.power == "off"
        # A burst must not bounce the device on/off: exactly one toggle.
        assert dev.commands == ["ON"], dev.commands

    run(scenario())


def test_rapid_power_burst_from_off_ends_on_with_single_toggle():
    async def scenario():
        dev = FakeDevice(power="off")
        dev.delay = 0.01
        api = DeviceAPI.build(dev)

        await asyncio.wait_for(
            asyncio.gather(
                api.async_turn_on(),
                api.async_turn_off(),
                api.async_turn_on(),
            ),
            timeout=_burst_timeout(),
        )

        assert dev.power == "on"
        assert dev.commands == ["ON"], dev.commands

    run(scenario())


def test_rapid_power_burst_while_unreadable_toggles_once():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        dev.respond = False
        dev.delay = 0.01
        api = DeviceAPI.build(dev)

        await asyncio.wait_for(
            asyncio.gather(
                api.async_turn_off(),
                api.async_turn_on(),
                api.async_turn_off(),
                api.async_turn_on(),
            ),
            timeout=_burst_timeout(),
        )

        # State is unreadable: each queued command would toggle blindly if it
        # ran, flipping the device back and forth. Only the last one may run.
        assert dev.commands == ["ON"], dev.commands

    run(scenario())


def test_rapid_brightness_burst_sends_only_last_level():
    async def scenario():
        dev = FakeDevice(power="on", led_level=0)
        dev.delay = 0.01
        api = DeviceAPI.build(dev)

        levels = [1, 3, 5, 7, 9]
        results = await asyncio.wait_for(
            asyncio.gather(*(api.async_set_brightness_verified(l) for l in levels)),
            timeout=_burst_timeout(),
        )

        assert results == [True] * len(levels), results
        assert dev.led_level == 9
        assert dev.commands == ["D9"], dev.commands
        assert dev.power == "on"
        assert api.max_active_calls == 1

    run(scenario())


def test_mixed_channel_burst_converges_to_last_state():
    async def scenario():
        dev = FakeDevice(power="off", last_mode="auto")
        dev.delay = 0.01
        api = DeviceAPI.build(dev)

        results = await asyncio.wait_for(
            asyncio.gather(
                api.async_set_fan_speed_verified("turbo"),
                api.async_set_brightness_verified(7),
                api.async_turn_on(),
                api.async_set_fan_speed_verified("auto"),
            ),
            timeout=_burst_timeout(),
        )

        assert results == [True] * 4, results
        assert dev.power == "on"
        assert dev.fan_speed == "auto"
        assert dev.led_level == 7
        # The power command turns it on; brightness is the only LED write.
        assert sorted(dev.commands) == ["D7", "ON"], dev.commands
        assert api.max_active_calls == 1

    run(scenario())


def test_command_arriving_mid_flight_is_not_dropped():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        dev.delay = 0.01
        dev.status_event = asyncio.Event()
        api = DeviceAPI.build(dev)

        first = asyncio.create_task(api.async_set_fan_speed_verified("quiet"))
        # Wait until the first command is inside its initial status read.
        await asyncio.wait_for(dev.status_event.wait(), timeout=_burst_timeout())
        second = asyncio.create_task(api.async_set_fan_speed_verified("speed_1"))

        results = await asyncio.wait_for(
            asyncio.gather(first, second), timeout=_burst_timeout()
        )
        assert results == [True, True], results
        # The mid-flight command still reaches the device...
        assert dev.commands[0] == "SQ", dev.commands
        # ...and the later command always wins.
        assert dev.commands[-1] == "S1", dev.commands
        assert dev.fan_speed == "speed_1"

    run(scenario())


def test_burst_during_in_flight_command_collapses_to_last():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        dev.delay = 0.01
        dev.status_event = asyncio.Event()
        api = DeviceAPI.build(dev)

        first = asyncio.create_task(api.async_set_fan_speed_verified("quiet"))
        await asyncio.wait_for(dev.status_event.wait(), timeout=_burst_timeout())

        follow_ups = [
            asyncio.create_task(api.async_set_fan_speed_verified(m))
            for m in ("speed_1", "speed_2", "speed_3", "turbo")
        ]
        results = await asyncio.wait_for(
            asyncio.gather(first, *follow_ups), timeout=_burst_timeout()
        )

        assert results == [True] * 5, results
        assert dev.fan_speed == "turbo"
        # The in-flight command was already sent; the burst collapses to one.
        assert dev.commands == ["SQ", "ST"], dev.commands

    run(scenario())


def test_lost_burst_command_is_retried_and_superseded_command_is_not_sent():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="speed_2")
        dev.delay = 0.01
        seen = {"n": 0}

        def filt(command):
            if command == "SA":
                seen["n"] += 1
                return seen["n"] > 1
            return True

        dev.command_filter = filt
        api = DeviceAPI.build(dev)

        results = await asyncio.wait_for(
            asyncio.gather(
                api.async_set_fan_speed_verified("speed_1"),
                api.async_set_fan_speed_verified("auto"),
            ),
            timeout=_burst_timeout(),
        )

        assert results == [True, True], results
        assert dev.fan_speed == "auto"
        # speed_1 was superseded before it was ever sent; the dropped SA was
        # retried until it stuck.
        assert "S1" not in dev.commands, dev.commands
        assert dev.commands == ["SA", "SA"], dev.commands

    run(scenario())


def test_flaky_reads_during_burst_never_toggle_power():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="speed_2")
        dev.delay = 0.01
        reads = {"n": 0}
        original = dev.status

        def status():
            reads["n"] += 1
            return "" if reads["n"] % 3 == 0 else original()

        dev.status = status
        api = DeviceAPI.build(dev)

        results = await asyncio.wait_for(
            asyncio.gather(
                api.async_set_fan_speed_verified("speed_1"),
                api.async_set_fan_speed_verified("speed_3"),
                api.async_set_fan_speed_verified("turbo"),
            ),
            timeout=_burst_timeout(),
        )

        assert results == [True] * 3, results
        assert dev.fan_speed == "turbo"
        # Unreadable status must not produce a power toggle.
        assert "ON" not in dev.commands, dev.commands

    run(scenario())


def test_reads_during_burst_never_overlap_with_writes():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="speed_2")
        dev.delay = 0.005
        api = DeviceAPI.build(dev)

        calls = []
        for i in range(10):
            calls.append(api.async_set_fan_speed_verified(["quiet", "speed_1", "speed_3"][i % 3]))
            calls.append(api.async_set_brightness_verified(i % 10))
            calls.append(api.async_turn_on() if i % 2 else api.async_turn_off())
            calls.append(api.async_get_power_state())
            calls.append(api.async_handshake_and_read())

        results = await asyncio.wait_for(
            asyncio.gather(*calls, return_exceptions=True),
            timeout=_burst_timeout(),
        )

        assert not any(isinstance(r, Exception) for r in results), results
        assert api.max_active_calls == 1
        # Last queued intent per channel wins.
        assert dev.power == "on"  # last of the alternating power calls
        assert dev.led_level == 9

    run(scenario())


def test_stress_burst_completes_without_deadlock():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        dev.delay = 0.001
        api = DeviceAPI.build(dev)

        calls = []
        for i in range(30):
            calls.append(api.async_set_fan_speed_verified(["quiet", "auto", "turbo"][i % 3]))
            calls.append(api.async_turn_on())
            calls.append(api.async_set_brightness_verified(i % 10))

        results = await asyncio.wait_for(
            asyncio.gather(*calls, return_exceptions=True),
            timeout=_burst_timeout(),
        )

        assert not any(isinstance(r, Exception) for r in results), results
        assert all(r is True for r in results), results
        assert api.max_active_calls == 1

    run(scenario())


# --- entity level -----------------------------------------------------------


def test_entity_percentage_drag_sends_only_final_speed():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        dev.delay = 0.01
        api = DeviceAPI.build(dev)
        coord = FakeCoordinator({"power": "on", "fan_speed": "auto", "speed_level": 3})
        fan = fan_mod.IdealProFan(api, coord, {})

        results = await asyncio.wait_for(
            asyncio.gather(
                *(fan.async_set_percentage(p) for p in (20, 40, 60, 80, 100))
            ),
            timeout=_burst_timeout(),
        )

        assert results == [None] * 5, results
        assert dev.fan_speed == "turbo"
        assert dev.commands == ["ST"], dev.commands
        assert coord.data["fan_speed"] == "turbo"
        assert coord.data["speed_level"] == 5
        assert coord.data["power"] == "on"

    run(scenario())


def test_entity_switch_burst_toggles_device_once():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        dev.delay = 0.01
        api = DeviceAPI.build(dev)
        coord = FakeCoordinator({"power": "on"})
        switch = switch_mod.IdealProSwitch(api, coord, {})

        results = await asyncio.wait_for(
            asyncio.gather(
                switch.async_turn_off(),
                switch.async_turn_on(),
                switch.async_turn_off(),
            ),
            timeout=_burst_timeout(),
        )

        assert results == [None] * 3, results
        assert dev.power == "off"
        assert dev.commands == ["ON"], dev.commands
        assert coord.data["power"] == "off"

    run(scenario())


def test_entity_light_drag_sends_only_final_brightness():
    async def scenario():
        dev = FakeDevice(power="on", led_level=3)
        dev.delay = 0.01
        api = DeviceAPI.build(dev)
        coord = FakeCoordinator({"led_level": 3})
        light = light_mod.IdealProLight(api, coord, {})

        await asyncio.wait_for(
            asyncio.gather(
                light.async_turn_on(brightness=28),
                light.async_turn_on(brightness=142),
                light.async_turn_off(),
            ),
            timeout=_burst_timeout(),
        )

        assert dev.led_level == 0
        assert dev.commands == ["D0"], dev.commands
        assert coord.data["led_level"] == 0

    run(scenario())


def test_interleaved_channels_keep_chronological_order():
    """speed -> off -> speed must end running at the last speed, not off."""
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="auto")
        dev.delay = 0.01
        api = DeviceAPI.build(dev)

        results = await asyncio.wait_for(
            asyncio.gather(
                api.async_set_fan_speed_verified("quiet"),
                api.async_turn_off(),
                api.async_set_fan_speed_verified("turbo"),
            ),
            timeout=_burst_timeout(),
        )

        assert results == [True] * 3, results
        assert dev.power == "on"
        assert dev.fan_speed == "turbo"
        # off followed by turbo: power-down then power-up with the mode.
        assert dev.commands == ["ON", "ON", "ST"], dev.commands

    run(scenario())


def test_entity_slider_off_then_back_ends_running():
    """Dragging the slider to 0 and back up must end at the final speed."""
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="speed_2")
        dev.delay = 0.01
        api = DeviceAPI.build(dev)
        coord = FakeCoordinator({"power": "on", "fan_speed": "speed_2", "speed_level": 3})
        fan = fan_mod.IdealProFan(api, coord, {})

        await asyncio.wait_for(
            asyncio.gather(
                fan.async_set_percentage(0),
                fan.async_set_percentage(100),
            ),
            timeout=_burst_timeout(),
        )

        assert dev.power == "on"
        assert dev.fan_speed == "turbo"
        assert coord.data["fan_speed"] == "turbo"
        assert coord.data["speed_level"] == 5

    run(scenario())


def test_entities_sharing_one_api_coexist_under_burst():
    async def scenario():
        dev = FakeDevice(power="on", fan_speed="speed_2", led_level=3)
        dev.delay = 0.01
        api = DeviceAPI.build(dev)
        coord = FakeCoordinator(
            {"power": "on", "fan_speed": "speed_2", "speed_level": 3, "led_level": 3}
        )
        fan = fan_mod.IdealProFan(api, coord, {})
        switch = switch_mod.IdealProSwitch(api, coord, {})
        light = light_mod.IdealProLight(api, coord, {})

        await asyncio.wait_for(
            asyncio.gather(
                fan.async_set_percentage(100),
                switch.async_turn_off(),
                light.async_turn_on(brightness=142),
            ),
            timeout=_burst_timeout(),
        )

        assert dev.power == "off"
        assert dev.led_level == 5
        # Each channel saw exactly one command, in queue order.
        assert dev.commands == ["ST", "ON", "D5"], dev.commands
        assert api.max_active_calls == 1

    run(scenario())


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = []
    for test in tests:
        try:
            test()
        except Exception as err:
            failed.append(test.__name__)
            print(f"FAIL {test.__name__}: {err!r}")
        else:
            print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} tests passed." if not failed else f"\n{len(failed)} FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
