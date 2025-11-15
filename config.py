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
    
    # Session security configuration
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour session timeout
    
    # CSRF protection (enabled by default with Flask-WTF)
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # CSRF tokens don't expire (only session lifetime matters)
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///martingale.db'
    # Fix for Heroku postgres URL
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Application settings
    INITIAL_CASH = float(os.environ.get('INITIAL_CASH', 100000))
    
    # Price service configuration
    PRICE_SERVICE_URL = os.environ.get('PRICE_SERVICE_URL', 'http://localhost:5001')
    
    RANDOM_INITIAL_ASSET_PRICE = bool(os.environ.get('RANDOM_INITIAL_ASSET_PRICE', 'True').lower() in ['true', '1', 'yes'])
    # Initial asset price
    INITIAL_ASSET_PRICE = float(os.environ.get('INITIAL_ASSET_PRICE', 100))
    
    # Asset lifecycle settings
    MIN_ACTIVE_ASSETS = int(os.environ.get('MIN_ACTIVE_ASSETS', 16))  # Minimum active assets to maintain
    EXPIRATION_CHECK_INTERVAL = int(os.environ.get('EXPIRATION_CHECK_INTERVAL', 1)) # in seconds
    CLEANUP_OLD_ASSETS_DAYS = int(os.environ.get('CLEANUP_OLD_ASSETS_DAYS', 1))
    CLEANUP_INTERVAL_HOURS = int(os.environ.get('CLEANUP_INTERVAL_HOURS', 1))

    # Legacy ASSETS config - now used only as fallback/migration
    # New assets are created dynamically with expiration dates
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
    PRICE_SERVICE_URL = os.environ.get('PRICE_SERVICE_URL')

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