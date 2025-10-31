# Migration Guide: Expiring Assets System

## Overview

The Martingale trading platform has been redesigned to support **expiring assets** with automatic settlement and replacement. This document explains the changes and how to migrate from the old fixed-asset system.

## Key Changes

### 1. Dynamic Asset Lifecycle

**Before:**
- Fixed set of 11 assets (XQR, ZLN, FWX, etc.) defined in `config.py`
- Assets existed indefinitely with no expiration
- Portfolio holdings initialized with all assets set to 0

**After:**
- Assets have expiration dates ranging from 1 day to 30 days
- System automatically creates new assets to maintain a minimum pool (default: 10 active assets)
- Each asset has random symbol (3 uppercase letters), volatility (0.1% - 20%), and expiration date
- Portfolios start empty - holdings added only when user trades
- Expired assets are automatically settled and cash returned to users

### 2. Database Schema Changes

#### New Models Added

**Asset Model** (`assets` table):
- `symbol` - 3-letter random symbol (e.g., "KLP", "FGH")
- `initial_price` - Starting price when asset was created
- `current_price` - Current market price
- `volatility` - Price volatility (0.1% - 20%)
- `created_at` - When asset was created
- `expires_at` - When asset expires
- `is_active` - Whether asset is still tradeable
- `final_price` - Settlement price (set when expired)
- `settled_at` - When settlement occurred

**Settlement Model** (`settlements` table):
- `user_id` - User who held the position
- `asset_id` - Reference to expired asset
- `symbol` - Asset symbol (denormalized)
- `quantity` - Quantity held at expiration
- `settlement_price` - Final price used for settlement
- `settlement_value` - Total cash returned (quantity × price)
- `settled_at` - Settlement timestamp

#### Modified Models

**Transaction Model**:
- Added new transaction type: `'settlement'` for automatic settlements

### 3. Asset Management System

New `AssetManager` class handles:
- **Asset Creation**: Generates new assets with random symbols, volatility, expiration dates
- **Expiration Checking**: Background thread checks every 60 seconds for expired assets
- **Settlement Processing**: Automatically settles user positions at final price
- **Pool Maintenance**: Creates new assets to replace expired ones
- **Cleanup**: Removes old expired assets after 30 days

### 4. Configuration Changes

New config options in `config.py`:

```python
MIN_ACTIVE_ASSETS = 10  # Minimum active assets to maintain
EXPIRATION_CHECK_INTERVAL = 60  # Check for expirations every 60 seconds
CLEANUP_OLD_ASSETS_DAYS = 30  # Remove assets expired >30 days ago
```

### 5. API Changes

#### Modified Endpoints

**`/api/assets`** - Now returns:
```json
{
  "ABC": {
    "price": 102.34,
    "expires_at": "2025-11-15T10:30:00",
    "time_to_expiry_seconds": 432000,
    "initial_price": 100.0,
    "volatility": 0.05,
    "created_at": "2025-11-01T10:30:00"
  }
}
```

**`/api/assets/history`** - Filtered to only active assets

**`/api/open-interest`** - Uses only active assets

**`/api/performance`** - Ignores expired assets in calculations

#### New Endpoints

**`/api/assets/summary`** - Asset lifecycle statistics:
```json
{
  "active_count": 10,
  "expired_unsettled_count": 0,
  "expired_settled_count": 5,
  "average_ttl_hours": 360.5,
  "active_symbols": ["ABC", "DEF", ...],
  "expiring_soon": [...]
}
```

**`/api/settlements`** - User settlement history:
```json
[
  {
    "symbol": "XYZ",
    "quantity": 10,
    "settlement_price": 105.50,
    "settlement_value": 1055.00,
    "settled_at": "2025-11-01T12:00:00"
  }
]
```

### 6. Trade Validation

Trading now validates:
1. Asset exists in database
2. Asset is active (not expired)
3. Price is available from price service

Users cannot trade expired assets - trades are rejected with message:
```
"Asset XYZ is not available for trading (may have expired)"
```

## Migration Steps

### Step 1: Backup Database

```bash
# For SQLite
cp martingale.db martingale.db.backup

# For PostgreSQL
pg_dump $DATABASE_URL > backup.sql
```

### Step 2: Update Dependencies

No new dependencies required - existing packages support the new system.

### Step 3: Run Database Migration

The system will automatically create new tables on first run:

```bash
python app.py
```

This creates:
- `assets` table
- `settlements` table
- Initializes 10 active assets

### Step 4: Migrate Existing Data (Optional)

If you have existing user portfolios with holdings:

```python
# Run this in Flask shell or migration script
from app import app, db
from models import Asset, Portfolio, User
from asset_manager import AssetManager

with app.app_context():
    asset_manager = AssetManager(app.config)
    
    # Create initial assets
    asset_manager.initialize_asset_pool(count=10)
    
    # Clear old holdings (they were for legacy symbols)
    portfolios = Portfolio.query.all()
    for portfolio in portfolios:
        portfolio.set_holdings({})
        portfolio.set_position_info({})
    
    db.session.commit()
    print("Migration complete")
```

### Step 5: Update Frontend (if customized)

If you've customized `main.js`, update to:
1. Handle dynamic asset lists
2. Display expiration information
3. Listen for `assets_updated` WebSocket events
4. Show settlement notifications

### Step 6: Test System

1. **Verify Asset Creation**: Check `/api/assets/summary` - should show 10 active assets
2. **Test Trading**: Place buy/sell orders for active assets
3. **Test Expiration**: Create test asset expiring in 2 minutes:
   ```python
   from datetime import datetime, timedelta
   asset = Asset.create_new_asset(days_to_expiry=0.0014)  # ~2 minutes
   db.session.add(asset)
   db.session.commit()
   # Register with price service
   price_service.fallback.add_asset(asset.symbol, asset.initial_price, asset.volatility)
   ```
4. **Verify Settlement**: After expiration, check:
   - Asset marked inactive
   - User cash increased by settlement value
   - Settlement record created
   - Transaction added with type='settlement'
   - New asset created to replace expired one

## Background Processes

Two background threads now run:

### 1. Price Update Thread
- Frequency: Every 1 second
- Updates prices for active assets
- Emits WebSocket updates

### 2. Expiration Check Thread
- Frequency: Every 60 seconds (configurable)
- Checks for expired assets
- Settles user positions
- Creates replacement assets
- Emits `assets_updated` WebSocket event

## Settlement Process

When an asset expires:

1. **Mark Expired**: Asset's `is_active` set to `False`, `final_price` and `settled_at` recorded
2. **Find Holdings**: Query all portfolios for holdings in expired symbol
3. **For Each Position**:
   - Calculate settlement value = quantity × final_price
   - Add cash to user's portfolio
   - Set holding quantity to 0
   - Clear position info
   - Create `Settlement` record
   - Create `Transaction` with type='settlement'
4. **Remove from Price Service**: Delete symbol from price tracking
5. **Create Replacement**: If total active assets < MIN_ACTIVE_ASSETS, create new assets
6. **Notify Clients**: Emit WebSocket event to update frontends

## Testing Scenarios

### Test 1: Normal Trading Lifecycle
1. Create new user
2. Buy 10 shares of asset A
3. Wait for asset A to expire
4. Verify cash returned = 10 × final_price
5. Verify settlement recorded
6. Verify new asset created

### Test 2: Multiple Asset Expirations
1. Create 3 assets expiring in next 5 minutes
2. Users trade all 3 assets
3. Wait for expiration
4. Verify all settlements processed
5. Verify 3 new assets created

### Test 3: No Holdings at Expiration
1. Let asset expire with no user holdings
2. Verify no settlements created
3. Verify asset marked inactive
4. Verify replacement created

### Test 4: Edge Cases
- User holds multiple expired assets simultaneously
- Asset expires during active trading session
- Settlement with fractional shares
- Very short expiration (< 1 hour)
- Very long expiration (30 days)

## Rollback Procedure

If you need to rollback to fixed assets:

1. **Stop Application**
2. **Restore Database Backup**
3. **Revert Code Changes**:
   ```bash
   git revert <commit-hash>
   ```
4. **Remove New Files**:
   - `asset_manager.py`
   - `MIGRATION_EXPIRING_ASSETS.md`
5. **Restart Application**

## Configuration Options

### Environment Variables

```bash
# Minimum active assets to maintain
MIN_ACTIVE_ASSETS=10

# How often to check for expirations (seconds)
EXPIRATION_CHECK_INTERVAL=60

# Remove old expired assets after N days
CLEANUP_OLD_ASSETS_DAYS=30

# Initial price for new assets
INITIAL_ASSET_PRICE=100
```

### Customizing Asset Generation

Edit `Asset.create_new_asset()` in `models.py`:

```python
# Change symbol length (default 3)
symbol = Asset.generate_symbol(length=4)

# Change expiration range (default 1-30 days)
days_to_expiry = random.randint(7, 14)  # 1-2 weeks only

# Change volatility range (default 0.1%-20%)
volatility = random.uniform(0.01, 0.10)  # 1%-10% only
```

## Monitoring

### Key Metrics to Monitor

1. **Active Asset Count**: Should stay at MIN_ACTIVE_ASSETS
2. **Expiration Rate**: Track assets expiring per day
3. **Settlement Volume**: Total value settled
4. **Failed Settlements**: Any errors during settlement
5. **Price Service Sync**: Ensure new assets registered with price service

### Logging

Key log messages:

```
"Expiring asset ABC at price 102.34"
"Settled 10 units of ABC for user 5 at $102.34 = $1023.40"
"Created new asset XYZ with volatility 0.0543, expires in 15 days"
"Processing asset expirations... expired_assets=2, positions_settled=5"
```

## Troubleshooting

### Asset Count Dropping Below Minimum
**Symptom**: Fewer than MIN_ACTIVE_ASSETS active
**Cause**: Expiration thread not running or database error
**Fix**: Check logs, restart application

### Settlements Not Processing
**Symptom**: Assets marked expired but holdings not cleared
**Cause**: Error in settlement logic or database constraint
**Fix**: Check logs, manually trigger `asset_manager.process_expirations()`

### Price Service Out of Sync
**Symptom**: New assets have no price data
**Cause**: Asset not registered with fallback price service
**Fix**: Manually add to price service or restart application

### Old Assets Accumulating
**Symptom**: Database growing with expired assets
**Cause**: Cleanup not running
**Fix**: Manually run `asset_manager.cleanup_old_assets(days_old=30)`

## Performance Considerations

- **Database Queries**: Active assets filtered by `is_active=True` index
- **Settlement Processing**: Batched in single transaction
- **Price Updates**: Only active assets updated
- **Memory**: Fallback price service tracks only active symbols
- **Cleanup**: Runs automatically, cascade deletes settlements

## Security Considerations

- **Settlement Amounts**: Validated in database constraints
- **Asset Validation**: Trading restricted to active assets only
- **Price Manipulation**: Final price = current market price (from price service)
- **Double Settlement**: Asset `is_active` prevents re-settlement

## Future Enhancements

Potential improvements:
- Email notifications for approaching expirations
- User-configurable expiration alerts
- Historical analysis of expired assets
- Settlement tax implications tracking
- Configurable settlement delays (T+1, T+2)
- Asset creation scheduling (specific times)
- Premium/discount to initial price at creation
- Limit on total holdings per asset
- Early settlement option for users

## Support

For issues or questions:
1. Check logs in `martingale.log`
2. Review this migration guide
3. Test in development environment first
4. Check `/api/assets/summary` for system status
