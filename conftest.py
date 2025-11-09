"""
Pytest configuration and shared fixtures for Martingale test suite.

This module provides:
- Test database setup and teardown
- Mock data generators
- Shared fixtures for models and services
- Test client configuration
"""
import pytest
import tempfile
import os
from datetime import datetime, timedelta
from decimal import Decimal
from app import create_app
from models import db, User, Portfolio, Asset, Transaction, Settlement, current_utc
from config import Config


class TestConfig(Config):
    """Test configuration class."""
    TESTING = True
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # In-memory database for tests
    INITIAL_CASH = 100000.0
    MIN_ACTIVE_ASSETS = 3  # Fewer assets for faster tests
    EXPIRATION_CHECK_INTERVAL = 1
    PRICE_UPDATE_INTERVAL = 0.1
    SECRET_KEY = 'test-secret-key'


@pytest.fixture(scope='function')
def app():
    """Create and configure a new app instance for each test."""
    # Import the module-level app which has all routes registered
    from app import app as flask_app
    
    # Override config for testing
    flask_app.config.from_object(TestConfig)
    
    # Use a temporary file-based SQLite DB to avoid in-memory connection
    # isolation issues across multiple connections/sessions.
    tmp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp_db.close()
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{tmp_db.name}"
    
    # Create application context and initialize schema
    try:
        with flask_app.app_context():
            db.create_all()
            yield flask_app
    finally:
        # Teardown: drop tables and remove temporary file
        try:
            with flask_app.app_context():
                db.session.remove()
                db.drop_all()
        except Exception:
            pass
        try:
            os.unlink(tmp_db.name)
        except Exception:
            pass


@pytest.fixture(scope='function')
def client(app):
    """Create a test client for the app."""
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    """Create a test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture(scope='function')
def db_session(app):
    """Create a database session for testing."""
    with app.app_context():
        yield db.session


# User fixtures
@pytest.fixture
def test_user(app):
    """Create a test user."""
    with app.app_context():
        # Check if user already exists
        user = User.query.filter_by(username='testuser').first()
        if not user:
            user = User(username='testuser')
            user.set_password('TestPass123!')
            db.session.add(user)
            db.session.commit()
        user_id = user.id  # Cache ID before session closes
        db.session.refresh(user)  # Ensure object is fully loaded
        # Return within context so object stays attached
        yield user


@pytest.fixture
def test_user_with_portfolio(app):
    """Create a test user with a portfolio."""
    with app.app_context():
        # Check if user already exists (may happen if DB not cleaned up properly)
        user = User.query.filter_by(username='testuser').first()
        if not user:
            user = User(username='testuser')
            user.set_password('TestPass123!')
            db.session.add(user)
            db.session.commit()
        
        # Check if portfolio exists
        portfolio = Portfolio.query.filter_by(user_id=user.id).first()
        if not portfolio:
            portfolio = Portfolio(
                user_id=user.id,
                cash=100000.0
            )
            portfolio.set_holdings({})
            portfolio.set_position_info({})
            db.session.add(portfolio)
            db.session.commit()
        
        db.session.refresh(user)
        db.session.refresh(portfolio)
        yield user


@pytest.fixture
def multiple_users(app):
    """Create multiple test users with portfolios."""
    with app.app_context():
        users = []
        for i in range(3):
            user = User(username=f'user{i}')
            user.set_password(f'TestPass{i}!')
            db.session.add(user)
            db.session.commit()
            
            portfolio = Portfolio(
                user_id=user.id,
                cash=100000.0
            )
            portfolio.set_holdings({})
            portfolio.set_position_info({})
            db.session.add(portfolio)
            users.append(user)
        
        db.session.commit()
        for user in users:
            db.session.refresh(user)
        yield users


# Asset fixtures
@pytest.fixture
def test_asset(app):
    """Create a single test asset."""
    with app.app_context():
        asset = Asset(
            symbol='TEST',
            initial_price=100.0,
            current_price=100.0,
            volatility=0.02,
            drift=0.0,
            color='#ff0000',
            expires_at=current_utc() + timedelta(hours=1),
            is_active=True
        )
        db.session.add(asset)
        db.session.commit()
        db.session.refresh(asset)
        yield asset


@pytest.fixture
def multiple_assets(app):
    """Create multiple test assets."""
    with app.app_context():
        assets = []
        for i in range(5):
            asset = Asset(
                symbol=f'TST{i}',
                initial_price=100.0,
                current_price=100.0 + (i * 10),
                volatility=0.02 + (i * 0.01),
                drift=0.0,
                color=Asset.get_random_color(),
                expires_at=current_utc() + timedelta(minutes=30 + (i * 10)),
                is_active=True
            )
            db.session.add(asset)
            assets.append(asset)
        
        db.session.commit()
        for asset in assets:
            db.session.refresh(asset)
        yield assets


@pytest.fixture
def expired_asset(app):
    """Create an expired asset."""
    with app.app_context():
        asset = Asset(
            symbol='EXPIRED',
            initial_price=100.0,
            current_price=95.0,
            volatility=0.02,
            drift=0.0,
            color='#ff0000',
            expires_at=current_utc() - timedelta(hours=1),
            is_active=False,
            final_price=95.0,
            settled_at=current_utc()
        )
        db.session.add(asset)
        db.session.commit()
        db.session.refresh(asset)
        yield asset


@pytest.fixture
def worthless_asset(app):
    """Create an asset with price below threshold."""
    with app.app_context():
        asset = Asset(
            symbol='WORTHLESS',
            initial_price=100.0,
            current_price=0.005,  # Below 0.01 threshold
            volatility=0.02,
            drift=0.0,
            color='#ff0000',
            expires_at=current_utc() + timedelta(hours=1),
            is_active=True
        )
        db.session.add(asset)
        db.session.commit()
        db.session.refresh(asset)
        yield asset


# Portfolio fixtures with holdings
@pytest.fixture
def user_with_holdings(app, test_asset):
    """Create a user with holdings in test asset."""
    with app.app_context():
        # Check if user already exists
        user = User.query.filter_by(username='holdingsuser').first()
        if not user:
            user = User(username='holdingsuser')
            user.set_password('TestPass123!')
            db.session.add(user)
            db.session.commit()
        
        # Check if portfolio exists
        portfolio = Portfolio.query.filter_by(user_id=user.id).first()
        if not portfolio:
            portfolio = Portfolio(
                user_id=user.id,
                cash=50000.0
            )
            holdings = {test_asset.id: 100.0}
            position_info = {
                test_asset.id: {
                    'total_cost': 10000.0,
                    'total_quantity': 100.0
                }
            }
            portfolio.set_holdings(holdings)
            portfolio.set_position_info(position_info)
            db.session.add(portfolio)
            db.session.commit()
        
        db.session.refresh(user)
        db.session.refresh(portfolio)
        yield user


# Transaction fixtures
@pytest.fixture
def buy_transaction(app, test_user_with_portfolio, test_asset):
    """Create a buy transaction."""
    with app.app_context():
        # Re-query objects to ensure they're in the current session
        user = User.query.filter_by(username='testuser').first()
        asset = Asset.query.filter_by(symbol='TEST').first()
        
        transaction = Transaction(
            user_id=user.id,
            asset_id=asset.id,
            legacy_symbol=asset.symbol,
            timestamp=current_utc().timestamp() * 1000,
            type='buy',
            quantity=10.0,
            price=100.0,
            total_cost=1000.0
        )
        db.session.add(transaction)
        db.session.commit()
        db.session.refresh(transaction)
        yield transaction


@pytest.fixture
def sell_transaction(app, test_user_with_portfolio, test_asset):
    """Create a sell transaction."""
    with app.app_context():
        # Re-query objects to ensure they're in the current session
        user = User.query.filter_by(username='testuser').first()
        asset = Asset.query.filter_by(symbol='TEST').first()
        
        transaction = Transaction(
            user_id=user.id,
            asset_id=asset.id,
            legacy_symbol=asset.symbol,
            timestamp=current_utc().timestamp() * 1000,
            type='sell',
            quantity=5.0,
            price=105.0,
            total_cost=525.0
        )
        db.session.add(transaction)
        db.session.commit()
        db.session.refresh(transaction)
        yield transaction


# Settlement fixtures
@pytest.fixture
def settlement_record(app, test_user_with_portfolio, expired_asset):
    """Create a settlement record."""
    with app.app_context():
        # Re-query objects to ensure they're in the current session
        user = User.query.filter_by(username='testuser').first()
        asset = Asset.query.filter_by(symbol='EXPIRED').first()
        
        settlement = Settlement(
            user_id=user.id,
            asset_id=asset.id,
            legacy_symbol=asset.symbol,
            quantity=50.0,
            settlement_price=95.0,
            settlement_value=4750.0,
            settled_at=current_utc()
        )
        db.session.add(settlement)
        db.session.commit()
        db.session.refresh(settlement)
        yield settlement


# Authentication fixtures
@pytest.fixture
def authenticated_client(app, client, test_user):
    """Create an authenticated test client."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(test_user.id)
    return client


@pytest.fixture
def authenticated_client_with_holdings(app, client, user_with_holdings):
    """Create an authenticated test client for user with holdings."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_with_holdings.id)
    return client


# Helper fixtures
@pytest.fixture
def mock_price_service():
    """Create a mock price service for testing."""
    class MockPriceService:
        def __init__(self):
            self.prices = {}
            self.history = {}
        
        def get_current_prices(self):
            return self.prices
        
        def get_price_history(self, limit=100):
            return self.history
        
        def set_price(self, symbol, price, timestamp=None):
            if timestamp is None:
                timestamp = current_utc().timestamp() * 1000
            self.prices[symbol] = {
                'price': price,
                'last_update': timestamp
            }
        
        def sync_assets_from_db(self, assets):
            """Mock sync method."""
            for asset in assets:
                if asset.symbol not in self.prices:
                    self.set_price(asset.symbol, asset.current_price)
    
    return MockPriceService()


@pytest.fixture
def mock_socketio():
    """Create a mock SocketIO for testing."""
    class MockSocketIO:
        def __init__(self):
            self.emitted_events = []
        
        def emit(self, event, data, **kwargs):
            self.emitted_events.append({
                'event': event,
                'data': data,
                'kwargs': kwargs
            })
        
        def clear_events(self):
            self.emitted_events = []
        
        def get_events(self, event_name=None):
            if event_name:
                return [e for e in self.emitted_events if e['event'] == event_name]
            return self.emitted_events
    
    return MockSocketIO()


# Data generator helpers
class TestDataGenerator:
    """Helper class for generating test data."""
    
    @staticmethod
    def create_user(username='testuser', password='TestPass123!', with_portfolio=True):
        """Create a user with optional portfolio."""
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        if with_portfolio:
            portfolio = Portfolio(
                user_id=user.id,
                cash=100000.0
            )
            portfolio.set_holdings({})
            portfolio.set_position_info({})
            db.session.add(portfolio)
            db.session.commit()
        
        return user
    
    @staticmethod
    def create_asset(symbol='TEST', price=100.0, volatility=0.02, expires_in_hours=1):
        """Create an asset."""
        asset = Asset(
            symbol=symbol,
            initial_price=price,
            current_price=price,
            volatility=volatility,
            drift=0.0,
            color=Asset.get_random_color(),
            expires_at=current_utc() + timedelta(hours=expires_in_hours),
            is_active=True
        )
        db.session.add(asset)
        db.session.commit()
        return asset
    
    @staticmethod
    def create_transaction(user, asset, trade_type='buy', quantity=10.0, price=100.0):
        """Create a transaction."""
        total_cost = quantity * price
        transaction = Transaction(
            user_id=user.id,
            asset_id=asset.id,
            legacy_symbol=asset.symbol,
            timestamp=current_utc().timestamp() * 1000,
            type=trade_type,
            quantity=quantity,
            price=price,
            total_cost=total_cost
        )
        db.session.add(transaction)
        db.session.commit()
        return transaction


@pytest.fixture
def data_generator(app):
    """Provide test data generator."""
    with app.app_context():
        return TestDataGenerator()


# Helper to reload detached objects
def reload_object(obj):
    """Reload a detached object from the database."""
    return db.session.merge(obj)
