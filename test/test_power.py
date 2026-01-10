#!/usr/bin/env python3
"""
Test script for Ideal Pro Air Purifier power control.

This script tests the state-aware turn_on/turn_off methods that:
1. Check current state before toggling
2. Verify the state changed correctly
3. Retry on failure

Usage:
    python test_power.py              # Interactive menu
    python test_power.py status       # Get current status
    python test_power.py on           # Turn on (with verification)
    python test_power.py off          # Turn off (with verification)
    python test_power.py toggle       # Toggle (legacy, no verification)
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


async def test_get_status(api: IdealProAPI):
    """Test getting device status."""
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


async def test_turn_on(api: IdealProAPI):
    """Test state-aware turn ON with verification."""
    print(f"\n🔛 Turning ON device at {DEVICE_IP}...")
    print("   (This will check state, send toggle if needed, and verify)")
    
    success = await api.async_turn_on()
    
    if success:
        print("✅ Device confirmed ON!")
    else:
        print("❌ Failed to turn device ON after retries")
    
    return success


async def test_turn_off(api: IdealProAPI):
    """Test state-aware turn OFF with verification."""
    print(f"\n🔴 Turning OFF device at {DEVICE_IP}...")
    print("   (This will check state, send toggle if needed, and verify)")
    
    success = await api.async_turn_off()
    
    if success:
        print("✅ Device confirmed OFF!")
    else:
        print("❌ Failed to turn device OFF after retries")
    
    return success


async def test_toggle_legacy(api: IdealProAPI):
    """Test legacy toggle (no state verification)."""
    print(f"\n🔄 Sending legacy toggle to {DEVICE_IP}...")
    print("   ⚠️  This does NOT verify state change!")
    
    try:
        await api.async_toggle()
        print("→ Toggle command sent")
        
        # Check state after toggle
        await asyncio.sleep(0.5)
        raw = await api.async_handshake_and_read()
        if raw:
            status = api.parse_status(raw)
            print(f"   New state: {status.get('power', 'unknown').upper()}")
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_reliability(api: IdealProAPI, cycles: int = 5):
    """Test ON/OFF reliability over multiple cycles."""
    print(f"\n🧪 Running reliability test: {cycles} ON/OFF cycles...")
    
    successes = 0
    failures = 0
    
    for i in range(cycles):
        print(f"\n--- Cycle {i+1}/{cycles} ---")
        
        # Turn ON
        if await api.async_turn_on():
            successes += 1
        else:
            failures += 1
        
        await asyncio.sleep(1)
        
        # Turn OFF
        if await api.async_turn_off():
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
        print("Ideal Pro Air Purifier - Test Menu")
        print("="*50)
        print("1. Get current status")
        print("2. Turn ON (with verification)")
        print("3. Turn OFF (with verification)")
        print("4. Toggle (legacy, no verification)")
        print("5. Reliability test (5 cycles)")
        print("6. Exit")
        print("-"*50)
        
        choice = input("Select option (1-6): ").strip()
        
        if choice == "1":
            await test_get_status(api)
        elif choice == "2":
            await test_turn_on(api)
        elif choice == "3":
            await test_turn_off(api)
        elif choice == "4":
            await test_toggle_legacy(api)
        elif choice == "5":
            await test_reliability(api)
        elif choice == "6":
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
        elif cmd == "on":
            await test_turn_on(api)
        elif cmd == "off":
            await test_turn_off(api)
        elif cmd == "toggle":
            await test_toggle_legacy(api)
        elif cmd == "test":
            cycles = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            await test_reliability(api, cycles)
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python test_power.py [status|on|off|toggle|test]")
    else:
        # Interactive mode
        await interactive_menu(api)


if __name__ == "__main__":
    asyncio.run(main())
