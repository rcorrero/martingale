# Martingale

A paper trading web application that simulates real-time asset trading with virtual money. Built with Flask, SocketIO, and Chart.js for an interactive trading experience.

## Features

- **Real-time Trading**: Buy and sell simulated assets (BTC, ETH) with live price updates
- **Interactive Charts**: Real-time price history charts with VWAP indicators
- **Portfolio Management**: Track holdings, cash balance, and trading history
- **Performance Analytics**: Comprehensive P&L tracking with realized/unrealized gains
- **User Authentication**: Secure login system with persistent user portfolios
- **Security Features**: Password strength requirements, rate limiting, CAPTCHA protection
- **Responsive Design**: Works seamlessly on desktop and mobile devices

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
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
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
- `INITIAL_CASH`: Starting cash amount for new users
- `RECAPTCHA_ENABLED`: Enable/disable CAPTCHA verification (optional)
- `RECAPTCHA_SITE_KEY`: Google reCAPTCHA site key (if enabled)
- `RECAPTCHA_SECRET_KEY`: Google reCAPTCHA secret key (if enabled)

### Optional: Enable CAPTCHA

To protect against bot registrations, you can enable Google reCAPTCHA:

1. Get reCAPTCHA keys from: https://www.google.com/recaptcha/admin
2. Set `RECAPTCHA_ENABLED=true` in your `.env` file
3. Add your `RECAPTCHA_SITE_KEY` and `RECAPTCHA_SECRET_KEY`
4. See [docs/RECAPTCHA_SETUP.md](docs/RECAPTCHA_SETUP.md) for detailed instructions

## Usage

1. **Register/Login**: Create an account or log in with existing credentials
2. **View Markets**: See real-time prices for available assets
3. **Place Trades**: Enter symbol and quantity to buy/sell assets
4. **Monitor Portfolio**: Track your holdings and performance in real-time
5. **Analyze Performance**: View detailed P&L analytics and transaction history

## Technology Stack

- **Backend**: Flask, Flask-SocketIO, Flask-Login
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Real-time**: WebSocket communications via SocketIO
- **Charts**: Chart.js with real-time streaming
- **Authentication**: Flask-Login with password hashing
- **Data Storage**: JSON files (easily replaceable with database)

## Project Structure

```
martingale/
├── app.py                 # Main application file
├── config.py             # Configuration settings
├── requirements.txt      # Python dependencies
├── .env.example         # Environment variables template
├── .gitignore           # Git ignore rules
├── README.md            # Project documentation
├── static/
│   ├── css/
│   │   └── style.css    # Application styles
│   └── js/
│       └── main.js      # Frontend JavaScript
└── templates/
    ├── index.html       # Main trading interface
    ├── login.html       # Login page
    └── register.html    # Registration page
```

## Development

### Adding New Assets

To add new tradeable assets, update the `ASSETS` configuration in `config.py`:

```python
ASSETS = {
    'BTC': {'price': 50000, 'volatility': 0.02},
    'ETH': {'price': 3000, 'volatility': 0.03},
    'AAPL': {'price': 150, 'volatility': 0.015},  # New asset
}
```

### Database Migration

For production use, consider replacing JSON file storage with a proper database:

1. Add database configuration to `config.py`
2. Create database models
3. Update data persistence functions
4. Add database migrations

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Security Considerations

⚠️ **Important**: This application implements multiple security features for production use.

### Implemented Security Features
- ✅ Strong password requirements (8+ chars, uppercase, lowercase, numbers, special chars)
- ✅ Username validation and sanitization
- ✅ Rate limiting on login attempts (5 attempts per 5 minutes)
- ✅ Password hashing with scrypt algorithm
- ✅ Session security (HttpOnly, SameSite, timeout)
- ✅ CSRF protection on all forms
- ✅ SQL injection prevention via SQLAlchemy ORM
- ✅ XSS protection with secure cookie configuration
- ✅ CAPTCHA for registration (optional, configurable)

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
