#!/usr/bin/env python3
"""
Unit tests for IdealProAPI.parse_status.

The test vectors below are real status frames captured from a device (see
captures/*.txt). They can be run with pytest or directly:

    python3 test/test_parse_status.py
"""

import os
import sys

# Add custom_components/idealpro to path to import the api module
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "custom_components",
        "idealpro",
    ),
)

from api import IdealProAPI

API = IdealProAPI("127.0.0.1")

# --- Real capture frames -------------------------------------------------
STATUS_OFF = (
    "{A-,FO,C00000,S0,KI,L9,D1430,V0283,R0281,N00000,O00000,Y0674,"
    "Z01770,P094,W01,HD0N1,I0275,J0000,U0540,T40,X006}"
)
STATUS_AUTO_2 = (
    "{A2,FO,C00000,S2,KI,L9,D1424,V0296,R0281,N00000,O00333,Y0673,"
    "Z01770,P094,W03,HD1N1,I0275,J0000,U1500,T40,X006}"
)
STATUS_MANUAL_1 = (
    "{M1,FO,C00000,S2,KI,L9,D1424,V0295,R0281,N00000,O00329,Y0673,"
    "Z01770,P094,W03,HD1N1,I0275,J0000,U2220,T40,X006}"
)
STATUS_MANUAL_3 = (
    "{M3,FO,C00000,S2,KI,L9,D1410,V0296,R0281,N00000,O00320,Y0674,"
    "Z01770,P094,W05,HD1N1,I0275,J0000,U2100,T40,X006}"
)
STATUS_TURBO = (
    "{MT,FO,C00000,S2,KI,L9,D1437,V0295,R0281,N00000,O00313,Y0674,"
    "Z01770,P094,W10,HD1N1,I0275,J0000,U3120,T40,X006}"
)
STATUS_ON_LED9 = (
    "{A1,FO,C00000,S1,KI,L9,D1437,V0288,R0281,N00000,O00000,Y0674,"
    "Z01770,P094,W01,HD9N1,I0275,J0000,U0540,T40,X006}"
)


def test_power_off():
    status = API.parse_status(STATUS_OFF)
    assert status["power"] == "off"
    assert status["fan_speed"] == "off"
    assert status["led_level"] == 0


def test_auto_mode():
    status = API.parse_status(STATUS_AUTO_2)
    assert status["power"] == "on"
    assert status["fan_speed"] == "auto"
    assert status["led_level"] == 1


def test_manual_modes():
    assert API.parse_status(STATUS_MANUAL_1)["fan_speed"] == "speed_1"
    assert API.parse_status(STATUS_MANUAL_3)["fan_speed"] == "speed_3"


def test_turbo_mode():
    status = API.parse_status(STATUS_TURBO)
    assert status["power"] == "on"
    assert status["fan_speed"] == "turbo"


def test_quiet_mode():
    status = API.parse_status("{MQ,FO,C00000,S1,KI,L9,HD5N1}")
    assert status["power"] == "on"
    assert status["fan_speed"] == "quiet"
    assert status["led_level"] == 5


def test_led_levels():
    assert API.parse_status(STATUS_ON_LED9)["led_level"] == 9
    assert API.parse_status(STATUS_OFF)["led_level"] == 0


def test_tokens_and_body():
    status = API.parse_status(STATUS_AUTO_2)
    assert status["body"] == STATUS_AUTO_2.strip("{}")
    assert status["raw"] == STATUS_AUTO_2
    assert status["HD"] == "1N1"
    assert status["W"] == "03"
    assert status["D"] == "1424"


def test_last_block_wins():
    raw = STATUS_OFF + "\n" + STATUS_AUTO_2
    status = API.parse_status(raw)
    assert status["power"] == "on"
    assert status["fan_speed"] == "auto"


def test_unknown_input():
    for raw in ("", "garbage", "{}", "  "):
        status = API.parse_status(raw)
        assert status["power"] == "unknown", raw
        assert status["fan_speed"] == "unknown", raw


def test_fan_speed_command_mapping():
    assert API.FAN_SPEED_COMMANDS == {
        "quiet": b"SQ",
        "auto": b"SA",
        "speed_1": b"S1",
        "speed_2": b"S2",
        "speed_3": b"S3",
        "turbo": b"ST",
    }


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} tests passed.")


if __name__ == "__main__":
    main()
