"""
Database models for Martingale trading platform.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

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