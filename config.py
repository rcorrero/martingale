"""
Configuration settings for the Martingale trading application.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration class."""
    
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///martingale.db'
    # Fix for Heroku postgres URL
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Application settings
    INITIAL_CASH = float(os.environ.get('INITIAL_CASH', 100000))
    
    # File paths
    USERS_FILE = 'users.json'
    PORTFOLIOS_FILE = 'portfolios.json'
    GLOBAL_TRANSACTIONS_FILE = 'global_transactions.json'
    
    # Price service configuration
    PRICE_SERVICE_URL = os.environ.get('PRICE_SERVICE_URL', 'http://localhost:5001')
    
    # Initial asset price
    INITIAL_ASSET_PRICE = float(os.environ.get('INITIAL_ASSET_PRICE', 100))

    # Asset configuration - Random fictitious symbols
    ASSETS = {
        'XQR': {'price': INITIAL_ASSET_PRICE, 'volatility': 0.05},
        'ZLN': {'price': INITIAL_ASSET_PRICE, 'volatility': 0.06},
        'FWX': {'price': INITIAL_ASSET_PRICE, 'volatility': 0.02},
        'KVT': {'price': INITIAL_ASSET_PRICE, 'volatility': 0.03},
        'PGH': {'price': INITIAL_ASSET_PRICE, 'volatility': 0.08},
        'MWZ': {'price': INITIAL_ASSET_PRICE, 'volatility': 0.025},
        'DQB': {'price': INITIAL_ASSET_PRICE, 'volatility': 0.035},
        'LNC': {'price': INITIAL_ASSET_PRICE, 'volatility': 0.04},
        'EPS': {'price': INITIAL_ASSET_PRICE, 'volatility': 0.10},
        'ACT': {'price': INITIAL_ASSET_PRICE, 'volatility': 0.001},
        'ORD': {'price': INITIAL_ASSET_PRICE, 'volatility': 0.2},
    }
    
    # Chart settings
    MAX_HISTORY_POINTS = 100
    PRICE_UPDATE_INTERVAL = 1  # seconds

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    FLASK_ENV = 'development'

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    FLASK_ENV = 'production'
    
    # Use secure secret key in production - use fallback if not set (will warn)
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        import warnings
        warnings.warn("SECRET_KEY environment variable not set. Using fallback for development.")
        SECRET_KEY = 'fallback-secret-key-set-proper-key-in-production'
    
    # Ensure HTTPS in production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}