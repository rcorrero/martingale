# Martingale

A paper trading web application that simulates real-time asset trading with virtual money. Built with Flask, SocketIO, and Chart.js for an interactive trading experience.

## Features

- **Real-time Trading**: Buy and sell simulated assets with live price updates
- **Expiring Assets**: Assets have predefined expiration dates (1 day to 1 month)
- **Automatic Settlement**: Positions automatically settled at expiration with cash returned
- **Dynamic Asset Pool**: New assets automatically created to replace expired ones
- **Interactive Charts**: Real-time price history charts with VWAP indicators
- **Portfolio Management**: Track holdings, cash balance, and trading history
- **Performance Analytics**: Comprehensive P&L tracking with realized/unrealized gains
- **User Authentication**: Secure login system with persistent user portfolios
- **Responsive Design**: Works seamlessly on desktop and mobile devices

## What's New: Expiring Assets System

The platform now supports **dynamic expiring assets** that simulate real-world futures contracts:

- ✅ **Random Asset Generation**: New assets created with 3-letter symbols (e.g., "KLP", "FGH")
- ✅ **Variable Expirations**: Each asset expires between 1 day and 1 month from creation
- ✅ **Automatic Settlement**: Holdings settled at final price upon expiration
- ✅ **Auto-Replacement**: System maintains minimum of 10 active assets
- ✅ **Settlement History**: Complete audit trail of all settlements
- ✅ **No Manual Intervention**: Fully automated lifecycle management

See [EXPIRING_ASSETS_SUMMARY.md](EXPIRING_ASSETS_SUMMARY.md) for detailed documentation.

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/martingale.git
   cd martingale
   ```

2. **Create a virtual environment:**
   ```bash
   5. **Initialize the database schema:**
       ```bash
       python init_database.py --env development
       ```

   6. **Run the application:**
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   7. **Open your browser and navigate to:**
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env file with your preferred settings
   ```

5. **Run the application:**
   ```bash
   python app.py
   ```

6. **Open your browser and navigate to:**
   ```
   http://localhost:5001
   ```

## Configuration

The application uses environment variables for configuration. Copy `.env.example` to `.env` and modify as needed:

- `SECRET_KEY`: Flask secret key for session security
- `FLASK_ENV`: Set to 'development' or 'production'
- `FLASK_DEBUG`: Enable/disable debug mode
- `FLASK_PORT`: Port number for the application
- `INITIAL_CASH`: Starting cash amount for new users (default: 100000)
- `INITIAL_ASSET_PRICE`: Starting price for new assets (default: 100)
- `MIN_ACTIVE_ASSETS`: Minimum active assets to maintain (default: 10)
- `EXPIRATION_CHECK_INTERVAL`: How often to check for expirations in seconds (default: 60)
- `CLEANUP_OLD_ASSETS_DAYS`: Remove expired assets after N days (default: 30)

## Usage

1. **Register/Login**: Create an account or log in with existing credentials
2. **View Markets**: See real-time prices for available assets
3. **Place Trades**: Enter symbol and quantity to buy/sell assets
4. **Monitor Portfolio**: Track your holdings and performance in real-time
5. **Analyze Performance**: View detailed P&L analytics and transaction history

## Technology Stack

- **Backend**: Flask, Flask-SocketIO, Flask-Login, Flask-SQLAlchemy
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Real-time**: WebSocket communications via SocketIO
- **Charts**: Chart.js with real-time streaming
- **Authentication**: Flask-Login with scrypt password hashing
- **Database**: SQLite (development) / PostgreSQL (production)
- **Asset Management**: Custom lifecycle manager with automatic settlement

## Project Structure

```
martingale/
├── app.py                      # Main application file
├── config.py                   # Configuration settings
├── models.py                   # Database models (User, Portfolio, Asset, Settlement)
├── asset_manager.py            # Asset lifecycle management
├── price_client.py             # Price service client with fallback
├── price_service.py            # Standalone price generation service
├── requirements.txt            # Python dependencies
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore rules
├── README.md                  # Project documentation
├── EXPIRING_ASSETS_SUMMARY.md # Expiring assets documentation
├── MIGRATION_EXPIRING_ASSETS.md # Migration guide
├── SECURITY.md                # Security documentation
├── test_expiring_assets.py    # Test suite for asset lifecycle
├── static/
│   ├── css/
│   │   └── style.css          # Application styles
│   └── js/
│       └── main.js            # Frontend JavaScript
└── templates/
    ├── index.html             # Main trading interface
    ├── login.html             # Login page
    └── register.html          # Registration page
```

## Development

### Testing the System

Run the test suite to verify asset lifecycle:

```bash
python test_expiring_assets.py
```

Tests include:
- Asset creation with random parameters
- Expiration mechanics
- Settlement processing
- Pool maintenance
- Full lifecycle integration

### Monitoring Asset Lifecycle

Check asset statistics:
```bash
curl http://localhost:5000/api/assets/summary
```

View active assets:
```bash
curl http://localhost:5000/api/assets | jq
```

Watch expiration logs:
```bash
tail -f martingale.log | grep -i "expir"
```

### Customizing Asset Generation

Edit `Asset.create_new_asset()` in `models.py`:

```python
# Change expiration range (default 1-30 days)
days_to_expiry = random.randint(7, 14)  # 1-2 weeks only

# Change volatility range (default 0.1%-20%)
volatility = random.uniform(0.01, 0.10)  # 1%-10% only

# Change symbol length (default 3)
symbol = Asset.generate_symbol(length=4)  # 4-letter symbols
```

### Database Operations

Access Flask shell for manual operations:
```bash
flask shell
>>> from models import Asset, Settlement
>>> Asset.query.filter_by(is_active=True).count()
10
>>> Asset.query.filter_by(is_active=False).count()
0
```

### Resetting the Database

Use the unified initialization script to drop and recreate tables, reseed price metadata, and rebuild the active asset pool:

```bash
python init_database.py --env development
```

Flags such as `--no-reset`, `--skip-price-seed`, or `--skip-asset-seed` let you customize what gets reinitialized. For production deployments (including Heroku) run the same script with `--env production` in the target environment.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Security Considerations

⚠️ **Important**: This application implements multiple security features for production use.

### Implemented Security Features
- ✅ **Input Validation** (Phase 1.1 - Production Ready)
  - Comprehensive validation module with Decimal precision for financial calculations
  - Symbol validation with SQL injection protection
  - Quantity/price bounds checking (prevents negative, infinity, NaN values)
  - Trade value limits to prevent overflow attacks
  - Database CHECK constraints as defense-in-depth layer
- ✅ Password length policy (8+ chars, whitespace-only passwords rejected)
- ✅ Username validation and sanitization
- ✅ Rate limiting on login attempts (5 attempts per 5 minutes)
- ✅ Password hashing with scrypt algorithm
- ✅ Session security (HttpOnly, SameSite, timeout)
- ✅ CSRF protection on all forms
- ✅ SQL injection prevention via SQLAlchemy ORM and validators
- ✅ XSS protection with secure cookie configuration

### For Production Deployment
1. **Set strong SECRET_KEY** in environment variables
2. **Use HTTPS** (SESSION_COOKIE_SECURE enabled in production)
3. **Use PostgreSQL** instead of SQLite for better concurrency
4. **Review SECURITY.md** for comprehensive security documentation
5. **Keep dependencies updated** for security patches

See [SECURITY.md](SECURITY.md) for detailed security documentation and best practices.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Chart.js for excellent charting capabilities
- Flask community for comprehensive documentation
- Contributors and testers

## Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/yourusername/martingale/issues) page
2. Create a new issue with detailed information
3. Contact the maintainers

---

**Disclaimer**: This is a paper trading application for educational purposes only. No real money or assets are involved.
