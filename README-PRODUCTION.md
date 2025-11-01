# Martingale Trading Platform - Production Deployment Guide

A professional paper trading web application for simulated asset trading with real-time price feeds, interactive charts, and portfolio management.

## Features

- **Real-time Trading**: Simulated trading with live price updates
- **Interactive Charts**: Dynamic price charts with cross-highlighting
- **Portfolio Management**: Track holdings, cash, and performance metrics
- **User Authentication**: Secure login system with persistent portfolios
- **Responsive Design**: VS Code Dark High Contrast theme
- **Microservices Architecture**: Separate price service for scalability

## Production Deployment

### Prerequisites

- Python 3.8+
- Virtual environment support
- Reverse proxy (nginx/apache) recommended
- SSL certificates for HTTPS

### Quick Start

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd martingale
   ./deploy.sh
   ```

2. **Configure Environment**
   - Copy `.env.production` to `.env`
   - Set a secure `SECRET_KEY`
   - Adjust other settings as needed

3. **Initialize Database Schema**
   ```bash
   source .venv/bin/activate
   python init_database.py --env production
   ```

4. **Start Services**
   ```bash
   source .venv/bin/activate
   python start_services.py
   ```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes (prod) | - | Flask secret key for sessions |
| `FLASK_ENV` | No | development | Flask environment |
| `INITIAL_CASH` | No | 100000 | Starting cash for new users |
| `PRICE_SERVICE_URL` | No | http://localhost:5001 | Price service endpoint |

### Security Considerations

- Set a strong, random `SECRET_KEY` in production
- Use HTTPS with proper SSL certificates
- Configure firewall to only expose necessary ports
- Set up proper logging and monitoring
- Regular security updates

### Architecture

- **Web Application** (port 5000): Main Flask app with user interface
- **Price Service** (port 5001): Independent price generation service
- **Data Storage**: PostgreSQL backend for users, portfolios, assets, transactions, and settlements

### Monitoring and Logs

- Application logs: `martingale.log`
- Error tracking via Python logging
- Client-side error handling in JavaScript

### Production Checklist

- [ ] Secure SECRET_KEY configured
- [ ] HTTPS/SSL certificates installed
- [ ] Reverse proxy configured
- [ ] Firewall rules set
- [ ] Log rotation configured
- [ ] Backup strategy for data files
- [ ] Monitoring and alerting set up
- [ ] Document database reset procedure using `python init_database.py --env production`

## Development

For development setup, use the standard requirements.txt and .env.example files.

## Support

For issues and support, please check the application logs and ensure all environment variables are properly configured.