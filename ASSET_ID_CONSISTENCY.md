# Asset ID Consistency Implementation

## Overview

This document describes the implementation of consistent asset ID usage throughout the Martingale Trading Platform, ensuring proper asset identification and preventing data integrity issues.

## Problem Statement

The original implementation had several issues related to asset identification:

1. **Symbol-based lookups**: Historical queries used `filter_by(symbol=).order_by(created_at.desc())` which is ambiguous
2. **No symbol uniqueness**: The database allows duplicate symbols (though unlikely with 3-letter random generation)
3. **Mixed storage**: Holdings stored as JSON with both integer IDs and string symbols as keys
4. **Backward compatibility**: Need to handle legacy data with symbol-based references

## Solution

Implemented consistent asset ID usage with backward compatibility:

### 1. Helper Methods

Added `Asset.get_by_id_or_symbol()` static method for safe asset lookups:
```python
Asset.get_by_id_or_symbol(asset_id=None, symbol=None, active_only=False)
```
- **Prefers ID lookup**: Always uses asset_id when available
- **Falls back to symbol**: For backward compatibility with legacy data
- **Handles active filtering**: Optional filtering for active assets only
- **Returns most recent**: When lookup by symbol, returns newest asset with that symbol

### 2. Portfolio Methods

Added `Portfolio.get_asset_from_holdings()` method:
```python
portfolio.get_asset_from_holdings(asset_id)
```
- **Validates holdings**: Only returns asset if user actually holds it
- **Uses ID directly**: No symbol ambiguity
- **Returns None safely**: If asset not in holdings or not found

### 3. Updated Backfill Logic

Modified Transaction and Settlement backfill code to use new helper:
```python
# Before
asset = Asset.query.filter_by(symbol=legacy_symbol).order_by(Asset.created_at.desc()).first()

# After
asset = Asset.get_by_id_or_symbol(symbol=legacy_symbol)
```

### 4. Backward Compatibility

The `Portfolio._normalize_asset_id()` method handles:
- Integer IDs (preferred format)
- String representations of IDs
- Legacy symbol-based keys
- Mixed holdings data

## Database Schema

### Asset Table
- `id`: INTEGER PRIMARY KEY (preferred reference)
- `symbol`: VARCHAR(10) UNIQUE NOT NULL (user-facing identifier)
- `is_active`: BOOLEAN (lifecycle state)

### Transaction Table  
- `asset_id`: INTEGER NOT NULL (FK to assets.id)
- `legacy_symbol`: VARCHAR(10) (backward compatibility)

### Settlement Table
- `asset_id`: INTEGER NOT NULL (FK to assets.id)
- `legacy_symbol`: VARCHAR(10) (backward compatibility)

### Portfolio Table
- `holdings`: JSON TEXT (stores {asset_id: quantity} mapping)
- `position_info`: JSON TEXT (stores {asset_id: {total_cost, total_quantity}} mapping)

## Key Benefits

### 1. Data Integrity
- **Unambiguous references**: Each asset has unique ID that never changes
- **No symbol confusion**: Even if symbols are reused, IDs remain distinct
- **Proper foreign keys**: Database enforces referential integrity

### 2. Performance
- **Indexed lookups**: Primary key lookups are fastest
- **No string comparisons**: Integer comparison vs string matching
- **Single query**: No need for `.order_by(created_at.desc())` workarounds

### 3. Backward Compatibility
- **Legacy data supported**: Symbol-based holdings automatically normalized
- **Gradual migration**: New code uses IDs, old data handled gracefully
- **No breaking changes**: Existing functionality preserved

### 4. Race Condition Prevention
- **Holdings isolated**: User holdings tied to specific asset instance by ID
- **Transaction tracking**: Trade history unambiguous even with symbol reuse
- **Settlement accuracy**: Expired positions reference correct asset

## Test Coverage

Created comprehensive test suite (`test_asset_id_consistency.py`) with 12 tests:

### TestAssetIDConsistency
1. `test_asset_get_by_id_or_symbol_with_id` - ID lookup functionality
2. `test_asset_get_by_id_or_symbol_with_symbol` - Symbol fallback
3. `test_asset_get_by_id_or_symbol_active_only` - Active filtering
4. `test_asset_get_by_id_or_symbol_id_preferred_over_symbol` - ID precedence
5. `test_portfolio_holdings_use_asset_id` - Integer ID storage
6. `test_portfolio_get_asset_from_holdings` - Holdings method
7. `test_portfolio_backward_compatible_symbol_holdings` - Legacy support
8. `test_transaction_uses_asset_id` - Transaction FK
9. `test_settlement_uses_asset_id` - Settlement FK
10. `test_mixed_id_and_symbol_holdings` - Mixed data handling

### TestAssetIDRaceConditions
11. `test_holdings_isolated_by_asset_id` - Holdings isolation
12. `test_transactions_track_correct_asset_by_id` - Transaction integrity

**All 12 tests passing** ✅

## Migration Path

### For Existing Deployments

1. **No action required**: Backward compatibility built-in
2. **Holdings normalization**: Automatic on portfolio access
3. **Backfill runs**: Transaction/Settlement asset_id populated on startup
4. **New data**: Automatically uses ID-based approach

### For New Deployments

1. **Fresh database**: All references use asset_id from the start
2. **No legacy data**: Symbol-based fallback not needed
3. **Optimal performance**: Pure ID-based lookups

## Code Examples

### Looking up an asset (new way)
```python
# Prefer ID when available
asset = Asset.get_by_id_or_symbol(asset_id=42)

# Fall back to symbol for legacy code
asset = Asset.get_by_id_or_symbol(symbol='ABC')

# Check for active assets only
asset = Asset.get_by_id_or_symbol(asset_id=42, active_only=True)
```

### Working with holdings
```python
# Get holdings (always keyed by ID)
holdings = portfolio.get_holdings_map()  # {42: 150.5, 97: 200.0}

# Get specific asset from holdings
asset = portfolio.get_asset_from_holdings(42)  # Returns Asset or None

# Set holdings (using IDs)
holdings = {asset.id: quantity}
portfolio.set_holdings(holdings)
```

### Querying transactions
```python
# Query by asset_id (unambiguous)
txns = Transaction.query.filter_by(asset_id=42).all()

# Asset relationship works automatically
for txn in txns:
    print(txn.asset.symbol)  # Via FK relationship
```

## Future Improvements

### Short Term
1. **Remove legacy_symbol column**: After sufficient production time, can be deprecated
2. **Add asset_id indexes**: On transaction/settlement tables if not already present
3. **Performance monitoring**: Track query performance on asset_id vs symbol lookups

### Long Term
1. **Separate holdings table**: Replace JSON storage with proper table
2. **Full Decimal migration**: Convert Float columns to DECIMAL for precision
3. **Symbol reuse prevention**: Add database-level constraints if needed

## Testing Recommendations

Before deploying to production:

1. **Run full test suite**: 
   ```bash
   source .venv/bin/activate  # Always activate virtual environment first!
   python -m pytest test_validators.py test_asset_id_consistency.py -v
   ```
2. **Test with legacy data**: Verify existing holdings normalize correctly
3. **Monitor performance**: Check for any query slowdowns
4. **Verify backfills**: Ensure Transaction/Settlement asset_id populated

## Summary

The asset ID consistency implementation provides:
- ✅ **Unambiguous asset identification** via primary key IDs
- ✅ **Backward compatibility** with symbol-based legacy data
- ✅ **Data integrity** through proper foreign key relationships
- ✅ **Race condition prevention** by isolating holdings per asset instance
- ✅ **Comprehensive testing** with 12 passing unit tests
- ✅ **No breaking changes** to existing functionality

The system now uses asset IDs consistently throughout, with symbol-based lookups relegated to backward compatibility and user display purposes only.
