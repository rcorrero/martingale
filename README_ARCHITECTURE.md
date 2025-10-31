# Martingale Trading Platform - Architecture Update

The price generation functionality has been refactored into a separate service for better modularity and scalability.

## Architecture Overview

### Components

1. **Price Service** (`price_service.py`)
   - Standalone service for generating and managing asset prices
   - Runs on port 5001 by default
   - Provides REST API for price data
   - Can run independently of the main application

2. **Web Application** (`app.py`)
   - Main trading platform interface
   - Runs on port 5000 by default
   - Communicates with price service via API

3. **Price Client** (`price_client.py`)
   - Interface library for communicating with the price service
   - Provides fallback functionality if price service is unavailable
   - Hybrid mode automatically switches between API and local generation

## Running the Application

### Option 1: Start All Services (Recommended)
```bash
python start_services.py
```
This will automatically start both the price service and web application.

### Option 2: Start Services Manually

1. **Start Price Service**:
```bash
python price_service.py
```

2. **Start Web Application** (in a separate terminal):
```bash
python app.py
```

### Option 3: Web Application Only (Fallback Mode)
```bash
python app.py
```
The web application will use local price generation if the price service is not available.

## API Endpoints (Price Service)

- `GET /health` - Health check
- `GET /prices` - Get current prices for all assets
- `GET /prices/{symbol}` - Get current price for specific asset
- `GET /history` - Get price history for all assets
- `GET /history/{symbol}` - Get price history for specific asset
- `GET /assets` - Get complete asset information
- `GET /assets/{symbol}` - Get information for specific asset

## Configuration

### Environment Variables

- `PRICE_SERVICE_URL` - URL of the price service (default: http://localhost:5001)
- `FLASK_ENV` - Flask environment (development/production)
- `SECRET_KEY` - Flask secret key
- `INITIAL_CASH` - Initial cash for new users

### Files

- `config.py` - Main configuration file
- `price_data.json` - Persistent price data storage (created automatically)
- `users.json` - User account data
- `portfolios.json` - User portfolio data
- `global_transactions.json` - Transaction history

## Benefits of the New Architecture

1. **Modularity**: Price generation is completely separate from the web application
2. **Scalability**: Price service can be scaled independently
3. **Flexibility**: Easy to swap price generation algorithms or data sources
4. **Reliability**: Fallback mode ensures the application works even if price service is down
5. **Development**: Easier to test and develop individual components

## Development Notes

- The price service saves data to `price_data.json` periodically
- Price updates are broadcast via WebSocket to connected clients
- The hybrid client automatically handles failover between API and local generation
- All price-related API calls now go through the price service client

## Dependencies

See `requirements.txt` for the complete list. New dependencies include:
- `requests` - For HTTP API communication

## Migration from Previous Version

The application is fully backward compatible. If you have existing data files (`users.json`, `portfolios.json`, etc.), they will continue to work without modification.