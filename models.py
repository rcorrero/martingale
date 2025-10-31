"""
Database models for Martingale trading platform.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import json
import random
import string

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User model for authentication."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)  # Increased from 120 to 255 for scrypt hashes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to portfolio
    portfolio = db.relationship('Portfolio', backref='user', uselist=False, cascade='all, delete-orphan')
    transactions = db.relationship('Transaction', backref='user', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Set password hash."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if password matches."""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Portfolio(db.Model):
    """Portfolio model for user holdings."""
    __tablename__ = 'portfolios'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    cash = db.Column(db.Float, default=100000.0)
    holdings = db.Column(db.Text, default='{}')  # JSON string of holdings
    position_info = db.Column(db.Text, default='{}')  # JSON string of position info
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_holdings(self):
        """Get holdings as dictionary."""
        return json.loads(self.holdings) if self.holdings else {}
    
    def set_holdings(self, holdings_dict):
        """Set holdings from dictionary."""
        self.holdings = json.dumps(holdings_dict)
    
    def get_position_info(self):
        """Get position info as dictionary."""
        return json.loads(self.position_info) if self.position_info else {}
    
    def set_position_info(self, position_dict):
        """Set position info from dictionary."""
        self.position_info = json.dumps(position_dict)

class Transaction(db.Model):
    """Transaction model for trade history."""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.Float, nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'buy' or 'sell'
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    total_cost = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PriceData(db.Model):
    """Price data model for asset prices."""
    __tablename__ = 'price_data'
    
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False, unique=True)
    current_price = db.Column(db.Float, nullable=False)
    volatility = db.Column(db.Float, default=0.02)
    history = db.Column(db.Text, default='[]')  # JSON string of price history
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_history(self):
        """Get price history as list."""
        return json.loads(self.history) if self.history else []
    
    def set_history(self, history_list):
        """Set price history from list."""
        self.history = json.dumps(history_list)
    
    def add_price_point(self, timestamp, price):
        """Add a new price point to history."""
        history = self.get_history()
        history.append({'time': timestamp, 'price': price})
        
        # Keep only last 1000 points to prevent database bloat
        if len(history) > 1000:
            history = history[-1000:]
        
        self.set_history(history)
        self.current_price = price


class Asset(db.Model):
    """Asset model for tradeable instruments with expiration dates."""
    __tablename__ = 'assets'
    
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False, unique=True, index=True)
    initial_price = db.Column(db.Float, nullable=False)
    current_price = db.Column(db.Float, nullable=False)
    volatility = db.Column(db.Float, default=0.02)
    color = db.Column(db.String(7), nullable=False)  # Hex color code
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    final_price = db.Column(db.Float, nullable=True)  # Set when asset expires
    settled_at = db.Column(db.DateTime, nullable=True)  # When settlement occurred
    
    # Relationships
    settlements = db.relationship('Settlement', backref='asset', cascade='all, delete-orphan')
    
    # Color palette for random assignment
    COLOR_PALETTE = [
        '#f7931a', '#627eea', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#17becf', '#ff7f0e', '#1f77b4',
        '#bcbd22', '#ff6384', '#36a2eb', '#ffce56', '#4bc0c0',
        '#ff9f40', '#9966ff', '#c9cbcf', '#00d084', '#fe6b8b'
    ]
    
    @staticmethod
    def get_random_color():
        """Get a random color from the palette."""
        return random.choice(Asset.COLOR_PALETTE)
    
    @staticmethod
    def generate_symbol(length=3):
        """Generate a random symbol using uppercase letters."""
        while True:
            symbol = ''.join(random.choices(string.ascii_uppercase, k=length))
            # Check if symbol already exists
            if not Asset.query.filter_by(symbol=symbol).first():
                return symbol
    
    @staticmethod
    def create_new_asset(initial_price=100.0, volatility=None, minutes_to_expiry=None):
        """Create a new asset with random expiration between 5 minutes and 8 hours.
        
        Args:
            initial_price: Starting price for the asset
            volatility: Price volatility (random if None)
            minutes_to_expiry: Specific minutes to expiry (random 5-480 if None)
        
        Returns:
            New Asset instance (not yet added to session)
        """
        symbol = Asset.generate_symbol()
        
        # Random volatility between 0.1% and 20% if not specified
        if volatility is None:
            volatility = random.uniform(0.001, 0.20)
        
        # Random expiration between 5 minutes and 8 hours (480 minutes)
        # Using exponential distribution for average around 30 minutes
        if minutes_to_expiry is None:
            # Exponential distribution with mean ~25 minutes, clamped to range
            lambda_param = 1.0 / 25.0
            minutes_to_expiry = random.expovariate(lambda_param)
            # Clamp between 5 and 480 minutes
            minutes_to_expiry = max(5, min(480, minutes_to_expiry))
        
        expires_at = datetime.utcnow() + timedelta(minutes=minutes_to_expiry)
        
        asset = Asset(
            symbol=symbol,
            initial_price=initial_price,
            current_price=initial_price,
            volatility=volatility,
            color=Asset.get_random_color(),
            expires_at=expires_at,
            is_active=True
        )
        
        return asset
    
    def expire(self, final_price=None):
        """Mark asset as expired and set final price.
        
        Args:
            final_price: Final settlement price (uses current_price if None)
        """
        self.is_active = False
        self.final_price = final_price if final_price is not None else self.current_price
        self.settled_at = datetime.utcnow()
    
    def time_to_expiry(self):
        """Get time remaining until expiration.
        
        Returns:
            timedelta object or None if expired
        """
        if not self.is_active:
            return None
        
        now = datetime.utcnow()
        if now >= self.expires_at:
            return timedelta(0)
        
        return self.expires_at - now
    
    def is_expired(self):
        """Check if asset has expired."""
        return datetime.utcnow() >= self.expires_at
    
    def to_dict(self):
        """Convert asset to dictionary for API responses."""
        ttl = self.time_to_expiry()
        return {
            'symbol': self.symbol,
            'price': self.current_price,
            'initial_price': self.initial_price,
            'volatility': self.volatility,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'time_to_expiry_seconds': ttl.total_seconds() if ttl else 0,
            'is_active': self.is_active,
            'final_price': self.final_price,
            'settled_at': self.settled_at.isoformat() if self.settled_at else None
        }
    
    def __repr__(self):
        return f'<Asset {self.symbol} expires {self.expires_at}>'


class Settlement(db.Model):
    """Settlement records for expired asset positions."""
    __tablename__ = 'settlements'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)  # Denormalized for easy access
    quantity = db.Column(db.Float, nullable=False)
    settlement_price = db.Column(db.Float, nullable=False)
    settlement_value = db.Column(db.Float, nullable=False)  # quantity * settlement_price
    settled_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship
    user = db.relationship('User', backref='settlements')
    
    def __repr__(self):
        return f'<Settlement {self.symbol} user={self.user_id} qty={self.quantity} value={self.settlement_value}>'
