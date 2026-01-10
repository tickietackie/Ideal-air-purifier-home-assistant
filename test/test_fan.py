#!/usr/bin/env python3
"""
Test script for Ideal Pro Air Purifier fan speed control.

This script tests the state-aware fan speed control methods that:
1. Check current fan speed before sending command
2. Verify the speed changed correctly
3. Retry on failure

Usage:
    python test_fan.py              # Interactive menu
    python test_fan.py status       # Get current status
    python test_fan.py set quiet    # Set to quiet mode
    python test_fan.py set auto     # Set to auto mode
    python test_fan.py set 1        # Set to speed 1
    python test_fan.py set turbo    # Set to turbo mode
    python test_fan.py cycle        # Cycle through all modes
"""

import asyncio
import sys
import os

# Add parent directory to path to import the api module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import IdealProAPI

# Configure your device IP here
DEVICE_IP = "192.168.178.112"
DEVICE_PORT = 8899

# Mode aliases for user-friendly input
MODE_ALIASES = {
    "q": "quiet",
    "quiet": "quiet",
    "a": "auto",
    "auto": "auto",
    "1": "speed_1",
    "speed_1": "speed_1",
    "2": "speed_2",
    "speed_2": "speed_2",
    "3": "speed_3",
    "speed_3": "speed_3",
    "t": "turbo",
    "turbo": "turbo",
}


async def test_get_status(api: IdealProAPI):
    """Test getting device status including fan speed."""
    print(f"\n📡 Getting status from {DEVICE_IP}:{DEVICE_PORT}...")
    
    raw = await api.async_handshake_and_read()
    if raw:
        print(f"← Raw response: {raw}")
        status = api.parse_status(raw)
        print(f"\n📊 Parsed status:")
        print(f"   Power: {status.get('power', 'unknown').upper()}")
        print(f"   Fan Speed: {status.get('fan_speed', 'unknown')}")
        print(f"   LED Level: {status.get('led_level', 'N/A')}")
        return status
    else:
        print("❌ No response from device")
        return None


async def test_get_fan_speed(api: IdealProAPI):
    """Test getting current fan speed."""
    print(f"\n🌀 Getting fan speed...")
    speed = await api.async_get_fan_speed()
    print(f"   Current fan speed: {speed}")
    return speed


async def test_set_fan_speed_verified(api: IdealProAPI, mode: str):
    """Test state-aware fan speed setting with verification."""
    # Resolve mode alias
    resolved_mode = MODE_ALIASES.get(mode.lower())
    if not resolved_mode:
        print(f"❌ Unknown mode: {mode}")
        print(f"   Valid modes: quiet (q), auto (a), 1, 2, 3, turbo (t)")
        return False
    
    print(f"\n🌀 Setting fan speed to {resolved_mode} (with verification)...")
    print("   (This will check current speed, send command if needed, and verify)")
    
    success = await api.async_set_fan_speed_verified(resolved_mode)
    
    if success:
        print(f"✅ Fan confirmed at {resolved_mode}!")
    else:
        print(f"❌ Failed to set fan to {resolved_mode} after retries")
    
    return success


async def test_set_fan_speed_legacy(api: IdealProAPI, mode: str):
    """Test legacy fan speed setting (no verification)."""
    # Resolve mode alias
    resolved_mode = MODE_ALIASES.get(mode.lower())
    if not resolved_mode:
        print(f"❌ Unknown mode: {mode}")
        return
    
    print(f"\n🌀 Setting fan speed to {resolved_mode} (legacy, no verification)...")
    
    try:
        await api.async_set_fan_speed(resolved_mode)
        print(f"→ Fan speed command sent for {resolved_mode}")
        
        # Check speed after command
        await asyncio.sleep(1.0)
        new_speed = await api.async_get_fan_speed()
        print(f"   New fan speed: {new_speed}")
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_mode_cycle(api: IdealProAPI):
    """Cycle through all fan speed modes."""
    print(f"\n🔄 Testing all fan speed modes...")
    
    modes = ["quiet", "auto", "speed_1", "speed_2", "speed_3", "turbo"]
    results = []
    
    for mode in modes:
        success = await api.async_set_fan_speed_verified(mode)
        results.append((mode, success))
        print(f"   {mode}: {'✅' if success else '❌'}")
        await asyncio.sleep(1)
    
    successes = sum(1 for _, s in results if s)
    total = len(results)
    print(f"\n📈 Cycle Results:")
    print(f"   Total modes: {total}")
    print(f"   Successes: {successes} ({100*successes/total:.1f}%)")
    print(f"   Failures: {total - successes} ({100*(total-successes)/total:.1f}%)")


async def test_reliability(api: IdealProAPI, cycles: int = 3):
    """Test fan speed reliability over multiple cycles."""
    print(f"\n🧪 Running fan reliability test: {cycles} full cycles...")
    
    modes = ["quiet", "auto", "speed_1", "speed_2", "speed_3", "turbo"]
    successes = 0
    failures = 0
    
    for i in range(cycles):
        print(f"\n--- Cycle {i+1}/{cycles} ---")
        
        for mode in modes:
            if await api.async_set_fan_speed_verified(mode):
                successes += 1
            else:
                failures += 1
            await asyncio.sleep(0.5)
    
    total = cycles * len(modes)
    print(f"\n📈 Reliability Results:")
    print(f"   Total commands: {total}")
    print(f"   Successes: {successes} ({100*successes/total:.1f}%)")
    print(f"   Failures: {failures} ({100*failures/total:.1f}%)")


async def interactive_menu(api: IdealProAPI):
    """Interactive menu for testing."""
    while True:
        print("\n" + "="*50)
        print("Ideal Pro Fan Speed - Test Menu")
        print("="*50)
        print("1. Get current status")
        print("2. Get fan speed only")
        print("3. Set fan speed (with verification)")
        print("4. Set fan speed (legacy, no verification)")
        print("5. Mode cycle test (all modes)")
        print("6. Reliability test (3 full cycles)")
        print("7. Quick preset: Quiet")
        print("8. Quick preset: Auto")
        print("9. Quick preset: Turbo")
        print("0. Exit")
        print("-"*50)
        
        choice = input("Select option (0-9): ").strip()
        
        if choice == "1":
            await test_get_status(api)
        elif choice == "2":
            await test_get_fan_speed(api)
        elif choice == "3":
            mode = input("Enter mode (quiet/q, auto/a, 1, 2, 3, turbo/t): ").strip()
            await test_set_fan_speed_verified(api, mode)
        elif choice == "4":
            mode = input("Enter mode (quiet/q, auto/a, 1, 2, 3, turbo/t): ").strip()
            await test_set_fan_speed_legacy(api, mode)
        elif choice == "5":
            await test_mode_cycle(api)
        elif choice == "6":
            await test_reliability(api)
        elif choice == "7":
            await test_set_fan_speed_verified(api, "quiet")
        elif choice == "8":
            await test_set_fan_speed_verified(api, "auto")
        elif choice == "9":
            await test_set_fan_speed_verified(api, "turbo")
        elif choice == "0":
            print("\nGoodbye! 👋")
            break
        else:
            print("Invalid option, try again.")


async def main():
    api = IdealProAPI(DEVICE_IP, DEVICE_PORT)
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "status":
            await test_get_status(api)
        elif cmd == "speed":
            await test_get_fan_speed(api)
        elif cmd == "set":
            if len(sys.argv) > 2:
                mode = sys.argv[2]
                await test_set_fan_speed_verified(api, mode)
            else:
                print("Usage: python test_fan.py set <mode>")
        elif cmd == "cycle":
            await test_mode_cycle(api)
        elif cmd == "test":
            cycles = int(sys.argv[2]) if len(sys.argv) > 2 else 3
            await test_reliability(api, cycles)
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python test_fan.py [status|speed|set <mode>|cycle|test]")
    else:
        # Interactive mode
        await interactive_menu(api)


if __name__ == "__main__":
    asyncio.run(main())
