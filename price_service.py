"""
Price Service - Separate service for generating and managing asset prices.
This service can be run independently and provides APIs for price data.
"""
from flask import Flask, jsonify, request
import numpy as np
import threading
import time
import json
from datetime import datetime
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PriceService:
    """Service for managing asset prices and price history."""
    
    def __init__(self, config=None):
        """Initialize the price service with asset configuration."""
        self.config = config or self._get_default_config()
        self.assets = {}
        self.running = False
        self.update_thread = None
        self._initialize_assets()
    
    def _get_default_config(self):
        """Get default configuration for fictitious assets."""
        return {
            'ASSETS': {
                'XQR': {'price': 100, 'volatility': 0.05},
                'ZLN': {'price': 100, 'volatility': 0.06},
                'FWX': {'price': 100, 'volatility': 0.02},
                'KVT': {'price': 100, 'volatility': 0.03},
                'PGH': {'price': 100, 'volatility': 0.08},
                'MWZ': {'price': 100, 'volatility': 0.025},
                'DQB': {'price': 100, 'volatility': 0.035},
                'LNC': {'price': 100, 'volatility': 0.04},
                'EPS': {'price': 100, 'volatility': 0.10},
                'ACT': {'price': 100, 'volatility': 0.001},
                'ORD': {'price': 100, 'volatility': 0.2},
            },
            'MAX_HISTORY_POINTS': 100,
            'PRICE_UPDATE_INTERVAL': 1,  # seconds
            'PRICE_DATA_FILE': 'price_data.json'
        }
    
    def _initialize_assets(self):
        """Initialize assets with starting prices and empty history."""
        # Try to load existing price data
        self._load_price_data()
        
        # Initialize any missing assets
        for symbol, config_data in self.config['ASSETS'].items():
            if symbol not in self.assets:
                self.assets[symbol] = {
                    'price': config_data['price'],
                    'volatility': config_data['volatility'],
                    'history': [],
                    'last_update': None
                }
    
    def _load_price_data(self):
        """Load existing price data from file."""
        data_file = self.config.get('PRICE_DATA_FILE', 'price_data.json')
        if os.path.exists(data_file):
            try:
                with open(data_file, 'r') as f:
                    self.assets = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.assets = {}
        else:
            self.assets = {}
    
    def _save_price_data(self):
        """Save current price data to file."""
        data_file = self.config.get('PRICE_DATA_FILE', 'price_data.json')
        try:
            with open(data_file, 'w') as f:
                json.dump(self.assets, f, indent=2)
        except IOError as e:
            logger.error(f"Error saving price data: {e}")
    
    def start_price_updates(self):
        """Start the background price update process."""
        if not self.running:
            self.running = True
            self.update_thread = threading.Thread(target=self._price_update_loop, daemon=True)
            self.update_thread.start()
            logger.info("Price service started")
    
    def stop_price_updates(self):
        """Stop the background price update process."""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=2)
        self._save_price_data()
        logger.info("Price service stopped")
    
    def _price_update_loop(self):
        """Main price update loop - runs in background thread."""
        while self.running:
            try:
                self._update_prices()
                time.sleep(self.config['PRICE_UPDATE_INTERVAL'])
            except Exception as e:
                logger.error(f"Error in price update loop: {e}")
                time.sleep(1)  # Brief pause before retry
    
    def _update_prices(self):
        """Update all asset prices using geometric Brownian motion to ensure martingale property."""
        timestamp = time.time() * 1000  # JavaScript-compatible timestamp
        
        # Round timestamp to nearest second to avoid sub-second duplicates
        timestamp = int(timestamp / 1000) * 1000
        
        for symbol, data in self.assets.items():
            # Skip if this timestamp already exists for this symbol
            if (data.get('last_update') == timestamp or
                (len(data['history']) > 0 and data['history'][-1]['time'] == timestamp)):
                continue
            
            # Get volatility from config or asset data
            volatility = data.get('volatility', 0.02)
            
            # Use geometric Brownian motion with drift correction for martingale property
            # S(t+dt) = S(t) * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
            # For a martingale, mu = 0, so we get:
            # S(t+dt) = S(t) * exp(-0.5*sigma^2*dt + sigma*sqrt(dt)*Z)
            # where Z ~ N(0,1)
            
            dt = 1.0  # 1 second time step
            sigma = volatility
            
            # Generate random shock from standard normal
            z = np.random.standard_normal()
            
            # Calculate multiplicative factor with drift correction
            # The -0.5*sigma^2*dt term ensures E[S(t+dt)] = S(t)
            log_return = -0.5 * sigma**2 * dt + sigma * np.sqrt(dt) * z
            
            # Update price using exponential (geometric Brownian motion)
            new_price = data['price'] * np.exp(log_return)
            
            # Ensure price stays positive (shouldn't go negative with GBM, but safety check)
            data['price'] = max(new_price, 0.0)
            data['last_update'] = timestamp
            
            # Add to history
            price_record = {'time': timestamp, 'price': data['price']}
            data['history'].append(price_record)
            
            # Trim history to maximum points
            max_points = self.config.get('MAX_HISTORY_POINTS', 100)
            if len(data['history']) > max_points:
                data['history'] = data['history'][-max_points:]
        
        # Periodically save data (every 10 updates)
        if int(timestamp / 1000) % 10 == 0:
            self._save_price_data()
    
    def get_current_prices(self):
        """Get current prices for all assets."""
        return {symbol: {'price': data['price'], 'last_update': data.get('last_update')} 
                for symbol, data in self.assets.items()}
    
    def get_price_history(self, symbol=None, limit=None):
        """Get price history for a specific symbol or all symbols."""
        if symbol:
            if symbol in self.assets:
                history = self.assets[symbol]['history']
                if limit:
                    history = history[-limit:]
                return {symbol: history}
            else:
                return {}
        else:
            # Return all histories
            result = {}
            for sym, data in self.assets.items():
                history = data['history']
                if limit:
                    history = history[-limit:]
                result[sym] = history
            return result
    
    def get_asset_info(self, symbol=None):
        """Get complete asset information."""
        if symbol:
            return self.assets.get(symbol, {})
        return self.assets
    
    def add_asset(self, symbol, initial_price, volatility=0.02):
        """Add a new asset to the service."""
        self.assets[symbol] = {
            'price': initial_price,
            'volatility': volatility,
            'history': [],
            'last_update': None
        }
        self._save_price_data()
    
    def remove_asset(self, symbol):
        """Remove an asset from the service."""
        if symbol in self.assets:
            del self.assets[symbol]
            self._save_price_data()
            return True
        return False

# Flask API wrapper for the price service
def create_price_api(price_service):
    """Create a Flask API for the price service."""
    app = Flask(__name__)
    
    @app.route('/health')
    def health():
        """Health check endpoint."""
        return jsonify({'status': 'healthy', 'service': 'price_service'})
    
    @app.route('/prices')
    def get_prices():
        """Get current prices for all assets."""
        return jsonify(price_service.get_current_prices())
    
    @app.route('/prices/<symbol>')
    def get_price(symbol):
        """Get current price for a specific asset."""
        symbol = symbol.upper()
        prices = price_service.get_current_prices()
        if symbol in prices:
            return jsonify({symbol: prices[symbol]})
        return jsonify({'error': 'Asset not found'}), 404
    
    @app.route('/history')
    def get_all_history():
        """Get price history for all assets."""
        limit = request.args.get('limit', type=int)
        return jsonify(price_service.get_price_history(limit=limit))
    
    @app.route('/history/<symbol>')
    def get_symbol_history(symbol):
        """Get price history for a specific asset."""
        symbol = symbol.upper()
        limit = request.args.get('limit', type=int)
        history = price_service.get_price_history(symbol, limit)
        if history:
            return jsonify(history)
        return jsonify({'error': 'Asset not found'}), 404
    
    @app.route('/assets')
    def get_assets():
        """Get all asset information."""
        return jsonify(price_service.get_asset_info())
    
    @app.route('/assets/<symbol>')
    def get_asset(symbol):
        """Get information for a specific asset."""
        symbol = symbol.upper()
        asset_info = price_service.get_asset_info(symbol)
        if asset_info:
            return jsonify({symbol: asset_info})
        return jsonify({'error': 'Asset not found'}), 404
    
    return app

if __name__ == "__main__":
    # Create and start the price service
    service = PriceService()
    service.start_price_updates()
    
    # Create the Flask API
    api_app = create_price_api(service)
    
    try:
        # Run the API server
        logger.info("Starting Price Service API on http://localhost:5001")
        api_app.run(host='0.0.0.0', port=5001, debug=False)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        service.stop_price_updates()