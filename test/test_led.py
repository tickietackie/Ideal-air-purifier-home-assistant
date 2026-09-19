#!/usr/bin/env python3
"""
Test script for Ideal Pro Air Purifier LED control.

This script tests the state-aware LED brightness control methods that:
1. Check current LED level before sending command
2. Verify the level changed correctly
3. Retry on failure

Usage:
    python test_led.py              # Interactive menu
    python test_led.py status       # Get current status
    python test_led.py set 5        # Set brightness to level 5 (with verification)
    python test_led.py off          # Turn LED off (with verification)
    python test_led.py cycle        # Cycle through brightness levels
"""

import asyncio
import sys
import os

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

# Configure your device IP here
DEVICE_IP = "192.168.178.112"
DEVICE_PORT = 8899


async def test_get_status(api: IdealProAPI):
    """Test getting device status including LED level."""
    print(f"\n📡 Getting status from {DEVICE_IP}:{DEVICE_PORT}...")
    
    raw = await api.async_handshake_and_read()
    if raw:
        print(f"← Raw response: {raw}")
        status = api.parse_status(raw)
        print(f"\n📊 Parsed status:")
        print(f"   Power: {status.get('power', 'unknown').upper()}")
        print(f"   LED Level: {status.get('led_level', 'N/A')}")
        print(f"   Full body: {status.get('body', 'N/A')}")
        return status
    else:
        print("❌ No response from device")
        return None


async def test_get_led_level(api: IdealProAPI):
    """Test getting current LED level."""
    print(f"\n💡 Getting LED level...")
    level = await api.async_get_led_level()
    print(f"   Current LED level: {level}")
    return level


async def test_set_brightness_verified(api: IdealProAPI, level: int):
    """Test state-aware brightness setting with verification."""
    print(f"\n💡 Setting LED brightness to {level} (with verification)...")
    print("   (This will check current level, send command if needed, and verify)")
    
    success = await api.async_set_brightness_verified(level)
    
    if success:
        print(f"✅ LED confirmed at level {level}!")
    else:
        print(f"❌ Failed to set LED to level {level} after retries")
    
    return success


async def test_set_brightness_legacy(api: IdealProAPI, level: int):
    """Test legacy brightness setting (no verification)."""
    print(f"\n💡 Setting LED brightness to {level} (legacy, no verification)...")
    
    try:
        await api.async_set_brightness(level)
        print(f"→ Brightness command sent for level {level}")
        
        # Check level after command
        await asyncio.sleep(1.0)
        new_level = await api.async_get_led_level()
        print(f"   New LED level: {new_level}")
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_brightness_cycle(api: IdealProAPI, max_level: int = 5):
    """Cycle through brightness levels to test reliability."""
    print(f"\n🔄 Testing brightness cycle (0 → {max_level} → 0)...")
    
    results = []
    
    # Ramp up
    for level in range(0, max_level + 1):
        success = await api.async_set_brightness_verified(level)
        results.append((f"Set {level}", success))
        print(f"   Level {level}: {'✅' if success else '❌'}")
        await asyncio.sleep(0.5)
    
    # Ramp down
    for level in range(max_level, -1, -1):
        success = await api.async_set_brightness_verified(level)
        results.append((f"Set {level}", success))
        print(f"   Level {level}: {'✅' if success else '❌'}")
        await asyncio.sleep(0.5)
    
    successes = sum(1 for _, s in results if s)
    total = len(results)
    print(f"\n📈 Cycle Results:")
    print(f"   Total commands: {total}")
    print(f"   Successes: {successes} ({100*successes/total:.1f}%)")
    print(f"   Failures: {total - successes} ({100*(total-successes)/total:.1f}%)")


async def test_reliability(api: IdealProAPI, cycles: int = 5):
    """Test LED reliability over multiple ON/OFF cycles."""
    print(f"\n🧪 Running LED reliability test: {cycles} ON/OFF cycles...")
    
    successes = 0
    failures = 0
    
    for i in range(cycles):
        print(f"\n--- Cycle {i+1}/{cycles} ---")
        
        # Turn ON (level 5)
        if await api.async_set_brightness_verified(5):
            successes += 1
        else:
            failures += 1
        
        await asyncio.sleep(1)
        
        # Turn OFF (level 0)
        if await api.async_set_brightness_verified(0):
            successes += 1
        else:
            failures += 1
        
        await asyncio.sleep(1)
    
    total = cycles * 2
    print(f"\n📈 Reliability Results:")
    print(f"   Total commands: {total}")
    print(f"   Successes: {successes} ({100*successes/total:.1f}%)")
    print(f"   Failures: {failures} ({100*failures/total:.1f}%)")


async def interactive_menu(api: IdealProAPI):
    """Interactive menu for testing."""
    while True:
        print("\n" + "="*50)
        print("Ideal Pro LED - Test Menu")
        print("="*50)
        print("1. Get current status")
        print("2. Get LED level only")
        print("3. Set brightness (with verification)")
        print("4. Set brightness (legacy, no verification)")
        print("5. Brightness cycle test (0→5→0)")
        print("6. Reliability test (5 ON/OFF cycles)")
        print("7. Turn LED OFF")
        print("8. Exit")
        print("-"*50)
        
        choice = input("Select option (1-8): ").strip()
        
        if choice == "1":
            await test_get_status(api)
        elif choice == "2":
            await test_get_led_level(api)
        elif choice == "3":
            try:
                level = int(input("Enter brightness level (0-9): ").strip())
                await test_set_brightness_verified(api, level)
            except ValueError:
                print("Invalid level, enter a number 0-9")
        elif choice == "4":
            try:
                level = int(input("Enter brightness level (0-9): ").strip())
                await test_set_brightness_legacy(api, level)
            except ValueError:
                print("Invalid level, enter a number 0-9")
        elif choice == "5":
            await test_brightness_cycle(api)
        elif choice == "6":
            await test_reliability(api)
        elif choice == "7":
            await test_set_brightness_verified(api, 0)
        elif choice == "8":
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
        elif cmd == "level":
            await test_get_led_level(api)
        elif cmd == "set":
            if len(sys.argv) > 2:
                try:
                    level = int(sys.argv[2])
                    await test_set_brightness_verified(api, level)
                except ValueError:
                    print("Invalid level, use a number 0-9")
            else:
                print("Usage: python test_led.py set <level>")
        elif cmd == "off":
            await test_set_brightness_verified(api, 0)
        elif cmd == "cycle":
            max_level = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            await test_brightness_cycle(api, max_level)
        elif cmd == "test":
            cycles = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            await test_reliability(api, cycles)
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python test_led.py [status|level|set <n>|off|cycle|test]")
    else:
        # Interactive mode
        await interactive_menu(api)


if __name__ == "__main__":
    asyncio.run(main())