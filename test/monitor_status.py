#!/usr/bin/env python3
"""
Monitor all Ideal Pro status fields over time.

Useful for reverse engineering: poll the device, print every field and log
everything to a CSV so changes can be correlated with events (dust, spray,
cooking, fan commands...).

Usage:
    python3 test/monitor_status.py
    python3 test/monitor_status.py --interval 1 --duration 120 --csv status.csv
    python3 test/monitor_status.py --host 192.168.178.112 --interval 5

Options:
    --host HOST        Device IP (default 192.168.178.112)
    --port PORT        Device port (default 8899)
    --interval SEC     Seconds between samples (default 2)
    --duration SEC     Stop after SEC seconds, 0 = run forever (default 0)
    --csv FILE         Write samples to FILE (default: monitor_<timestamp>.csv)
"""

import argparse
import asyncio
import csv
import os
import sys
import time
from datetime import datetime

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

FIELDS = [
    "D", "V", "R", "P", "O", "S", "W", "U", "Y", "Z", "I",
    "T", "X", "L", "N", "J", "C", "HD", "KI", "FO",
]


def fmt(status, previous):
    """Format one sample, marking changed fields with '*'."""
    parts = []
    for key in FIELDS:
        value = status.get(key, "-")
        mark = "*" if previous and previous.get(key) != value else " "
        parts.append(f"{key}={value}{mark}")
    return " ".join(parts)


async def main():
    parser = argparse.ArgumentParser(description="Monitor Ideal Pro status fields")
    parser.add_argument("--host", default="192.168.178.112")
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--duration", type=float, default=0)
    parser.add_argument("--csv", default=None)
    args = parser.parse_args()

    csv_path = args.csv or f"monitor_{int(time.time())}.csv"
    api = IdealProAPI(args.host, args.port)
    start = time.time()
    previous = None

    with open(csv_path, "w", newline="") as csv_file:
        writer = None
        print(f"# monitoring {args.host}:{args.port} -> {csv_path}")
        print(f"# interval={args.interval}s duration={args.duration or 'forever'}s")
        print(f"# sample time | mode/power | {' '.join(FIELDS)}")

        while args.duration == 0 or time.time() - start < args.duration:
            try:
                raw = await api.async_handshake_and_read(timeout=2.0)
                status = api.parse_status(raw or "")
            except Exception as err:
                print(f"{time.time() - start:7.1f} connect error: {err}")
                await asyncio.sleep(args.interval)
                continue

            row = {"timestamp": datetime.now().isoformat(timespec="seconds"),
                   "elapsed": round(time.time() - start, 1),
                   "power": status.get("power"),
                   "fan_speed": status.get("fan_speed")}
            for key in FIELDS:
                row[key] = status.get(key)
            row["body"] = status.get("body", "")

            if writer is None:
                writer = csv.DictWriter(csv_file, fieldnames=list(row))
                writer.writeheader()
            writer.writerow(row)
            csv_file.flush()

            print(f"{time.time() - start:7.1f} {status.get('power', '?'):<7} "
                  f"{status.get('fan_speed', '?'):<8} {fmt(status, previous)}")
            previous = status
            await asyncio.sleep(args.interval)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
