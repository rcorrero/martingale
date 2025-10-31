# Expiring Assets System - Implementation Summary

## Overview

The Martingale trading platform has been successfully redesigned to support **dynamic expiring assets** that automatically settle and replace themselves. This addresses your requirements for:

1. ✅ Assets with predefined expiration dates
2. ✅ Varying time horizons (1 day to 1 month)
3. ✅ Automatic settlement at final price upon expiration
4. ✅ Automatic creation of new instruments to replace expiring ones
5. ✅ No assumptions about exact timing of creation/expiration

## Architecture Changes

### Core Components

1. **Asset Model** (`models.py`)
   - Tracks individual assets with expiration dates
   - Random symbol generation (3 uppercase letters)
   - Stores volatility, prices, timestamps
   - Lifecycle states: active → expired → settled

2. **AssetManager** (`asset_manager.py`)
   - Centralized lifecycle management
   - Creates new assets with random parameters
   - Processes expirations and settlements
   - Maintains minimum asset pool
   - Cleanup of old data

3. **Settlement Model** (`models.py`)
   - Records all automatic settlements
   - Links user, asset, quantity, price
   - Audit trail for cash returns

4. **Background Threads** (`app.py`)
   - Price updates: Every 1 second
   - Expiration checks: Every 60 seconds (configurable)

### Key Features

#### 1. Random Asset Generation
```python
# Each asset gets:
- Symbol: Random 3 letters (e.g., "KLM", "PQR")
- Initial Price: $100 (configurable)
- Volatility: Random 0.1% - 20%
- Expiration: Random 1-30 days from creation
```

#### 2. Automatic Settlement
When an asset expires:
1. Mark asset as inactive
2. Record final settlement price
3. For each user holding the asset:
   - Calculate settlement value (quantity × final_price)
   - Add cash to user's portfolio
   - Clear holdings and position info
   - Create settlement record
   - Add transaction with type='settlement'
4. Remove from price service
5. Emit WebSocket notification

#### 3. Automatic Replacement
After settlements:
- Count active assets
- If below minimum (default 10), create new assets
- Register new assets with price service
- No manual intervention required

#### 4. Dynamic Trading
- Only active (non-expired) assets are tradeable
- Asset validation on each trade
- Expired assets rejected with clear message
- Holdings automatically cleaned up on expiration

## File Changes Summary

### New Files Created
1. **`asset_manager.py`** - Asset lifecycle management (342 lines)
2. **`MIGRATION_EXPIRING_ASSETS.md`** - Complete migration guide (600+ lines)
3. **`test_expiring_assets.py`** - Test suite (300+ lines)
4. **`EXPIRING_ASSETS_SUMMARY.md`** - This file

### Modified Files
1. **`models.py`**
   - Added `Asset` model (120 lines)
   - Added `Settlement` model (30 lines)
   - Updated imports

2. **`app.py`**
   - Imported `AssetManager`, `Asset`, `Settlement`
   - Initialized `asset_manager`
   - Updated `get_user_portfolio()` - dynamic holdings
   - Updated `update_prices()` - filter to active assets
   - Updated `/api/assets` - include expiration info
   - Updated `/api/assets/history` - active assets only
   - Updated `/api/performance` - ignore expired assets
   - Updated `/api/open-interest` - active assets only
   - Added `/api/assets/summary` - lifecycle stats
   - Added `/api/settlements` - user settlement history
   - Updated `handle_trade()` - validate asset is active
   - Added `expiration_check_thread()` - background processor
   - Updated initialization - create initial asset pool

3. **`config.py`**
   - Added `MIN_ACTIVE_ASSETS = 10`
   - Added `EXPIRATION_CHECK_INTERVAL = 60`
   - Added `CLEANUP_OLD_ASSETS_DAYS = 30`
   - Marked legacy `ASSETS` as fallback only

4. **`price_client.py`**
   - Added `add_asset()` method to `FallbackPriceService`
   - Added `remove_asset()` method
   - Added `get_symbols()` method

## Database Schema

### New Tables

**`assets`**
```sql
id                INTEGER PRIMARY KEY
symbol            VARCHAR(10) UNIQUE NOT NULL
initial_price     FLOAT NOT NULL
current_price     FLOAT NOT NULL
volatility        FLOAT DEFAULT 0.02
created_at        DATETIME NOT NULL
expires_at        DATETIME NOT NULL
is_active         BOOLEAN DEFAULT TRUE
final_price       FLOAT
settled_at        DATETIME
```

**`settlements`**
```sql
id                INTEGER PRIMARY KEY
user_id           INTEGER FOREIGN KEY → users.id
asset_id          INTEGER FOREIGN KEY → assets.id
symbol            VARCHAR(10) NOT NULL
quantity          FLOAT NOT NULL
settlement_price  FLOAT NOT NULL
settlement_value  FLOAT NOT NULL
settled_at        DATETIME NOT NULL
```

### Indexes
- `assets.symbol` (UNIQUE)
- `assets.is_active`
- `assets.expires_at`
- `settlements.user_id`
- `settlements.asset_id`

## API Endpoints

### Modified
- **GET `/api/assets`** - Returns active assets with expiration info
- **GET `/api/assets/history`** - Filtered to active assets
- **GET `/api/performance`** - Ignores expired assets
- **GET `/api/open-interest`** - Active assets only

### New
- **GET `/api/assets/summary`** - Asset lifecycle statistics
- **GET `/api/settlements`** - User settlement history (requires login)

### WebSocket Events
- **`assets_updated`** - Emitted when assets expire/settle
- **`portfolio_update`** - Triggered after settlements

## Configuration

### Environment Variables
```bash
MIN_ACTIVE_ASSETS=10              # Minimum active assets
EXPIRATION_CHECK_INTERVAL=60      # Check frequency (seconds)
CLEANUP_OLD_ASSETS_DAYS=30        # Remove old assets after N days
INITIAL_ASSET_PRICE=100           # Starting price for new assets
```

### Customization Points

**Asset Generation** (`models.py:Asset.create_new_asset`):
- Symbol length (default: 3)
- Volatility range (default: 0.1% - 20%)
- Expiration range (default: 1-30 days)

**Settlement Timing** (`config.py`):
- Check interval (default: 60 seconds)
- Cleanup threshold (default: 30 days)

**Pool Size** (`config.py`):
- Minimum active assets (default: 10)

## Testing

### Running Tests
```bash
python test_expiring_assets.py
```

Tests cover:
- ✅ Asset creation with random parameters
- ✅ Asset expiration mechanics
- ✅ Settlement processing and cash returns
- ✅ AssetManager pool maintenance
- ✅ Full lifecycle (create → trade → expire → settle → replace)

### Manual Testing
```bash
# Start application
python app.py

# Check asset summary
curl http://localhost:5000/api/assets/summary

# Monitor logs for expiration events
tail -f martingale.log | grep -i "expir"
```

## Migration Path

### For New Installations
1. Run `python app.py` - automatically creates schema and initializes 10 assets
2. Assets start expiring after 1-30 days
3. System self-manages from there

### For Existing Installations
1. **Backup database**
2. Run application - new tables created automatically
3. Optional: Clear old holdings from fixed assets
4. Initial pool of 10 assets created
5. Old fixed asset config becomes unused (but safe to keep)

See `MIGRATION_EXPIRING_ASSETS.md` for detailed migration steps.

## Monitoring

### Key Metrics
- Active asset count (should stay ≥ MIN_ACTIVE_ASSETS)
- Expiration rate (assets/day)
- Settlement volume ($/day)
- Average time to expiry

### Log Messages to Watch
```
"Expiring asset ABC at price 102.34"
"Settled X units of ABC for user Y at $Z"
"Created new asset XYZ with volatility 0.05, expires in 15 days"
"Processing asset expirations... expired_assets=2, positions_settled=5"
```

### Health Checks
```bash
# Check active asset count
curl http://localhost:5000/api/assets/summary | jq '.active_count'

# Check recent settlements (requires auth)
curl -H "Cookie: session=..." http://localhost:5000/api/settlements

# Monitor price service sync
grep "Registered.*with price service" martingale.log
```

## Performance Impact

### Positive
- ✅ Smaller active dataset (only ~10 assets vs 11 fixed)
- ✅ Automatic cleanup of old data
- ✅ Indexed queries on `is_active` and `expires_at`

### Considerations
- Background thread runs every 60 seconds
- Settlement processing scales with number of users × holdings
- Database writes on each expiration/settlement
- Recommended: Monitor database size, consider archiving old settlements

## Security

### Implemented
- ✅ Final price = market price (no manipulation)
- ✅ Settlement amount validation in database
- ✅ Cannot trade expired assets
- ✅ Atomic transactions for settlements
- ✅ Audit trail via Settlement records

### Future Enhancements
- Settlement email notifications
- Configurable settlement delays (T+1, T+2)
- User expiration alerts
- Rate limiting on asset creation

## Limitations & Known Issues

### Current Limitations
1. **Frontend Not Updated**: UI still shows all symbols, no expiration countdown
2. **No User Notifications**: Settlements happen silently (only WebSocket event)
3. **Fixed Initial Price**: All assets start at $100
4. **Random Symbols**: May generate similar-looking symbols (e.g., "III")

### Future Improvements Needed
1. Update `main.js` to:
   - Display expiration countdown for each asset
   - Show settlement notifications
   - Hide/remove expired assets from trading UI
   - Highlight assets expiring soon
2. Add email/push notifications for:
   - Assets expiring in < 24 hours
   - Settlements completed
3. Allow configuration of:
   - Initial price range (not just $100)
   - Symbol format (e.g., prefix pattern)
   - Expiration schedules (e.g., only business days)

## Rollback Plan

If needed, rollback by:
1. Stop application
2. Restore database backup
3. `git revert` to previous commit
4. Remove new files (`asset_manager.py`, etc.)
5. Restart application

No data loss - old system compatible with same database structure (just ignores new tables).

## Next Steps

### Required (For Full Functionality)
1. **Update Frontend** - Add expiration display, settlement notifications
2. **Test Thoroughly** - Run for several expiration cycles
3. **Monitor Logs** - Watch for settlement errors

### Optional (Enhancements)
1. Email notifications for expirations
2. Configurable expiration schedules
3. Historical analysis dashboard
4. User preferences for alerts
5. Tax reporting for settlements

## Support & Documentation

- **Migration Guide**: `MIGRATION_EXPIRING_ASSETS.md`
- **Test Suite**: `test_expiring_assets.py`
- **Code Documentation**: Inline docstrings in all new code
- **API Docs**: See `MIGRATION_EXPIRING_ASSETS.md` section 5

## Summary

The system now fully supports expiring assets with:
- ✅ Automatic lifecycle management
- ✅ Random generation (symbols, volatility, expiration)
- ✅ Settlement at final market price
- ✅ Cash return to users
- ✅ Automatic replacement assets
- ✅ Complete audit trail
- ✅ No manual intervention required

**Backend is complete and functional.** Frontend updates recommended but not required for core functionality to work.
