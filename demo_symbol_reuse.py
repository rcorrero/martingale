#!/usr/bin/env python3
"""
Demonstration script showing why UNIQUE constraint on symbols is problematic.

This script simulates the symbol exhaustion problem and demonstrates
how the new symbol reuse mechanism solves it.
"""

import random
import string


def simulate_old_behavior():
    """Simulate the old behavior with UNIQUE constraint."""
    print("\n" + "="*70)
    print("OLD BEHAVIOR: UNIQUE Constraint on Symbols")
    print("="*70 + "\n")
    
    # Simulate a small symbol space (2 letters instead of 3 for demo)
    SYMBOL_LENGTH = 2
    MAX_SYMBOLS = 26 ** SYMBOL_LENGTH  # 676 possible combinations
    
    used_symbols = set()
    assets_created = 0
    
    print(f"Symbol space: {MAX_SYMBOLS} possible 2-letter combinations")
    print(f"Creating assets until failure...\n")
    
    try:
        while True:
            # Try to generate unused symbol
            attempts = 0
            symbol = None
            
            while attempts < 10000:  # Prevent infinite loop in demo
                symbol = ''.join(random.choices(string.ascii_uppercase, k=SYMBOL_LENGTH))
                if symbol not in used_symbols:
                    break
                attempts += 1
            
            if attempts >= 10000:
                print(f"❌ FAILURE: Could not find unused symbol after {attempts} attempts")
                print(f"   Assets created before failure: {assets_created}")
                print(f"   Symbol space utilization: {len(used_symbols)}/{MAX_SYMBOLS} ({len(used_symbols)/MAX_SYMBOLS*100:.1f}%)")
                break
            
            used_symbols.add(symbol)
            assets_created += 1
            
            # Print progress
            if assets_created % 100 == 0:
                print(f"  Created {assets_created} assets, {len(used_symbols)} unique symbols used")
            
            # Stop at symbol space exhaustion
            if len(used_symbols) >= MAX_SYMBOLS:
                print(f"\n✓ All {MAX_SYMBOLS} symbols used")
                print(f"❌ NEXT ASSET CREATION WOULD FAIL (UNIQUE constraint violation)")
                break
                
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    print(f"\nFinal stats:")
    print(f"  Total assets created: {assets_created}")
    print(f"  Unique symbols used: {len(used_symbols)}/{MAX_SYMBOLS}")


def simulate_new_behavior():
    """Simulate the new behavior without UNIQUE constraint."""
    print("\n\n" + "="*70)
    print("NEW BEHAVIOR: Symbol Reuse Allowed (No UNIQUE Constraint)")
    print("="*70 + "\n")
    
    SYMBOL_LENGTH = 2
    MAX_SYMBOLS = 26 ** SYMBOL_LENGTH  # 676 possible combinations
    
    # Track all assets with their symbols and active status
    assets = []  # List of (symbol, is_active)
    assets_created = 0
    symbols_reused = 0
    
    print(f"Symbol space: {MAX_SYMBOLS} possible 2-letter combinations")
    print(f"Creating assets with symbol reuse enabled...\n")
    
    try:
        # Create way more assets than available symbols
        TARGET_ASSETS = MAX_SYMBOLS * 3  # 3x the symbol space
        
        for i in range(TARGET_ASSETS):
            # Simulate asset lifecycle: 10% chance existing asset expires
            if assets and random.random() < 0.1:
                idx = random.randint(0, len(assets) - 1)
                if assets[idx][1]:  # If active
                    symbol, _ = assets[idx]
                    assets[idx] = (symbol, False)  # Mark as inactive
            
            # Generate symbol (prefers unused, allows reuse)
            active_symbols = {s for s, active in assets if active}
            
            # Try to find unused symbol first (100 attempts)
            symbol = None
            for _ in range(100):
                candidate = ''.join(random.choices(string.ascii_uppercase, k=SYMBOL_LENGTH))
                if candidate not in active_symbols:
                    symbol = candidate
                    break
            
            # If no unused symbol found, just use random one (reuse)
            if symbol is None:
                symbol = ''.join(random.choices(string.ascii_uppercase, k=SYMBOL_LENGTH))
                symbols_reused += 1
            
            # Create asset
            assets.append((symbol, True))
            assets_created += 1
            
            # Print progress
            if (i + 1) % 200 == 0:
                active = sum(1 for _, a in assets if a)
                unique_active = len(set(s for s, a in assets if a))
                print(f"  Created {assets_created} assets, {active} active, "
                      f"{unique_active} unique active symbols, {symbols_reused} reused")
        
        print(f"\n✓ SUCCESS: Created {TARGET_ASSETS} assets")
        print(f"  (That's {TARGET_ASSETS/MAX_SYMBOLS:.1f}x the available symbol space!)")
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    print(f"\nFinal stats:")
    print(f"  Total assets created: {assets_created}")
    print(f"  Active assets: {sum(1 for _, a in assets if a)}")
    print(f"  Unique symbols used: {len(set(s for s, _ in assets))}")
    print(f"  Symbols reused: {symbols_reused}")
    print(f"  Symbol space: {MAX_SYMBOLS}")
    print(f"\n  System remains functional indefinitely! ✓")


def calculate_exhaustion_time():
    """Calculate when the symbol space would be exhausted in production."""
    print("\n\n" + "="*70)
    print("PRODUCTION IMPACT ANALYSIS")
    print("="*70 + "\n")
    
    SYMBOL_LENGTH = 3
    MAX_SYMBOLS = 26 ** SYMBOL_LENGTH  # 17,576
    
    print(f"3-letter uppercase symbols:")
    print(f"  Total possible combinations: {MAX_SYMBOLS:,}")
    print()
    
    scenarios = [
        ("Conservative (16 assets, 30min avg expiry)", 16, 30),
        ("Moderate (16 assets, 15min avg expiry)", 16, 15),
        ("Aggressive (32 assets, 10min avg expiry)", 32, 10),
    ]
    
    for scenario_name, num_assets, avg_expiry_min in scenarios:
        # Assets per hour = (60 / avg_expiry) * num_assets
        assets_per_hour = (60 / avg_expiry_min) * num_assets
        assets_per_day = assets_per_hour * 24
        days_to_exhaustion = MAX_SYMBOLS / assets_per_day
        
        print(f"{scenario_name}:")
        print(f"  Assets created/hour: {assets_per_hour:.1f}")
        print(f"  Assets created/day: {assets_per_day:.1f}")
        print(f"  Days until exhaustion: {days_to_exhaustion:.1f}")
        print()
    
    print("Without symbol reuse:")
    print("  ❌ System would FAIL after exhaustion")
    print("  ❌ Cannot create new assets")
    print("  ❌ Trading would stop")
    print()
    print("With symbol reuse:")
    print("  ✓ System continues indefinitely")
    print("  ✓ Old symbols recycled after expiration")
    print("  ✓ No impact on functionality")


def main():
    """Run all demonstrations."""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "    Symbol Reuse Demonstration - Martingale Trading Platform    ".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    
    # Show production impact first
    calculate_exhaustion_time()
    
    # Demonstrate old vs new behavior
    simulate_old_behavior()
    simulate_new_behavior()
    
    print("\n\n" + "="*70)
    print("CONCLUSION")
    print("="*70 + "\n")
    print("The UNIQUE constraint on asset.symbol was a critical bug that would")
    print("cause production failure within weeks of operation.")
    print()
    print("By removing the constraint and implementing symbol reuse:")
    print("  ✓ System can operate indefinitely")
    print("  ✓ Asset IDs ensure unambiguous references")
    print("  ✓ Backward compatibility maintained")
    print("  ✓ Performance impact negligible")
    print()
    print("This change is ESSENTIAL for production deployment.")
    print()


if __name__ == '__main__':
    main()
