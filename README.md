# Martingale Trading Platform

A sophisticated paper trading web application that simulates real-time asset trading with virtual money. Built with Flask, SocketIO, SQLAlchemy, and Chart.js for an interactive, production-ready trading experience.

## Overview

Martingale is a full-featured paper trading platform that simulates futures-style contracts with expiring assets. The system automatically manages asset lifecycles, settles positions at expiration, and maintains a dynamic pool of tradeable instruments. Designed with production-level security, input validation, and real-time price streaming.

## Core Features

### Trading & Markets
- **Real-time Price Updates**: WebSocket-based streaming price data with 1-second updates
- **Dynamic Asset Pool**: System maintains minimum of 16 active tradeable assets
- **Expiring Assets**: Each asset has a random expiration time (5-30 minutes) for fast-paced gameplay
- **Geometric Brownian Motion**: Price evolution with configurable drift and volatility
- **VWAP Tracking**: Volume-weighted average price calculation per user position

### Portfolio Management
- **Multi-user Support**: Concurrent trading with isolated user portfolios
- **Position Tracking**: Quantity, VWAP, unrealized P&L per asset
- **Settlement History**: Complete audit trail of expired positions
- **Performance Analytics**: Realized/unrealized P&L, total return, portfolio value history
- **Transaction History**: Complete trade log with timestamps and settlement records

### Asset Lifecycle Management
- **Automatic Expiration**: Background thread monitors and expires assets
- **Position Settlement**: Holdings automatically converted to cash at final price
- **Auto-Replacement**: New assets created to maintain minimum pool size
- **Worthless Asset Detection**: Early settlement for assets below price threshold
- **Cleanup System**: Removes old expired assets after configurable retention period

### Security & Validation
- **Input Validation**: Comprehensive validation system with Decimal precision for financial calculations
- **Rate Limiting**: Login attempt throttling (5 attempts per 5 minutes)
- **Password Security**: Scrypt hashing with 8+ character minimum
- **Session Management**: HttpOnly cookies, CSRF protection, 1-hour timeout
- **SQL Injection Protection**: Parameterized queries via SQLAlchemy ORM
- **Database Constraints**: CHECK constraints for data integrity at the database level

### User Experience
- **Responsive Design**: Mobile-optimized interface with touch-friendly controls
- **Real-time Updates**: WebSocket notifications for price changes and settlements
- **Interactive Charts**: Chart.js visualizations with historical price data
- **Portfolio Pie Chart**: Visual breakdown of holdings by asset
- **Global Leaderboard**: Compare performance with other traders
- **Color-coded Assets**: Each asset assigned unique color for visual identification

## Installation & Setup

### Prerequisites

- Python 3.11 or higher (tested on 3.11.x)
- pip (Python package installer)
- Virtual environment (recommended)
- PostgreSQL (for production) or SQLite (for development)

### Quick Start (Development)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/martingale.git
   cd martingale
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings (SECRET_KEY, etc.)
   ```

5. **Initialize the database:**
   ```bash
   python init_database.py --env development
   ```
   This will:
   - Create all database tables (users, portfolios, assets, transactions, settlements)
   - Seed price metadata from config
   - Create initial pool of 16 active expiring assets

6. **Run the application:**
   ```bash
   python app.py
   ```

7. **Access the application:**
   ```
   http://localhost:5000
   ```

### Alternative: Start All Services

If you want to run the optional standalone price service alongside the main app:

```bash
python start_services.py
```

This starts:
- Price service on port 5001 (optional, app has fallback)
- Main application on port 5000

**Note**: The app works fine without the price service - it uses local fallback price generation.

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
# Security (REQUIRED in production)
SECRET_KEY=your-super-secret-key-change-in-production

# Flask Environment
FLASK_ENV=development              # 'development' or 'production'
FLASK_DEBUG=True                   # Debug mode (disable in production)

# Database
DATABASE_URL=sqlite:///instance/martingale.db  # SQLite for dev
# DATABASE_URL=postgresql://user:pass@host:5432/dbname  # PostgreSQL for prod

# Trading Configuration
INITIAL_CASH=100000               # Starting cash for new users
INITIAL_ASSET_PRICE=100           # Base price for new assets

# Asset Lifecycle
MIN_ACTIVE_ASSETS=16              # Minimum active assets in pool
EXPIRATION_CHECK_INTERVAL=60      # Seconds between expiration checks
CLEANUP_OLD_ASSETS_DAYS=30        # Remove expired assets after N days

# Price Service (optional)
PRICE_SERVICE_URL=http://localhost:5001  # Standalone price service URL
```

### Configuration Classes

The application uses environment-based configuration (see `config.py`):

- **DevelopmentConfig**: Debug enabled, SQLite database, verbose logging
- **ProductionConfig**: Debug disabled, PostgreSQL, secure cookies, HTTPS enforcement

Configuration automatically selected based on `FLASK_ENV` environment variable.

## Usage

1. **Register/Login**: Create an account or log in with existing credentials
2. **View Markets**: See real-time prices for available assets
3. **Place Trades**: Enter symbol and quantity to buy/sell assets
4. **Monitor Portfolio**: Track your holdings and performance in real-time
5. **Analyze Performance**: View detailed P&L analytics and transaction history

## Architecture

### Data Model Design

**Asset Identification**: The system uses **integer asset IDs** as the primary reference for all internal operations:

- **Holdings**: Stored as `{asset_id: quantity}` JSON mapping (not by symbol)
- **Transactions**: Reference assets via `asset_id` foreign key
- **Settlements**: Reference assets via `asset_id` foreign key
- **Backward Compatibility**: Legacy `symbol` columns preserved for compatibility
- **User Display**: Symbols shown in UI, but IDs used internally

**Benefits**:
- Unambiguous asset references (IDs never change)
- Prevents race conditions from symbol reuse
- Proper database foreign key relationships
- Faster lookups via indexed integer primary keys

### System Components

The Martingale platform follows a modular architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Browser                           │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐    │
│  │   HTML/CSS  │  │ JavaScript   │  │   Chart.js           │    │
│  │  Templates  │  │   (main.js)  │  │   Visualizations     │    │
│  └─────────────┘  └──────────────┘  └──────────────────────┘    │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTP/WebSocket
┌──────────────────────┴──────────────────────────────────────────┐
│                      Flask Application                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                       app.py                               │ │
│  │  • WebSocket event handlers (SocketIO)                     │ │
│  │  • REST API endpoints                                      │ │
│  │  • Authentication & session management (Flask-Login)       │ │
│  │  • Background threads (price updates, expiration checks)   │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────┐    ┌─────────────────────────────────┐  │
│  │  AssetManager      │    │     PriceClient                 │  │
│  │  • Lifecycle mgmt  │    │     • Hybrid price service      │  │
│  │  • Expiration      │◄───┤     • API client + fallback     │  │
│  │  • Settlement      │    │     • GBM price generation      │  │
│  │  • Pool maint.     │    └─────────────────────────────────┘  │
│  └────────────────────┘                                         │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Validators                              │ │
│  │  • TradeValidator    • SymbolValidator                     │ │
│  │  • PortfolioValidator • QueryValidator                     │ │
│  │  • Decimal precision  • SQL injection protection           │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────────────────┘
                       │ SQLAlchemy ORM
┌──────────────────────┴────────────────────────────────────────┐
│                     Database Layer                            │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌─────────────┐   │
│  │  Users   │  │ Portfolio │  │  Assets  │  │Transactions │   │
│  ├──────────┤  ├───────────┤  ├──────────┤  ├─────────────┤   │
│  │ id (PK)  │  │ user_id   │  │ id (PK)  │  │ user_id     │   │
│  │ username │  │ cash      │  │ symbol   │  │ asset_id(FK)│   │
│  │ pass_hash│  │ holdings* │  │ price    │  │ quantity    │   │
│  │ created  │  │ updated   │  │ expires  │  │ price       │   │
│  └──────────┘  └───────────┘  │ volatility│ │ type        │   │
│                               │ drift    │  │ timestamp   │   │
│                               │ is_active│  │ symbol**    │   │
│  ┌──────────┐  ┌───────────┐  └──────────┘  └─────────────┘   │
│  │PriceData │  │Settlement │                                  │
│  ├──────────┤  ├───────────┤  SQLite (dev) / PostgreSQL (prod)│
│  │ symbol   │  │ user_id   │  *holdings: {asset_id: quantity} │
│  │ current  │  │ asset_id  │  **symbol: legacy compatibility  │
│  │ history  │  │ quantity  │                                  │
│  │ updated  │  │ price     │                                  │
│  └──────────┘  └───────────┘                                  │
└───────────────────────────────────────────────────────────────┘
```

### Background Processes

The application runs two daemon threads for continuous operation:

1. **Price Update Thread**
   - Frequency: Every 1 second
   - Fetches prices from price service (or generates locally)
   - Updates database with new price points
   - Broadcasts updates to all connected clients via WebSocket
   - Limits history to prevent unbounded growth

2. **Expiration Check Thread**
   - Frequency: Every 60 seconds (configurable)
   - Queries database for expired assets
   - Settles all user positions at final price
   - Creates replacement assets to maintain minimum pool
   - Cleans up old expired assets beyond retention period

## Technology Stack

### Backend
- **Flask 3.x**: Web framework with application factory pattern
- **Flask-SocketIO**: WebSocket support for real-time communication
- **Flask-Login**: User session management and authentication
- **Flask-SQLAlchemy**: ORM for database interactions
- **Flask-WTF**: Form handling and CSRF protection
- **Werkzeug**: Password hashing (scrypt algorithm)
- **SQLAlchemy**: Database toolkit with CHECK constraints

### Frontend
- **HTML5/CSS3**: Responsive terminal-themed UI
- **JavaScript (ES6+)**: Client-side logic and WebSocket handling
- **Chart.js 4.x**: Real-time price charts and portfolio visualization
- **Socket.IO Client**: WebSocket client library

### Database
- **SQLite**: Development and testing
- **PostgreSQL**: Production deployment (Heroku compatible)
- **Migrations**: Automated schema updates with backward compatibility
- **Asset ID Consistency**: All internal operations use integer asset IDs for unambiguous references
  - Holdings stored by asset ID (not symbol)
  - Transactions/settlements reference assets via foreign keys
  - Backward compatible with legacy symbol-based data

### Pricing System
- **HybridPriceService**: Dual-mode price generation
  - API mode: Uses dedicated price service (optional)
  - Fallback mode: Local Geometric Brownian Motion generation
  - **Database Sync**: Automatically syncs drift and volatility from database at startup
  - **Asset Parameters**: Each asset has unique drift (μ) and volatility (σ) from database
- **GBM Algorithm**: `dS = μS dt + σS dW` with per-asset drift and volatility
- **Price History**: Stored in database with configurable retention

## Project Structure

```
martingale/
├── Core Application
│   ├── app.py                      # Flask app, API routes, WebSocket handlers
│   ├── config.py                   # Environment-based configuration
│   ├── models.py                   # SQLAlchemy models (User, Portfolio, Asset, etc.)
│   ├── asset_manager.py            # Asset lifecycle orchestration
│   ├── price_client.py             # Hybrid price service (API + fallback)
│   ├── price_service.py            # Standalone price generation service (optional)
│   ├── validators.py               # Input validation with Decimal precision
│   └── start_services.py           # Startup script for all services
│
├── Database Management
│   ├── init_database.py            # Unified schema initialization CLI
│   ├── init_db.py                  # Legacy entry point (delegates to init_database)
│   ├── init_heroku_db.py           # Heroku-specific initialization
│   ├── migrate_add_drift.py        # Migration: Add drift column
│   ├── migrate_add_color.py        # Migration: Add color column
│   └── migrate_password_hash.py    # Migration: Update password hashing
│
├── Testing & Validation
│   ├── test_expiring_assets.py     # Asset lifecycle tests
│   ├── test_drift_implementation.py # GBM drift tests
│   ├── test_martingale_property.py # Martingale property verification
│   ├── test_validators.py          # Input validation tests (57 tests)
│   └── services_startup_test.py    # Service health checks
│
├── Deployment
│   ├── Procfile                    # Heroku process definition
│   ├── runtime.txt                 # Python version specification
│   ├── requirements.txt            # Production dependencies
│   ├── requirements-prod.txt       # Additional production packages
│   ├── deploy.sh                   # Deployment automation script
│   └── cleanup-data.sh             # Database cleanup utility
│
├── Documentation
│   ├── README.md                   # This file
│   ├── README_ARCHITECTURE.md      # Detailed architecture documentation
│   ├── SECURITY.md                 # Security features and best practices
│   ├── EXPIRING_ASSETS_SUMMARY.md  # Asset lifecycle system documentation
│   ├── MIGRATION_EXPIRING_ASSETS.md # Migration guide for expiring assets
│   ├── DRIFT_IMPLEMENTATION.md     # GBM drift implementation details
│   ├── VALIDATION_ARCHITECTURE.md  # Input validation system documentation
│   ├── DEPLOYMENT.md               # Deployment checklist
│   ├── DEPLOYMENT_READY.md         # Production readiness status
│   ├── PRODUCTION_CHECKLIST.md     # Pre-launch verification
│   ├── PRODUCTION-STATUS.md        # Current production status
│   ├── QUICK_DEPLOY.md             # Quick deployment guide
│   ├── QUICK_REFERENCE.md          # API quick reference
│   ├── MOBILE_VWAP_FEATURE.md      # Mobile VWAP implementation
│   └── CONTRIBUTING.md             # Contribution guidelines
│
├── Frontend
│   ├── templates/
│   │   ├── index.html              # Main trading interface
│   │   ├── login.html              # User login page
│   │   ├── register.html           # User registration page
│   │   └── about.html              # About/info page
│   └── static/
│       ├── css/
│       │   └── style.css           # Terminal-themed styling
│       ├── js/
│       │   └── main.js             # WebSocket client, charts, UI logic
│       └── [favicon files]         # Site icons
│
├── Data & Assets
│   ├── instance/                   # SQLite database directory (dev)
│   │   └── martingale.db           # Development database
│   └── notebooks/                  # Jupyter analysis notebooks
│       └── inspect_martingale.ipynb
│
└── Configuration
    ├── .env                        # Environment variables (local, not in git)
    ├── .env.example                # Environment variables template
    ├── .gitignore                  # Git ignore patterns
    ├── app.json                    # Heroku app configuration
    └── LICENSE                     # MIT License
```

## API Reference

### Public Endpoints

- `GET /` - Main trading interface (requires login)
- `GET /login` - User login page
- `POST /login` - Authenticate user
- `GET /register` - User registration page
- `POST /register` - Create new user account
- `GET /logout` - Log out current user
- `GET /about` - About page

### Authenticated API Endpoints

All require valid session cookie:

#### Portfolio & Performance
- `GET /api/portfolio` - User's current portfolio (holdings, cash, positions)
- `GET /api/performance` - P&L metrics (realized/unrealized, total return)
- `GET /api/performance/history` - Historical portfolio value snapshots
- `GET /api/transactions` - User's transaction history
- `GET /api/settlements` - User's settlement history (expired positions)

#### Market Data
- `GET /api/assets` - Active tradeable assets with prices and expiration
- `GET /api/assets/history?symbol=XYZ` - Price history for specific asset
- `GET /api/assets/summary` - Asset pool statistics (active/expired counts)
- `GET /api/open-interest` - Open interest per asset across all users

#### Global Data
- `GET /api/transactions/all` - Global transaction feed (all users)
- `GET /api/leaderboard` - Top traders by total P&L

### WebSocket Events

Client → Server:
- `trade` - Execute buy/sell order
  ```javascript
  socket.emit('trade', {
    symbol: 'XYZ',
    quantity: 10.5,
    action: 'buy'  // or 'sell'
  });
  ```

Server → Client:
- `price_update` - Real-time price updates (1s interval)
- `portfolio_update` - Portfolio changed (trade executed, settlement)
- `trade_result` - Trade execution result (success/error)
- `assets_updated` - Asset pool changed (expiration, new assets)
- `asset_expiring_soon` - Asset approaching expiration warning
- `settlement_notification` - Position was settled

## Development

### Running Tests

The Martingale project includes a comprehensive test suite with over 200+ tests covering models, business logic, API endpoints, and integration scenarios. Tests use pytest for test discovery and execution.

#### Prerequisites

Install test dependencies:
```bash
pip install pytest pytest-cov pytest-flask
```

#### Quick Test Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest test_models.py -v

# Run specific test class
pytest test_models.py::TestUserModel -v

# Run specific test
pytest test_models.py::TestUserModel::test_create_user -v

# Run tests matching pattern
pytest -k "validation" -v

# Run with coverage report
pytest --cov=. --cov-report=html

# Run tests and stop on first failure
pytest -x
```

#### Test Suite Organization

##### 1. Model Tests (`test_models.py`)
Tests database models, relationships, and constraints:
- **User Model**: Authentication, password hashing, cascade deletes
- **Portfolio Model**: Holdings management, serialization, cash constraints
- **Transaction Model**: CRUD operations, constraints, relationships
- **Asset Model**: Lifecycle methods, expiration, symbol generation
- **Settlement Model**: Settlement records, cascade behavior
- **Database Constraints**: Integrity checks, foreign keys

```bash
# Run all model tests
pytest test_models.py -v

# Run specific model tests
pytest test_models.py::TestUserModel -v
pytest test_models.py::TestPortfolioModel -v
pytest test_models.py::TestAssetModel -v
```

##### 2. Asset Manager Tests (`test_asset_manager.py`)
Tests asset lifecycle management:
- **Initialization**: Configuration, service dependencies
- **Asset Queries**: Active/expired/worthless asset retrieval
- **Expiration Processing**: Time-based and price-based expiration
- **Settlement**: Position settlement, cash return, transaction creation
- **Pool Maintenance**: Automatic asset replacement
- **Cleanup**: Old asset removal

```bash
# Run all asset manager tests
pytest test_asset_manager.py -v

# Run specific test groups
pytest test_asset_manager.py::TestAssetExpiration -v
pytest test_asset_manager.py::TestPositionSettlement -v
```

##### 3. Application Tests (`test_app.py`)
Tests Flask application endpoints and business logic:
- **Authentication**: Registration, login, logout, rate limiting
- **Portfolio Endpoints**: Portfolio data, holdings, performance
- **Transaction Endpoints**: History, pagination, global feed
- **Asset Endpoints**: Market data, price history, open interest
- **Performance Calculations**: P&L, portfolio value, returns
- **Input Validation**: SQL injection, XSS, parameter validation
- **Error Handling**: Invalid inputs, unauthorized access

```bash
# Run all application tests
pytest test_app.py -v

# Run authentication tests
pytest test_app.py::TestAuthentication -v

# Run API endpoint tests
pytest test_app.py::TestPortfolioEndpoints -v
pytest test_app.py::TestAssetEndpoints -v
```

##### 4. Validator Tests (`test_validators.py`)
Tests comprehensive input validation (57 tests):
- **Trade Validation**: Quantity, price, trade value, type validation
- **Symbol Validation**: Pattern matching, SQL injection protection
- **Portfolio Validation**: Cash balance, sufficient funds/holdings
- **Query Validation**: Pagination parameters, user IDs
- **Edge Cases**: Infinity, NaN, negative values, precision
- **Helper Functions**: Decimal conversion, safe parsing

```bash
# Run all validation tests
pytest test_validators.py -v

# Run specific validator tests
pytest test_validators.py::TestTradeValidator -v
pytest test_validators.py::TestSymbolValidator -v
```

##### 5. Integration Tests (`test_integration.py`)
Tests end-to-end workflows:
- **User Workflows**: Registration → trading → settlement
- **Asset Lifecycle**: Creation → expiration → replacement
- **Multi-User Scenarios**: Concurrent trading, competing traders
- **Performance Calculations**: With real trading data
- **Data Integrity**: Cash balance validity, no negative holdings
- **Concurrent Operations**: Simultaneous settlements, transactions

```bash
# Run all integration tests
pytest test_integration.py -v

# Run specific workflow tests
pytest test_integration.py::TestCompleteUserWorkflow -v
pytest test_integration.py::TestAssetLifecycleWorkflow -v
```

##### 6. Legacy Tests
Additional test files for specific features:
```bash
# Asset expiration tests
python test_expiring_assets.py

# Martingale property verification
python test_martingale_property.py

# Drift implementation tests
python test_drift_implementation.py

# Service health checks
python services_startup_test.py
```

#### Test Coverage

Generate coverage reports:
```bash
# HTML coverage report (opens in browser)
pytest --cov=. --cov-report=html
open htmlcov/index.html

# Terminal coverage report
pytest --cov=. --cov-report=term-missing

# Coverage for specific modules
pytest --cov=models --cov=validators --cov=asset_manager --cov-report=html
```

Target coverage goals:
- **Models**: >90% coverage
- **Validators**: >95% coverage (critical for security)
- **Asset Manager**: >85% coverage
- **Application Routes**: >80% coverage

#### Test Configuration

Tests use `conftest.py` for shared fixtures:
- **Test Database**: In-memory SQLite for isolation
- **Test Client**: Flask test client with authentication
- **Mock Services**: Price service and SocketIO mocks
- **Data Generators**: Helper functions for creating test data
- **Fixtures**: Users, portfolios, assets, transactions, settlements

Common fixtures:
```python
# Basic fixtures
test_user                  # User without portfolio
test_user_with_portfolio   # User with empty portfolio
multiple_users             # 3 users with portfolios

# Asset fixtures
test_asset                 # Single active asset
multiple_assets            # 5 active assets
expired_asset              # Already expired asset
worthless_asset            # Price below threshold

# Portfolio fixtures
user_with_holdings         # User with 100 shares
buy_transaction            # Sample buy transaction
sell_transaction           # Sample sell transaction
settlement_record          # Sample settlement

# Service fixtures
mock_price_service         # Mock price service
mock_socketio              # Mock SocketIO
authenticated_client       # Pre-authenticated test client
```

#### Running Tests in CI/CD

Example GitHub Actions workflow:
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest --cov=. --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

#### Test Best Practices

When writing new tests:
1. **Isolation**: Each test should be independent
2. **Clear Names**: Use descriptive test names (test_what_when_then)
3. **Fixtures**: Use fixtures for setup/teardown
4. **Assertions**: Be specific about expected values
5. **Edge Cases**: Test boundary conditions and error paths
6. **Documentation**: Add docstrings explaining test purpose
7. **Cleanup**: Tests should clean up after themselves
8. **Speed**: Keep tests fast (use in-memory database)

#### Debugging Tests

```bash
# Run with print statements visible
pytest -s

# Run with debugger on failure
pytest --pdb

# Show local variables on failure
pytest -l

# Verbose traceback
pytest --tb=long

# Only show failed tests
pytest --failed-first

# Re-run only failed tests from last run
pytest --lf
```

### Database Management

#### Initialize/Reset Database
```bash
# Full reset (drops tables, reseeds data, creates asset pool)
python init_database.py --env development

# Non-destructive (only create missing tables/assets)
python init_database.py --env development --no-reset

# Skip asset pool creation
python init_database.py --env development --skip-asset-seed
```

#### Run Migrations
```bash
# Add drift column to existing assets
python migrate_add_drift.py

# Add color column to assets
python migrate_add_color.py

# Update password hashing algorithm
python migrate_password_hash.py
```

#### Flask Shell Operations
```bash
flask shell

>>> from models import db, User, Asset, Portfolio, Transaction
>>> 
>>> # Check active assets
>>> Asset.query.filter_by(is_active=True).count()
16
>>> 
>>> # Look up asset by ID (preferred) or symbol (fallback)
>>> asset = Asset.get_by_id_or_symbol(asset_id=42)
>>> asset = Asset.get_by_id_or_symbol(symbol='XYZ')  # Fallback
>>> 
>>> # View user portfolios (holdings use asset IDs)
>>> portfolio = Portfolio.query.first()
>>> holdings = portfolio.get_holdings_map()  # {asset_id: quantity}
>>> 
>>> # Get asset from user's holdings
>>> asset = portfolio.get_asset_from_holdings(asset_id=42)
>>> 
>>> # Force expire an asset (for testing)
>>> from datetime import datetime, timedelta, timezone
>>> asset = Asset.get_by_id_or_symbol(symbol='XYZ')
>>> asset.expires_at = datetime.now(timezone.utc).replace(tzinfo=None)
>>> db.session.commit()
```

### Monitoring & Debugging

#### Check Asset Statistics
```bash
curl http://localhost:5000/api/assets/summary | jq
```

Response:
```json
{
  "active_count": 16,
  "expired_unsettled_count": 0,
  "expired_settled_count": 23,
  "average_ttl_hours": 360.5,
  "active_symbols": ["ABC", "DEF", ...],
  "expiring_soon": [...]
}
```

#### Watch Real-time Logs
```bash
# Follow application logs
tail -f martingale.log

# Filter for specific events
tail -f martingale.log | grep -i "expir"      # Expirations
tail -f martingale.log | grep -i "settlement" # Settlements
tail -f martingale.log | grep -i "ERROR"      # Errors
```

#### Price Service Health Check
```bash
# If running standalone price service
curl http://localhost:5001/health
```

### Customizing Asset Generation

Edit `Asset.create_new_asset()` in `models.py`:

```python
# Change expiration range (default 5-30 minutes)
minutes_to_expiry = random.randint(10, 20)  # 10-20 minutes only

# Change volatility range (default 0.1%-20%)
volatility = random.uniform(0.01, 0.10)  # 1%-10% only

# Change drift distribution (default N(0, 0.01))
drift = random.gauss(0.005, 0.01)  # Positive bias

# Change initial price (default $100 ± 50%)
initial_price = random.uniform(50, 150)

# Change symbol length (default 3)
symbol = Asset.generate_symbol(length=4)  # 4-letter symbols
```

### Code Style & Linting

```bash
# Format code (if using black)
black app.py models.py validators.py

# Lint code
flake8 *.py

# Security scanning
bandit -r . -x ./venv
```

## Production Deployment

### Heroku Deployment

1. **Create Heroku app:**
   ```bash
   heroku create your-app-name
   ```

2. **Add PostgreSQL:**
   ```bash
   heroku addons:create heroku-postgresql:mini
   ```

3. **Set environment variables:**
   ```bash
   heroku config:set SECRET_KEY=$(openssl rand -hex 32)
   heroku config:set FLASK_ENV=production
   heroku config:set INITIAL_CASH=100000
   ```

4. **Deploy:**
   ```bash
   git push heroku main
   ```

5. **Initialize database:**
   ```bash
   # Database is automatically initialized via Procfile release phase
   # Or manually trigger:
   heroku run python init_heroku_db.py
   ```

6. **Open application:**
   ```bash
   heroku open
   ```

### Production Checklist

Before deploying to production:

- [ ] Set strong `SECRET_KEY` (use `openssl rand -hex 32`)
- [ ] Set `FLASK_ENV=production`
- [ ] Use PostgreSQL database (not SQLite)
- [ ] Enable HTTPS/SSL
- [ ] Configure session timeout appropriately
- [ ] Set up monitoring (Sentry, DataDog, etc.)
- [ ] Configure backup strategy for database
- [ ] Review and test all security features
- [ ] Run full test suite
- [ ] Load test with expected user concurrency
- [ ] Set up log aggregation (Papertrail, Loggly, etc.)
- [ ] Configure DNS and custom domain
- [ ] Set up CDN for static assets (optional)

See [DEPLOYMENT.md](DEPLOYMENT.md) and [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md) for detailed deployment guides.

## Security

⚠️ **Production-Ready Security**: This application implements comprehensive security features suitable for production deployment.

### Implemented Security Features

#### Input Validation (Phase 1.1) ✅
- **Decimal Precision**: All financial calculations use Python's Decimal type (8 decimal places)
- **Bounds Checking**: Quantity (1e-8 to 1B), Price ($0.01 to 1B), Trade Value (max 10B)
- **Type Safety**: Rejects negative values, infinity, NaN, malformed inputs
- **SQL Injection Protection**: Symbol validator blocks SQL keywords, injection patterns
- **Database Constraints**: CHECK constraints enforce rules at database level

#### Authentication & Session Security ✅
- **Password Hashing**: Scrypt algorithm (CPU and memory hard)
- **Password Policy**: 8+ characters, rejects whitespace-only passwords
- **Rate Limiting**: 5 failed login attempts per 5 minutes per username
- **Session Management**: HttpOnly cookies, SameSite=Lax, 1-hour timeout
- **CSRF Protection**: Flask-WTF tokens on all forms

#### Database Security ✅
- **ORM-only Queries**: No raw SQL, all queries parameterized via SQLAlchemy
- **Username Validation**: Alphanumeric + underscore only, blocks reserved names
- **Data Integrity**: CHECK constraints on portfolios, transactions, assets

#### API Security ✅
- **Authentication Required**: All trading/portfolio endpoints require login
- **Input Sanitization**: All user inputs validated before processing
- **Error Handling**: Safe error messages, no information leakage

### Security Documentation

Comprehensive security documentation available:
- **[SECURITY.md](SECURITY.md)** - Security features and incident response
- **[VALIDATION_ARCHITECTURE.md](VALIDATION_ARCHITECTURE.md)** - Input validation system (57 tests)
- **[test_validators.py](test_validators.py)** - Validation test suite

### Reporting Security Issues

Found a security vulnerability? Please report via private email (do not create public issues):
- Email: [your-email@example.com]
- Include: Description, reproduction steps, impact assessment, suggested fix

## Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature-name`
3. **Write tests**: Add tests for new functionality
4. **Follow code style**: Use consistent formatting (black, flake8)
5. **Update documentation**: Update README, docstrings, type hints
6. **Run tests**: Ensure all tests pass before submitting
7. **Commit with clear messages**: Use descriptive commit messages
8. **Push to your fork**: `git push origin feature/your-feature-name`
9. **Open Pull Request**: Describe changes, link related issues

### Development Guidelines

- Use type hints for function signatures
- Write docstrings for all public functions/classes
- Add validation for all user inputs
- Include unit tests for new features
- Keep functions focused and modular
- Follow defensive programming practices
- Update documentation when changing behavior

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed contribution guidelines.

## Troubleshooting

### Common Issues

#### Database Errors
```
Solution: Reset database
python init_database.py --env development
```

#### Port Already in Use
```
Error: Address already in use (port 5000)
Solution: Kill existing process or change port
lsof -ti:5000 | xargs kill -9
# Or set in .env: FLASK_PORT=5001
```

#### WebSocket Connection Failed
```
Solution: Check CORS settings, ensure SocketIO installed
pip install flask-socketio python-socketio
```

#### Assets Not Expiring
```
Solution: Check expiration thread is running
tail -f martingale.log | grep "expiration"
# Should see checks every 60 seconds
```

#### Price Updates Not Working
```
Solution: Check price service status
curl http://localhost:5001/health
# Or check fallback mode is active in logs
```

### Getting Help

1. **Check logs**: `martingale.log` contains detailed error information
2. **Review documentation**: See `docs/` directory for guides
3. **Run diagnostics**: `python services_startup_test.py`
4. **GitHub Issues**: [Create an issue](https://github.com/yourusername/martingale/issues)

## Related Documentation

- **[README_ARCHITECTURE.md](README_ARCHITECTURE.md)** - Detailed architecture overview (legacy, partially outdated)
- **[EXPIRING_ASSETS_SUMMARY.md](EXPIRING_ASSETS_SUMMARY.md)** - Asset lifecycle system
- **[VALIDATION_ARCHITECTURE.md](VALIDATION_ARCHITECTURE.md)** - Input validation deep dive
- **[DRIFT_IMPLEMENTATION.md](DRIFT_IMPLEMENTATION.md)** - GBM drift parameter details
- **[SECURITY.md](SECURITY.md)** - Security features and practices
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Deployment checklist
- **[MIGRATION_EXPIRING_ASSETS.md](MIGRATION_EXPIRING_ASSETS.md)** - Migration guide (legacy → expiring assets)
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick API reference
- **[MOBILE_VWAP_FEATURE.md](MOBILE_VWAP_FEATURE.md)** - Mobile UI VWAP implementation
- **[ASSET_ID_CONSISTENCY.md](ASSET_ID_CONSISTENCY.md)** - Asset ID usage and backward compatibility

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **Flask** - Excellent web framework and ecosystem
- **Chart.js** - Powerful charting library
- **Socket.IO** - Reliable WebSocket implementation
- **SQLAlchemy** - Robust ORM with great documentation
- **Contributors** - Thank you to all who have contributed

## Disclaimer

⚠️ **Educational Purpose Only**

This is a **paper trading application** for educational and demonstration purposes. 

- No real money or financial instruments are involved
- Prices are simulated using mathematical models (Geometric Brownian Motion)
- Not suitable for real trading decisions
- Not financial advice
- Use at your own risk

For real trading, use licensed financial platforms with proper regulatory oversight.

---

**Author**: Richard Correro  
**Repository**: [github.com/rcorrero/martingale](https://github.com/rcorrero/martingale)  
**Last Updated**: November 2025  
**Version**: 2.0 (Expiring Assets + Input Validation)
