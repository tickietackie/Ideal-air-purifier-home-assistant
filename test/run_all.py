#!/usr/bin/env python3
"""Run every offline test module (no device or network required).

The interactive/hardware scripts (test_fan.py, test_led.py, test_power.py,
monitor_status.py) are intentionally not part of this runner.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

OFFLINE_TESTS = [
    "test_parse_status.py",
    "test_api_power.py",
    "test_api_modes.py",
    "test_concurrency.py",
    "test_entities.py",
]


def main():
    failed = []
    for name in OFFLINE_TESTS:
        path = os.path.join(HERE, name)
        print(f"\n===== {name} =====")
        result = subprocess.run([sys.executable, path])
        if result.returncode != 0:
            failed.append(name)

    print()
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1
    print(f"All {len(OFFLINE_TESTS)} offline test modules passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
