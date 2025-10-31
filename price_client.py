"""
Price Client - Client library for communicating with the price service.
Provides fallback functionality when the price service is unavailable.
"""
import time
import requests
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class PriceServiceClient:
    """Client for communicating with the price service API."""
    
    def __init__(self, base_url: str = "http://localhost:5001", timeout: int = 5):
        """Initialize the price service client.
        
        Args:
            base_url: Base URL of the price service API
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._session = requests.Session()
    
    def _make_request(self, endpoint: str, method: str = 'GET', **kwargs) -> Optional[Dict]:
        """Make a request to the price service.
        
        Args:
            endpoint: API endpoint (without base URL)
            method: HTTP method
            **kwargs: Additional arguments for requests
            
        Returns:
            Response data as dictionary, or None if error
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = self._session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error communicating with price service: {e}")
            return None
        except (ValueError, KeyError) as e:
            logger.error(f"Error parsing price service response: {e}")
            return None
    
    def health_check(self) -> bool:
        """Check if the price service is healthy.
        
        Returns:
            True if service is healthy, False otherwise
        """
        result = self._make_request('/health')
        return result is not None and result.get('status') == 'healthy'
    
    def get_current_prices(self) -> Dict[str, Dict[str, Any]]:
        """Get current prices for all assets.
        
        Returns:
            Dictionary mapping symbol to price info
        """
        result = self._make_request('/prices')
        return result or {}
    
    def get_current_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current price for a specific asset.
        
        Args:
            symbol: Asset symbol
            
        Returns:
            Price information for the symbol, or None if not found
        """
        symbol = symbol.upper()
        result = self._make_request(f'/prices/{symbol}')
        if result:
            return result.get(symbol)
        return None
    
    def get_price_history(self, symbol: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, List[Dict]]:
        """Get price history for assets.
        
        Args:
            symbol: Specific symbol to get history for (None for all)
            limit: Maximum number of historical points
            
        Returns:
            Dictionary mapping symbol to list of price history points
        """
        if symbol:
            endpoint = f'/history/{symbol.upper()}'
        else:
            endpoint = '/history'
        
        params = {}
        if limit:
            params['limit'] = limit
        
        result = self._make_request(endpoint, params=params)
        return result or {}
    
    def get_asset_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get complete asset information.
        
        Args:
            symbol: Specific symbol to get info for (None for all)
            
        Returns:
            Asset information
        """
        if symbol:
            endpoint = f'/assets/{symbol.upper()}'
        else:
            endpoint = '/assets'
        
        result = self._make_request(endpoint)
        return result or {}
    
    def wait_for_service(self, max_attempts: int = 30, delay: float = 1.0) -> bool:
        """Wait for the price service to become available.
        
        Args:
            max_attempts: Maximum number of health check attempts
            delay: Delay between attempts in seconds
            
        Returns:
            True if service becomes available, False if timeout
        """
        for attempt in range(max_attempts):
            if self.health_check():
                logger.info(f"Price service is ready (attempt {attempt + 1})")
                return True
            if attempt < max_attempts - 1:
                logger.debug(f"Waiting for price service... (attempt {attempt + 1}/{max_attempts})")
                time.sleep(delay)
        
        logger.warning("Price service did not become available within timeout")
        return False

class FallbackPriceService:
    """Fallback price service that generates prices locally if the API is unavailable."""
    
    def __init__(self, assets_config: Dict[str, Dict[str, Any]]):
        """Initialize with asset configuration.
        
        Args:
            assets_config: Configuration dictionary for assets
        """
        self.assets = {}
        for symbol, config in assets_config.items():
            self.assets[symbol] = {
                'price': config['price'],
                'volatility': config.get('volatility', 0.02),
                'history': [],
                'last_update': None
            }
    
    def add_asset(self, symbol: str, initial_price: float, volatility: float = 0.02):
        """Add a new asset to the fallback service.
        
        Args:
            symbol: Asset symbol
            initial_price: Starting price
            volatility: Price volatility
        """
        if symbol not in self.assets:
            self.assets[symbol] = {
                'price': initial_price,
                'volatility': volatility,
                'history': [],
                'last_update': None
            }
            logger.info(f"Added asset {symbol} to fallback price service")
    
    def remove_asset(self, symbol: str):
        """Remove an asset from the fallback service.
        
        Args:
            symbol: Asset symbol to remove
        """
        if symbol in self.assets:
            del self.assets[symbol]
            logger.info(f"Removed asset {symbol} from fallback price service")
    
    def get_symbols(self) -> List[str]:
        """Get list of all tracked symbols.
        
        Returns:
            List of symbol strings
        """
        return list(self.assets.keys())
    
    def update_prices(self):
        """Update prices using random walk (similar to original implementation)."""
        import numpy as np
        
        timestamp = time.time() * 1000
        # Round timestamp to nearest second to avoid sub-second duplicates
        timestamp = int(timestamp / 1000) * 1000
        
        for symbol, data in self.assets.items():
            # Skip if this timestamp already exists for this symbol
            if (data.get('last_update') == timestamp or
                (len(data['history']) > 0 and data['history'][-1]['time'] == timestamp)):
                continue
                
            change_percent = np.random.normal(0, data['volatility'])
            data['price'] *= (1 + change_percent)
            data['price'] = max(data['price'], 0.01)  # Prevent negative prices
            data['last_update'] = timestamp
            
            # Add to history
            price_record = {'time': timestamp, 'price': data['price']}
            data['history'].append(price_record)
            
            # Keep only last 100 points
            if len(data['history']) > 100:
                data['history'].pop(0)
    
    def get_current_prices(self) -> Dict[str, Dict[str, Any]]:
        """Get current prices for all assets."""
        return {symbol: {'price': data['price'], 'last_update': data.get('last_update')} 
                for symbol, data in self.assets.items()}
    
    def get_price_history(self, symbol: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, List[Dict]]:
        """Get price history for assets."""
        if symbol:
            if symbol in self.assets:
                history = self.assets[symbol]['history']
                if limit:
                    history = history[-limit:]
                return {symbol: history}
            return {}
        else:
            result = {}
            for sym, data in self.assets.items():
                history = data['history']
                if limit:
                    history = history[-limit:]
                result[sym] = history
            return result

class HybridPriceService:
    """Hybrid service that uses API when available, falls back to local generation."""
    
    def __init__(self, assets_config: Dict[str, Dict[str, Any]], api_url: str = "http://localhost:5001"):
        """Initialize hybrid service.
        
        Args:
            assets_config: Asset configuration for fallback
            api_url: URL of the price service API
        """
        self.client = PriceServiceClient(api_url)
        self.fallback = FallbackPriceService(assets_config)
        self._api_available = False
        self._last_health_check = 0
        self._health_check_interval = 30  # seconds
    
    def _check_api_health(self) -> bool:
        """Check if API is available (with caching to avoid frequent checks)."""
        current_time = time.time()
        if current_time - self._last_health_check > self._health_check_interval:
            self._api_available = self.client.health_check()
            self._last_health_check = current_time
        return self._api_available
    
    def get_current_prices(self) -> Dict[str, Dict[str, Any]]:
        """Get current prices, preferring API over fallback."""
        if self._check_api_health():
            prices = self.client.get_current_prices()
            if prices:
                return prices
        
        # Fallback to local generation - only update if prices are stale
        current_time = time.time() * 1000
        
        # Check if any price needs updating (older than 2 seconds)
        needs_update = False
        for symbol, data in self.fallback.assets.items():
            if data.get('last_update') is None or (current_time - data['last_update']) > 2000:
                needs_update = True
                break
        
        if needs_update:
            self.fallback.update_prices()
            
        return self.fallback.get_current_prices()
    
    def get_price_history(self, symbol: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, List[Dict]]:
        """Get price history, preferring API over fallback."""
        if self._check_api_health():
            history = self.client.get_price_history(symbol, limit)
            if history:
                return history
        
        # Fallback to local history
        return self.fallback.get_price_history(symbol, limit)
    
    def is_using_api(self) -> bool:
        """Check if currently using API (vs fallback)."""
        return self._api_available
    
    def sync_assets_from_db(self, active_assets):
        """Sync fallback price service with active assets from database.
        
        Args:
            active_assets: List of Asset model instances from database
        """
        # Get current symbols in price service
        current_symbols = set(self.fallback.get_symbols())
        db_symbols = {asset.symbol for asset in active_assets}
        
        # Add new assets
        for asset in active_assets:
            if asset.symbol not in current_symbols:
                self.fallback.add_asset(
                    symbol=asset.symbol,
                    initial_price=asset.initial_price,
                    volatility=asset.volatility
                )
        
        # Remove assets no longer in database
        for symbol in current_symbols - db_symbols:
            self.fallback.remove_asset(symbol)