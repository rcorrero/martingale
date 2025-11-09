# Martingale Trading Platform - Detailed Architecture

**Note**: This document provides detailed technical architecture. For a quick overview, see [README.md](README.md).

## System Overview

Martingale is a full-stack web application implementing a paper trading platform with real-time price streaming, expiring asset contracts, and automatic position settlement. The architecture follows a modular design with clear separation of concerns between presentation, business logic, and data persistence layers.

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
│  Browser (HTML/CSS/JavaScript + Socket.IO + Chart.js)           │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTP/WebSocket (Socket.IO)
┌────────────────────────────┴─────────────────────────────────────┐
│                      Application Layer                           │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Flask Application (app.py)                                │  │
│  │  • Request routing and session management                  │  │
│  │  • WebSocket event handling                                │  │
│  │  • Authentication and authorization                        │  │
│  │  • Background threads (price updates, expirations)         │  │
│  └────────────────────────────────────────────────────────────┘  │
│  ┌────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │ AssetManager   │  │ PriceClient      │  │ Validators      │  │
│  │ (lifecycle)    │  │ (price service)  │  │ (input sanit.)  │  │
│  └────────────────┘  └──────────────────┘  └─────────────────┘  │
└────────────────────────────┬─────────────────────────────────────┘
                             │ SQLAlchemy ORM
┌────────────────────────────┴─────────────────────────────────────┐
│                      Data Layer                                  │
│  SQLite (dev) / PostgreSQL (prod)                               │
│  • Users, Portfolios, Assets, Transactions, Settlements         │
└──────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Flask Application (`app.py`)

The main application server handling HTTP requests and WebSocket connections.

**Key Responsibilities:**
- Route HTTP requests to appropriate handlers
- Manage user sessions with Flask-Login
- Handle WebSocket events for real-time trading
- Spawn and manage background threads
- Orchestrate business logic between components

**Background Threads:**
- **Price Update Thread**: Fetches prices every 1 second, broadcasts to clients
- **Expiration Check Thread**: Checks for expired assets every 60 seconds, processes settlements

**Authentication Flow:**
```
Client → /login → LoginForm validation → check_rate_limit()
  → User.check_password() → login_user() → redirect to /
```

### 2. Asset Manager (`asset_manager.py`)

Centralized service for managing asset lifecycle from creation to settlement.

**Key Methods:**
- `create_new_assets(count)` - Generate new random assets
- `check_and_expire_assets()` - Mark expired assets as inactive
- `settle_expired_positions()` - Process user holdings, return cash
- `maintain_asset_pool()` - Ensure minimum active assets exist
- `cleanup_old_assets(days)` - Remove expired assets beyond retention

**Asset Lifecycle:**
```
CREATE → ACTIVE → EXPIRED → SETTLED → ARCHIVED
   ↓        ↓         ↓         ↓         ↓
Symbol   Trading   Final    Cash     Cleanup
Random   Enabled   Price    Return   (30 days)
```

### 3. Price Service System

**HybridPriceService** (`price_client.py`)
- Dual-mode operation: API client or local fallback
- Automatic failover if price service unavailable
- **Database Sync at Startup**: Queries active assets and syncs drift/volatility parameters
- **Continuous Sync**: Updates asset parameters during each price update cycle

**PriceServiceClient**
- HTTP client for standalone price service (optional)
- Endpoints: `/health`, `/prices`, `/history`, `/assets`

**FallbackPriceService**
- Local Geometric Brownian Motion price generation
- **Database-driven Parameters**: Each asset uses unique drift (μ) and volatility (σ) from Asset table
- **Startup Initialization**: Replaces hardcoded config with database values at app startup
- **Dynamic Updates**: Syncs price, drift, and volatility for existing assets
- Formula: `dS = μS dt + σS dW` where μ and σ are per-asset from database

**Standalone Price Service** (`price_service.py`) - Optional
- Independent Flask service on port 5001
- Provides REST API for price data
- Can run separately for distributed deployments

### 4. Input Validation System (`validators.py`)

Comprehensive validation layer preventing financial exploits and injection attacks.

**Validator Classes:**
- **TradeValidator**: Quantity, price, trade value validation with Decimal precision
- **SymbolValidator**: Pattern matching, SQL injection protection, reserved word blocking
- **PortfolioValidator**: Cash balance, sufficient funds/holdings checking
- **QueryValidator**: Pagination limits, offset validation, user ID validation

**Key Features:**
- Uses Python's `Decimal` type for all financial calculations (8 decimal places)
- Rejects negative values, infinity, NaN, malformed inputs
- Enforces realistic bounds (quantities: 1e-8 to 1B, prices: $0.01 to 1B)
- Fails fast - validates before any business logic or database operations

**Validation Flow:**
```
User Input → Validator → Decimal Conversion → Bounds Check
  → Business Logic → Database Constraints → Success
```

### 5. Database Models (`models.py`)

SQLAlchemy ORM models with CHECK constraints for data integrity.

**Models:**
- **User**: Authentication (id, username, password_hash, created_at)
- **Portfolio**: Holdings (user_id, cash, holdings JSON, position_info JSON)
- **Asset**: Tradeable instruments (symbol, prices, volatility, drift, expiration, is_active)
- **Transaction**: Trade history (user_id, asset_id, type, quantity, price, timestamp)
- **Settlement**: Expired position records (user_id, asset_id, settlement_price, settled_at)
- **PriceData**: Price metadata (symbol, current_price, volatility, history JSON)

**Key Relationships:**
```
User 1:1 Portfolio
User 1:N Transaction
User 1:N Settlement
Asset 1:N Transaction
Asset 1:N Settlement
```

## Data Flow

### Trading Flow

```
1. Client emits 'trade' WebSocket event
   { symbol: 'XYZ', quantity: 10, action: 'buy' }
   
2. app.py handle_trade()
   ├─ Validate inputs (symbol, quantity, action)
   ├─ Check asset exists and is active
   ├─ Get current price from price service
   ├─ Validate trade value (quantity × price)
   └─ Check sufficient funds/holdings
   
3. Update database
   ├─ Modify portfolio.cash
   ├─ Update portfolio.holdings
   ├─ Calculate new VWAP
   └─ Create Transaction record
   
4. Broadcast updates
   ├─ Emit 'trade_result' to client
   ├─ Emit 'portfolio_update' to client
   └─ Add to global transactions feed
```

### Price Update Flow

```
1. Background thread (every 1 second)
   
2. price_service.get_current_prices()
   ├─ Try API call to standalone service
   └─ Fallback to local GBM generation
   
3. Update database
   ├─ Asset.current_price = new_price
   └─ PriceData.history.append()
   
4. Broadcast to all clients
   └─ emit('price_update', prices_dict)
```

### Expiration & Settlement Flow

```
1. Background thread (every 60 seconds)
   
2. AssetManager.process_expirations()
   ├─ Query assets where expires_at <= now()
   └─ For each expired asset:
   
3. Mark asset as expired
   ├─ Asset.is_active = False
   ├─ Asset.final_price = current_price
   └─ Asset.settled_at = now()
   
4. Settle user positions
   ├─ Query all portfolios with holdings
   └─ For each position:
       ├─ Calculate value = quantity × final_price
       ├─ Add cash to portfolio
       ├─ Clear holdings
       ├─ Create Settlement record
       └─ Create Transaction (type='settlement')
   
5. Maintain asset pool
   ├─ Count active assets
   ├─ If count < MIN_ACTIVE_ASSETS:
   └─ Create new assets to reach minimum
   
6. Broadcast updates
   ├─ emit('assets_updated')
   └─ emit('settlement_notification')
```

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL
);
```

### Portfolios Table
```sql
CREATE TABLE portfolios (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    cash FLOAT NOT NULL CHECK (cash >= 0 AND cash <= 100000000000),
    holdings TEXT NOT NULL,      -- JSON string
    position_info TEXT NOT NULL, -- JSON string
    updated_at DATETIME NOT NULL
);
```

### Assets Table
```sql
CREATE TABLE assets (
    id INTEGER PRIMARY KEY,
    symbol VARCHAR(10) UNIQUE NOT NULL,
    initial_price FLOAT NOT NULL CHECK (initial_price > 0),
    current_price FLOAT NOT NULL CHECK (current_price > 0),
    volatility FLOAT NOT NULL CHECK (volatility >= 0 AND volatility <= 1),
    drift FLOAT NOT NULL DEFAULT 0.0,
    color VARCHAR(7) NOT NULL,
    created_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    final_price FLOAT CHECK (final_price >= 0),
    settled_at DATETIME
);

CREATE INDEX idx_assets_is_active ON assets(is_active);
CREATE INDEX idx_assets_expires_at ON assets(expires_at);
```

### Transactions Table
```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    symbol VARCHAR(10) NOT NULL,  -- Denormalized for query performance
    timestamp FLOAT NOT NULL,
    type VARCHAR(10) NOT NULL CHECK (type IN ('buy', 'sell', 'settlement')),
    quantity FLOAT NOT NULL CHECK (quantity > 0),
    price FLOAT NOT NULL CHECK (price >= 0),
    total_cost FLOAT NOT NULL CHECK (total_cost >= 0),
    created_at DATETIME NOT NULL
);

CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_asset_id ON transactions(asset_id);
```

### Settlements Table
```sql
CREATE TABLE settlements (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    symbol VARCHAR(10) NOT NULL,
    quantity FLOAT NOT NULL CHECK (quantity > 0),
    settlement_price FLOAT NOT NULL CHECK (settlement_price >= 0),
    settlement_value FLOAT NOT NULL CHECK (settlement_value >= 0),
    settled_at DATETIME NOT NULL
);

CREATE INDEX idx_settlements_user_id ON settlements(user_id);
CREATE INDEX idx_settlements_asset_id ON settlements(asset_id);
```

## Security Architecture

### Defense in Depth

The application implements multiple layers of security:

**Layer 1: Input Validation**
- All user inputs validated before processing
- Decimal precision prevents float exploits
- Bounds checking prevents overflow attacks
- Pattern matching blocks injection attempts

**Layer 2: Business Logic**
- Trade validation (asset exists, is active, sufficient funds)
- Portfolio constraints (no negative cash, realistic limits)
- Rate limiting (5 login attempts per 5 minutes)

**Layer 3: Database Constraints**
- CHECK constraints enforce data rules
- Foreign keys ensure referential integrity
- Unique constraints prevent duplicates
- NOT NULL constraints prevent missing data

**Layer 4: Authentication & Authorization**
- Flask-Login session management
- Scrypt password hashing
- HttpOnly cookies (XSS protection)
- SameSite cookies (CSRF protection)
- 1-hour session timeout

### Threat Model

**Prevented Attacks:**
- ✅ SQL Injection (ORM + validators)
- ✅ XSS (HttpOnly cookies, template escaping)
- ✅ CSRF (Flask-WTF tokens)
- ✅ Brute Force (rate limiting)
- ✅ Integer Overflow (Decimal precision, bounds checking)
- ✅ Negative Balance (validation + CHECK constraints)
- ✅ Session Hijacking (secure cookies, timeouts)

## Performance Considerations

### Database Optimization

- **Indexes**: Created on frequently queried columns (is_active, expires_at, user_id)
- **Denormalization**: Symbol stored in transactions for fast lookups
- **JSON Storage**: Holdings and position_info stored as JSON for flexibility
- **Connection Pooling**: SQLAlchemy handles connection management

### Caching Strategy

- **Price Data**: Cached in memory during active trading
- **Portfolio State**: Loaded once per request, updated transactionally
- **Asset List**: Active assets cached, refreshed on expiration events

### Scalability

**Current Limits:**
- Users: Unlimited (database-limited)
- Concurrent WebSocket: ~1000 per process (SocketIO)
- Active Assets: 16 (configurable)
- Transaction History: Unlimited with pagination

**Scaling Options:**
- Horizontal: Multiple Gunicorn workers behind load balancer
- Vertical: Increase worker count, database resources
- Caching: Add Redis for session storage, price data
- CDN: Serve static assets from CDN

## Configuration Management

### Environment-Based Config (`config.py`)

**DevelopmentConfig:**
- DEBUG = True
- SQLite database
- Verbose logging
- No HTTPS requirement

**ProductionConfig:**
- DEBUG = False
- PostgreSQL database
- Secure cookies (HTTPS only)
- Session cookie secure flags
- Error logging to stdout (Heroku-compatible)

### Configuration Hierarchy
```
1. Environment variables (highest priority)
2. .env file
3. config.py defaults
4. Hardcoded fallbacks (lowest priority)
```

## Deployment Architecture

### Development
```
Local Machine
├─ SQLite database (instance/martingale.db)
├─ Flask development server (port 5000)
└─ Optional: Standalone price service (port 5001)
```

### Production (Heroku)
```
Heroku Dyno
├─ Gunicorn WSGI server (eventlet worker)
├─ Flask application
└─ PostgreSQL database (Heroku Postgres addon)
    
Release Phase:
└─ init_heroku_db.py (schema initialization)
```

## Monitoring & Observability

### Logging

**Log Levels:**
- INFO: Normal operations (logins, trades, expirations)
- WARNING: Validation failures, rate limits
- ERROR: Database errors, service failures
- DEBUG: Detailed execution traces (development only)

**Log Destinations:**
- Development: `martingale.log` + stdout
- Production: stdout (Heroku log aggregation)

### Key Metrics to Monitor

**Application Health:**
- Active WebSocket connections
- Request latency (avg, p95, p99)
- Error rate (4xx, 5xx)
- Background thread status

**Business Metrics:**
- Active users count
- Total trades per minute
- Active assets count
- Settlement volume

**Database Metrics:**
- Connection pool utilization
- Query execution time
- Table sizes
- Index usage

## Testing Strategy

### Unit Tests
- `test_validators.py` - Input validation (57 tests)
- `test_drift_implementation.py` - GBM price generation
- `test_martingale_property.py` - Statistical properties

### Integration Tests
- `test_expiring_assets.py` - Asset lifecycle end-to-end
- `services_startup_test.py` - Service health checks

### Test Coverage

**Covered:**
- Input validation edge cases
- Asset lifecycle (create → expire → settle → replace)
- Price generation algorithms
- Authentication flows

**Not Covered:**
- WebSocket event handling
- Frontend JavaScript
- Concurrent trading scenarios
- Load testing

## Future Enhancements

### Planned Features
- Email notifications for expirations
- Two-factor authentication (2FA)
- API rate limiting per user
- Real-time portfolio streaming
- Mobile app (React Native)

### Technical Debt
- Migrate float columns to NUMERIC/DECIMAL
- Add database migration framework (Alembic)
- Implement comprehensive logging strategy
- Add API documentation (OpenAPI/Swagger)
- Improve test coverage (target: 80%+)

## References

- **Flask Documentation**: https://flask.palletsprojects.com/
- **SQLAlchemy Documentation**: https://docs.sqlalchemy.org/
- **Socket.IO Documentation**: https://socket.io/docs/
- **Chart.js Documentation**: https://www.chartjs.org/docs/

---

**Last Updated**: November 2025  
**Version**: 2.0