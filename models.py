"""
Database models for Martingale trading platform.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
import numpy as np
import json
import random
import string

db = SQLAlchemy()


def current_utc() -> datetime:
    """Return naive UTC timestamp derived from timezone-aware clock."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(UserMixin, db.Model):
    """User model for authentication."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)  # Increased from 120 to 255 for scrypt hashes
    created_at = db.Column(db.DateTime, default=current_utc)
    
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
    updated_at = db.Column(db.DateTime, default=current_utc, onupdate=current_utc)
    
    # Database constraints for data integrity
    __table_args__ = (
        db.CheckConstraint('cash >= 0', name='check_cash_non_negative'),
        db.CheckConstraint('cash <= 100000000000', name='check_cash_reasonable'),
    )
    
    @staticmethod
    def _normalize_asset_id(raw_key):
        """Convert stored key (id or legacy symbol) into an asset id."""
        if raw_key is None:
            return None
        if isinstance(raw_key, int):
            return raw_key
        if isinstance(raw_key, str):
            stripped = raw_key.strip()
            if stripped.isdigit():
                return int(stripped)
            # Legacy storage by symbol name
            asset = Asset.query.filter_by(symbol=stripped).order_by(Asset.created_at.desc()).first()
            return asset.id if asset else None
        try:
            return int(raw_key)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _serialize_holdings(holdings_map):
        if not holdings_map:
            return '{}'
        normalized = {str(int(asset_id)): float(quantity) for asset_id, quantity in holdings_map.items() if asset_id is not None}
        return json.dumps(normalized)

    @staticmethod
    def _serialize_position_info(position_map):
        if not position_map:
            return '{}'
        normalized = {}
        for asset_id, info in position_map.items():
            if asset_id is None:
                continue
            normalized[str(int(asset_id))] = {
                'total_cost': float(info.get('total_cost', 0.0)),
                'total_quantity': float(info.get('total_quantity', 0.0))
            }
        return json.dumps(normalized)

    def get_holdings_map(self):
        """Return holdings keyed by asset id (int -> float)."""
        raw = json.loads(self.holdings) if self.holdings else {}
        normalized = {}
        for raw_key, quantity in raw.items():
            asset_id = self._normalize_asset_id(raw_key)
            if asset_id is not None:
                normalized[asset_id] = float(quantity)
        return normalized

    def set_holdings(self, holdings_map):
        """Persist holdings keyed by asset id."""
        self.holdings = self._serialize_holdings(holdings_map)

    def get_holdings_by_symbol(self):
        """Return holdings keyed by asset symbol for presentation purposes."""
        holdings = self.get_holdings_map()
        if not holdings:
            return {}
        assets = Asset.query.filter(Asset.id.in_(holdings.keys())).all()
        id_to_symbol = {asset.id: asset.symbol for asset in assets if asset.symbol}
        return {id_to_symbol[asset_id]: holdings[asset_id] for asset_id in holdings if asset_id in id_to_symbol}

    def get_position_info_map(self):
        """Return position metadata keyed by asset id."""
        raw = json.loads(self.position_info) if self.position_info else {}
        normalized = {}
        for raw_key, info in raw.items():
            asset_id = self._normalize_asset_id(raw_key)
            if asset_id is None:
                continue
            normalized[asset_id] = {
                'total_cost': float(info.get('total_cost', 0.0)) if info else 0.0,
                'total_quantity': float(info.get('total_quantity', 0.0)) if info else 0.0
            }
        return normalized

    def set_position_info(self, position_map):
        """Persist position info keyed by asset id."""
        self.position_info = self._serialize_position_info(position_map)

    def get_position_info_by_symbol(self):
        """Return position info keyed by asset symbol for presentation."""
        position_map = self.get_position_info_map()
        if not position_map:
            return {}
        assets = Asset.query.filter(Asset.id.in_(position_map.keys())).all()
        id_to_symbol = {asset.id: asset.symbol for asset in assets if asset.symbol}
        result = {}
        for asset_id, info in position_map.items():
            symbol = id_to_symbol.get(asset_id)
            if symbol:
                result[symbol] = info
        return result

    # Backwards-compatible accessors used throughout the application
    def get_holdings(self):
        return self.get_holdings_map()

    def get_position_info(self):
        return self.get_position_info_map()

class Transaction(db.Model):
    """Transaction model for trade history."""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    legacy_symbol = db.Column('symbol', db.String(10), nullable=False)
    timestamp = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'buy', 'sell', or 'settlement'
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    total_cost = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=current_utc)

    # Relationships
    asset = db.relationship('Asset', back_populates='transactions', lazy='joined')
    
    # Database constraints for data integrity
    __table_args__ = (
        db.CheckConstraint('quantity > 0', name='check_positive_quantity'),
        db.CheckConstraint('price >= 0', name='check_non_negative_price'),
        db.CheckConstraint('total_cost >= 0', name='check_non_negative_cost'),
        db.CheckConstraint("type IN ('buy', 'sell', 'settlement')", name='check_valid_type'),
    )

    @property
    def symbol(self):
        """Convenience access to the asset symbol."""
        if self.asset and self.asset.symbol:
            return self.asset.symbol
        return self.legacy_symbol

class PriceData(db.Model):
    """Price data model for asset prices."""
    __tablename__ = 'price_data'
    
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False, unique=True)
    current_price = db.Column(db.Float, nullable=False)
    volatility = db.Column(db.Float, default=0.02)
    history = db.Column(db.Text, default='[]')  # JSON string of price history
    updated_at = db.Column(db.DateTime, default=current_utc, onupdate=current_utc)
    
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
    drift = db.Column(db.Float, default=0.0)  # Mean return (mu) for GBM - default 0.0 for backward compatibility
    color = db.Column(db.String(7), nullable=False)  # Hex color code
    created_at = db.Column(db.DateTime, default=current_utc, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    final_price = db.Column(db.Float, nullable=True)  # Set when asset expires
    settled_at = db.Column(db.DateTime, nullable=True)  # When settlement occurred
    
    # Relationships
    settlements = db.relationship('Settlement', back_populates='asset', cascade='all, delete-orphan')
    transactions = db.relationship('Transaction', back_populates='asset', cascade='all, delete-orphan')
    
    # Database constraints for data integrity
    __table_args__ = (
        db.CheckConstraint('initial_price > 0', name='check_positive_initial_price'),
        db.CheckConstraint('current_price >= 0', name='check_non_negative_current_price'),
        db.CheckConstraint('volatility >= 0', name='check_non_negative_volatility'),
        db.CheckConstraint('volatility <= 1', name='check_volatility_max'),
        db.CheckConstraint('final_price IS NULL OR final_price >= 0', name='check_non_negative_final_price'),
    )
    
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
    def generate_symbol(length=3, include_day_of_month=False):
        """Generate a random symbol using uppercase letters."""
        _n_cycles = 0
        while True:
            symbol = ''.join(random.choices(string.ascii_uppercase, k=length))
            if include_day_of_month:
                symbol += str(current_utc().minute)
            # Check if symbol already exists
            if not Asset.query.filter_by(symbol=symbol).first():
                return symbol
            _n_cycles += 1
            if _n_cycles > 100000:
                raise ValueError("Failed to generate a unique symbol after 1000 attempts")

    @staticmethod
    def create_new_asset(initial_price=None, volatility=None, drift=None, minutes_to_expiry=None):
        """Create a new asset with random expiration between 5 minutes and 8 hours.
        
        Args:
            initial_price: Starting price for the asset
            volatility: Price volatility (random if None)
            drift: Mean return rate (random from normal distribution if None)
            minutes_to_expiry: Specific minutes to expiry (random 5-480 if None)
        
        Returns:
            New Asset instance (not yet added to session)
        """
        symbol = Asset.generate_symbol()
        
        # # Random volatility between 0.1% and 20% if not specified
        # if volatility is None:
        #     volatility = random.uniform(0.001, 0.20)
        
        # # Random drift from normal distribution if not specified
        # # Standard deviation ~0.01 means drift is typically within 1% of zero
        # # (68% of values within ±0.01, 95% within ±0.02)
        # if drift is None:
        #     drift = random.gauss(0.0, 0.001)

        if drift is None and volatility is not None:
            drift = np.random.normal(0.0, 0.005)
        elif volatility is None and drift is not None:
            volatility = np.random.lognormal(mean=np.log(0.05), sigma=0.5)
        elif drift is None and volatility is None:
            mu_0 = -0.001
            log_sigma_0 = np.log(0.05)
            cov = np.array([
                [0.001**2, 0.0],
                [0.0, 0.5**2]
            ])
            drift, log_sigma = np.random.multivariate_normal([mu_0, log_sigma_0], cov)
            volatility = np.exp(log_sigma)

        # Random initial price if not specified
        if initial_price is None:
            mean_init = 100.0
            sigma_logn = 1.0  # Reasonable spread
            mu_logn = np.log(mean_init) - (sigma_logn**2) / 2
            initial_price = np.random.lognormal(mean=mu_logn, sigma=sigma_logn)

        
        # # Ensure |drift| <= sigma to prevent explosive price movements
        # # Clip drift to [-sigma, sigma] range
        # drift = max(-volatility, min(volatility, drift))
        
        # Using exponential distribution for average around 30 minutes
        if minutes_to_expiry is None:
            # # Exponential distribution with mean ~25 minutes, clamped to range
            # lambda_param = 1.0 / 10.0  # mean = 1/lambda minutes
            # minutes_to_expiry = random.expovariate(lambda_param)
            mu = 10
            sigma = 2
            minutes_to_expiry = random.normalvariate(mu, sigma)
            # Clamp time to expiry
            minutes_to_expiry = max(5, min(15, minutes_to_expiry))

        expires_at = current_utc() + timedelta(minutes=minutes_to_expiry)

        asset = Asset(
            symbol=symbol,
            initial_price=initial_price,
            current_price=initial_price,
            volatility=volatility,
            drift=drift,
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
        self.settled_at = current_utc()
    
    def time_to_expiry(self):
        """Get time remaining until expiration.
        
        Returns:
            timedelta object or None if expired
        """
        if not self.is_active:
            return None
        
        now = current_utc()
        if now >= self.expires_at:
            return timedelta(0)
        
        return self.expires_at - now
    
    def is_expired(self):
        """Check if asset has expired."""
        return current_utc() >= self.expires_at
    
    def to_dict(self):
        """Convert asset to dictionary for API responses."""
        ttl = self.time_to_expiry()
        return {
            'symbol': self.symbol,
            'price': self.current_price,
            'initial_price': self.initial_price,
            'volatility': self.volatility,
            'drift': self.drift,
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
    legacy_symbol = db.Column('symbol', db.String(10), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    settlement_price = db.Column(db.Float, nullable=False)
    settlement_value = db.Column(db.Float, nullable=False)  # quantity * settlement_price
    settled_at = db.Column(db.DateTime, default=current_utc, nullable=False)
    
    # Relationship
    user = db.relationship('User', backref='settlements')
    asset = db.relationship('Asset', back_populates='settlements', lazy='joined')
    
    # Database constraints for data integrity
    __table_args__ = (
        db.CheckConstraint('quantity > 0', name='check_positive_settlement_quantity'),
        db.CheckConstraint('settlement_price >= 0', name='check_non_negative_settlement_price'),
        db.CheckConstraint('settlement_value >= 0', name='check_non_negative_settlement_value'),
    )
    
    @property
    def symbol(self):
        """Convenience accessor for asset symbol."""
        return self.asset.symbol if self.asset else None
    
    def __repr__(self):
        display_symbol = self.symbol or self.legacy_symbol
        return f'<Settlement {display_symbol} user={self.user_id} qty={self.quantity} value={self.settlement_value}>'
