# Quick Reference: Expiring Assets System

## Quick Start

### First Run (New Installation)
```bash
python app.py
# System automatically:
# - Creates database tables
# - Initializes 10 active assets
# - Starts price and expiration threads
```

### Check System Status
```bash
curl http://localhost:5000/api/assets/summary
```

Expected response:
```json
{
  "active_count": 10,
  "expired_unsettled_count": 0,
  "active_symbols": ["KLP", "FGH", "MNQ", ...]
}
```

## Key Concepts

### Asset States
1. **Active** - Tradeable, prices updating
2. **Expired** - Reached expiration date, settlement pending
3. **Settled** - Positions settled, cash returned, removed from trading

### Asset Lifecycle
```
CREATE → TRADE → EXPIRE → SETTLE → REPLACE
  ↓        ↓        ↓        ↓         ↓
Symbol   Prices   Stop     Return    New
Random   Update   Trading  Cash      Asset
```

## API Endpoints

### Get Active Assets
```bash
GET /api/assets
```
Returns: Asset prices + expiration info

### Get Asset Summary
```bash
GET /api/assets/summary
```
Returns: Lifecycle statistics

### Get Settlements (requires auth)
```bash
GET /api/settlements
```
Returns: User's settlement history

### Get Open Interest
```bash
GET /api/open-interest
```
Returns: Total holdings per active asset

## Configuration

### Environment Variables
```bash
MIN_ACTIVE_ASSETS=10              # Pool size
EXPIRATION_CHECK_INTERVAL=60      # Check every 60s
CLEANUP_OLD_ASSETS_DAYS=30        # Delete after 30 days
INITIAL_ASSET_PRICE=100           # Starting price
```

### Code Customization

**Change expiration range** (models.py, line 65):
```python
days_to_expiry = random.randint(7, 14)  # 1-2 weeks
```

**Change volatility range** (models.py, line 62):
```python
volatility = random.uniform(0.02, 0.08)  # 2%-8%
```

**Change symbol length** (models.py, line 40):
```python
symbol = ''.join(random.choices(string.ascii_uppercase, k=4))  # 4 letters
```

## Common Tasks

### Create Test Asset Expiring Soon
```python
from models import Asset, db
import datetime

asset = Asset(
    symbol="TST",
    initial_price=100.0,
    current_price=100.0,
    volatility=0.05,
    expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
    is_active=True
)
db.session.add(asset)
db.session.commit()

# Register with price service
from app import price_service
price_service.fallback.add_asset("TST", 100.0, 0.05)
```

### Manually Trigger Expiration Check
```python
from app import asset_manager
stats = asset_manager.process_expirations()
print(stats)
```

### View All Settlements
```python
from models import Settlement
settlements = Settlement.query.order_by(Settlement.settled_at.desc()).limit(10).all()
for s in settlements:
    print(f"{s.symbol}: {s.quantity} @ ${s.settlement_price} = ${s.settlement_value}")
```

### Clear All Expired Assets (cleanup)
```python
from app import asset_manager
count = asset_manager.cleanup_old_assets(days_old=0)  # Remove all
print(f"Removed {count} expired assets")
```

## Monitoring

### Check Logs for Expiration Events
```bash
tail -f martingale.log | grep -E "(Expiring|Settled|Created new asset)"
```

### Watch Active Asset Count
```bash
watch -n 5 'curl -s http://localhost:5000/api/assets/summary | jq .active_count'
```

### Monitor Settlement Volume
```python
from models import Settlement
from sqlalchemy import func

total = db.session.query(func.sum(Settlement.settlement_value)).scalar()
print(f"Total settled: ${total:,.2f}")
```

## Troubleshooting

### "Asset not available for trading"
**Cause**: Asset expired between load and trade
**Fix**: Refresh page, trade different asset

### Active asset count dropping
**Cause**: Expiration thread not running
**Check**: `ps aux | grep python`, look for background threads
**Fix**: Restart application

### Settlements not processing
**Cause**: Database error or constraint violation
**Check**: `tail martingale.log` for errors
**Fix**: Check database integrity, restart app

### Price service out of sync
**Cause**: New asset not registered with price fallback
**Check**: Compare asset symbols to price_service.fallback.assets.keys()
**Fix**: Restart app (auto-registers on init)

## Testing

### Run Full Test Suite
```bash
python test_expiring_assets.py
```

### Manual Test: Full Lifecycle
```bash
# 1. Start app
python app.py

# 2. Create short-lived asset (in Python shell)
# (see "Create Test Asset Expiring Soon" above)

# 3. Trade the asset (in browser or curl)
curl -X POST http://localhost:5000/api/trade \
  -H "Content-Type: application/json" \
  -d '{"symbol":"TST","type":"buy","quantity":10}'

# 4. Wait for expiration (5 minutes)

# 5. Check settlement
curl http://localhost:5000/api/settlements

# 6. Verify cash returned
curl http://localhost:5000/api/portfolio
```

## Database Schema

### Assets Table
```sql
symbol          VARCHAR(10) UNIQUE   -- "KLP", "FGH", etc.
initial_price   FLOAT                -- Starting price
current_price   FLOAT                -- Current market price
volatility      FLOAT                -- 0.001 to 0.20
created_at      DATETIME             -- Creation timestamp
expires_at      DATETIME             -- Expiration timestamp
is_active       BOOLEAN              -- Trading enabled?
final_price     FLOAT                -- Settlement price
settled_at      DATETIME             -- When settled
```

### Settlements Table
```sql
user_id          INTEGER FK          -- User who held position
asset_id         INTEGER FK          -- Expired asset
symbol           VARCHAR(10)         -- Asset symbol (denorm)
quantity         FLOAT               -- Units held
settlement_price FLOAT               -- Final price
settlement_value FLOAT               -- quantity × price
settled_at       DATETIME            -- Settlement timestamp
```

## Background Threads

### Price Update Thread
- **Frequency**: Every 1 second
- **Action**: Update prices for active assets
- **Emits**: `price_update`, `price_chart_update` WebSocket events

### Expiration Check Thread
- **Frequency**: Every 60 seconds (configurable)
- **Action**: 
  1. Find expired assets
  2. Settle user positions
  3. Create replacement assets
- **Emits**: `assets_updated`, `portfolio_update` WebSocket events

## Performance Tips

1. **Index Usage**: Queries use `is_active` and `expires_at` indexes
2. **Batch Processing**: Settlements processed in single transaction
3. **Cleanup**: Run cleanup regularly to prevent bloat
4. **Monitoring**: Track active count, should be stable at MIN_ACTIVE_ASSETS

## Security Notes

- Settlement amounts validated in database
- Final price = market price (no manipulation)
- Cannot trade expired assets (validated on each trade)
- Atomic transactions prevent partial settlements
- Audit trail via Settlement records

## File Reference

- **models.py** - Asset, Settlement models
- **asset_manager.py** - Lifecycle management
- **app.py** - API endpoints, background threads
- **config.py** - Configuration settings
- **test_expiring_assets.py** - Test suite

## WebSocket Events

### Emitted by Server
- `price_update` - Price changes for active assets
- `price_chart_update` - Individual asset price update
- `assets_updated` - Assets expired/settled (includes stats)
- `portfolio_update` - Trigger portfolio refresh
- `performance_update` - Trigger performance refresh

### Listened by Server
- `trade` - User trade request

## Support Resources

- **Full Documentation**: EXPIRING_ASSETS_SUMMARY.md
- **Migration Guide**: MIGRATION_EXPIRING_ASSETS.md
- **Test Suite**: test_expiring_assets.py
- **Code Comments**: Inline docstrings in all modules
