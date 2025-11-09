"""
Comprehensive test suite for models.py

Tests database models including:
- User model and authentication
- Portfolio model and holdings management
- Transaction model and constraints
- Asset model and lifecycle
- Settlement model
- Database constraints and relationships
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from models import (
    db, User, Portfolio, Transaction, Asset, Settlement, current_utc
)


class TestUserModel:
    """Test User model functionality."""
    
    def test_create_user(self, app):
        """Test creating a user."""
        with app.app_context():
            user = User(username='testuser')
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()
            
            assert user.id is not None
            assert user.username == 'testuser'
            assert user.password_hash is not None
            assert user.password_hash != 'password123'
    
    def test_user_unique_username(self, app):
        """Test username uniqueness constraint."""
        with app.app_context():
            user1 = User(username='duplicate')
            user1.set_password('pass1')
            db.session.add(user1)
            db.session.commit()
            
            user2 = User(username='duplicate')
            user2.set_password('pass2')
            db.session.add(user2)
            
            with pytest.raises(IntegrityError):
                db.session.commit()
    
    def test_password_hashing(self, app):
        """Test password is hashed correctly."""
        with app.app_context():
            user = User(username='hashtest')
            user.set_password('mysecretpass')
            
            assert user.password_hash != 'mysecretpass'
            assert len(user.password_hash) > 20
    
    def test_password_verification(self, app, test_user):
        """Test password verification."""
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            
            assert user.check_password('TestPass123!')
            assert not user.check_password('wrongpassword')
            assert not user.check_password('')
    
    def test_user_portfolio_relationship(self, app, test_user_with_portfolio):
        """Test user-portfolio relationship."""
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            
            assert user.portfolio is not None
            assert user.portfolio.user_id == user.id
            assert user.portfolio.cash == 100000.0
    
    def test_user_cascade_delete(self, app, test_user_with_portfolio):
        """Test cascade delete of portfolio when user is deleted."""
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            portfolio_id = user.portfolio.id
            
            db.session.delete(user)
            db.session.commit()
            
            # Portfolio should be deleted too
            assert Portfolio.query.get(portfolio_id) is None


class TestPortfolioModel:
    """Test Portfolio model functionality."""
    
    def test_create_portfolio(self, app, test_user):
        """Test creating a portfolio."""
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            portfolio = Portfolio(user_id=user.id, cash=50000.0)
            portfolio.set_holdings({})
            portfolio.set_position_info({})
            db.session.add(portfolio)
            db.session.commit()
            
            assert portfolio.id is not None
            assert portfolio.cash == 50000.0
    
    def test_holdings_serialization(self, app, test_user_with_portfolio, test_asset):
        """Test holdings serialization and deserialization."""
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            portfolio = user.portfolio
            asset = Asset.query.filter_by(symbol='TEST').first()
            
            # Set holdings
            holdings = {asset.id: 100.0}
            portfolio.set_holdings(holdings)
            db.session.commit()
            
            # Retrieve and verify
            retrieved = portfolio.get_holdings()
            assert asset.id in retrieved
            assert retrieved[asset.id] == 100.0
    
    def test_holdings_by_symbol(self, app, test_user_with_portfolio, multiple_assets):
        """Test getting holdings by symbol."""
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            portfolio = user.portfolio
            assets = Asset.query.filter(Asset.symbol.like('TST%')).limit(3).all()
            
            # Set holdings for multiple assets
            holdings = {}
            for asset in assets:
                holdings[asset.id] = 50.0
            portfolio.set_holdings(holdings)
            db.session.commit()
            
            # Get by symbol
            by_symbol = portfolio.get_holdings_by_symbol()
            assert len(by_symbol) == 3
            assert all(symbol in by_symbol for symbol in ['TST0', 'TST1', 'TST2'])
    
    def test_position_info_management(self, app, test_user_with_portfolio, test_asset):
        """Test position info tracking."""
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            portfolio = user.portfolio
            asset = Asset.query.filter_by(symbol='TEST').first()
            
            # Set position info
            position_info = {
                asset.id: {
                    'total_cost': 5000.0,
                    'total_quantity': 50.0
                }
            }
            portfolio.set_position_info(position_info)
            db.session.commit()
            
            # Retrieve and verify
            retrieved = portfolio.get_position_info()
            assert asset.id in retrieved
            assert retrieved[asset.id]['total_cost'] == 5000.0
            assert retrieved[asset.id]['total_quantity'] == 50.0
    
    def test_cash_non_negative_constraint(self, app, test_user):
        """Test cash cannot be negative (database constraint)."""
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            portfolio = Portfolio(user_id=user.id, cash=-1000.0)
            portfolio.set_holdings({})
            db.session.add(portfolio)
            
            with pytest.raises(IntegrityError):
                db.session.commit()
    
    def test_cash_reasonable_constraint(self, app, test_user):
        """Test cash cannot exceed reasonable maximum."""
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            portfolio = Portfolio(user_id=user.id, cash=100000000001.0)
            portfolio.set_holdings({})
            db.session.add(portfolio)
            
            with pytest.raises(IntegrityError):
                db.session.commit()
    
    def test_empty_holdings(self, app, test_user_with_portfolio):
        """Test portfolio with no holdings."""
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            portfolio = user.portfolio
            
            holdings = portfolio.get_holdings()
            assert holdings == {} or len(holdings) == 0


class TestTransactionModel:
    """Test Transaction model functionality."""
    
    def test_create_buy_transaction(self, app, test_user_with_portfolio, test_asset):
        """Test creating a buy transaction."""
        with app.app_context():
            transaction = Transaction(
                user_id=test_user_with_portfolio.id,
                asset_id=test_asset.id,
                legacy_symbol=test_asset.symbol,
                timestamp=current_utc().timestamp() * 1000,
                type='buy',
                quantity=10.0,
                price=100.0,
                total_cost=1000.0
            )
            db.session.add(transaction)
            db.session.commit()
            
            assert transaction.id is not None
            assert transaction.type == 'buy'
            assert transaction.quantity == 10.0
    
    def test_create_sell_transaction(self, app, test_user_with_portfolio, test_asset):
        """Test creating a sell transaction."""
        with app.app_context():
            transaction = Transaction(
                user_id=test_user_with_portfolio.id,
                asset_id=test_asset.id,
                legacy_symbol=test_asset.symbol,
                timestamp=current_utc().timestamp() * 1000,
                type='sell',
                quantity=5.0,
                price=105.0,
                total_cost=525.0
            )
            db.session.add(transaction)
            db.session.commit()
            
            assert transaction.type == 'sell'
            assert transaction.total_cost == 525.0
    
    def test_transaction_asset_relationship(self, app, buy_transaction):
        """Test transaction-asset relationship."""
        with app.app_context():
            transaction = Transaction.query.first()
            
            assert transaction.asset is not None
            assert transaction.asset.symbol == transaction.legacy_symbol
    
    def test_transaction_user_relationship(self, app, buy_transaction):
        """Test transaction-user relationship."""
        with app.app_context():
            transaction = Transaction.query.first()
            
            assert transaction.user is not None
            assert transaction.user.username == 'testuser'
    
    def test_positive_quantity_constraint(self, app, test_user_with_portfolio, test_asset):
        """Test quantity must be positive."""
        with app.app_context():
            transaction = Transaction(
                user_id=test_user_with_portfolio.id,
                asset_id=test_asset.id,
                legacy_symbol=test_asset.symbol,
                timestamp=current_utc().timestamp() * 1000,
                type='buy',
                quantity=-10.0,  # Negative!
                price=100.0,
                total_cost=1000.0
            )
            db.session.add(transaction)
            
            with pytest.raises(IntegrityError):
                db.session.commit()
    
    def test_non_negative_price_constraint(self, app, test_user_with_portfolio, test_asset):
        """Test price must be non-negative."""
        with app.app_context():
            transaction = Transaction(
                user_id=test_user_with_portfolio.id,
                asset_id=test_asset.id,
                legacy_symbol=test_asset.symbol,
                timestamp=current_utc().timestamp() * 1000,
                type='buy',
                quantity=10.0,
                price=-5.0,  # Negative!
                total_cost=1000.0
            )
            db.session.add(transaction)
            
            with pytest.raises(IntegrityError):
                db.session.commit()
    
    def test_valid_transaction_type_constraint(self, app, test_user_with_portfolio, test_asset):
        """Test transaction type must be valid."""
        with app.app_context():
            transaction = Transaction(
                user_id=test_user_with_portfolio.id,
                asset_id=test_asset.id,
                legacy_symbol=test_asset.symbol,
                timestamp=current_utc().timestamp() * 1000,
                type='invalid_type',  # Invalid!
                quantity=10.0,
                price=100.0,
                total_cost=1000.0
            )
            db.session.add(transaction)
            
            with pytest.raises(IntegrityError):
                db.session.commit()
    
    def test_symbol_property(self, app, buy_transaction):
        """Test symbol property returns correct value."""
        with app.app_context():
            transaction = Transaction.query.first()
            
            assert transaction.symbol == 'TEST'
            assert transaction.symbol == transaction.asset.symbol


class TestAssetModel:
    """Test Asset model functionality."""
    
    def test_create_asset(self, app):
        """Test creating an asset."""
        with app.app_context():
            expires_at = current_utc() + timedelta(hours=1)
            asset = Asset(
                symbol='TEST',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                drift=0.0,
                color='#ff0000',
                expires_at=expires_at,
                is_active=True
            )
            db.session.add(asset)
            db.session.commit()
            
            assert asset.id is not None
            assert asset.symbol == 'TEST'
            assert asset.is_active is True
    
    def test_asset_unique_symbol(self, app):
        """Test symbol uniqueness constraint."""
        with app.app_context():
            asset1 = Asset(
                symbol='DUP',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                drift=0.0,
                color='#ff0000',
                expires_at=current_utc() + timedelta(hours=1)
            )
            db.session.add(asset1)
            db.session.commit()
            
            asset2 = Asset(
                symbol='DUP',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                drift=0.0,
                color='#00ff00',
                expires_at=current_utc() + timedelta(hours=2)
            )
            db.session.add(asset2)
            
            with pytest.raises(IntegrityError):
                db.session.commit()
    
    def test_positive_initial_price_constraint(self, app):
        """Test initial price must be positive."""
        with app.app_context():
            asset = Asset(
                symbol='BADPRICE',
                initial_price=-100.0,  # Negative!
                current_price=100.0,
                volatility=0.02,
                drift=0.0,
                color='#ff0000',
                expires_at=current_utc() + timedelta(hours=1)
            )
            db.session.add(asset)
            
            with pytest.raises(IntegrityError):
                db.session.commit()
    
    def test_volatility_constraints(self, app):
        """Test volatility must be between 0 and 1."""
        with app.app_context():
            # Test negative volatility
            asset = Asset(
                symbol='BADVOL1',
                initial_price=100.0,
                current_price=100.0,
                volatility=-0.1,  # Negative!
                drift=0.0,
                color='#ff0000',
                expires_at=current_utc() + timedelta(hours=1)
            )
            db.session.add(asset)
            
            with pytest.raises(IntegrityError):
                db.session.commit()
    
    def test_generate_symbol(self, app):
        """Test symbol generation."""
        with app.app_context():
            symbol = Asset.generate_symbol()
            
            assert len(symbol) == 3
            assert symbol.isupper()
            assert symbol.isalpha()
    
    def test_create_new_asset(self, app):
        """Test factory method for creating new assets."""
        with app.app_context():
            asset = Asset.create_new_asset(initial_price=100.0)
            db.session.add(asset)
            db.session.commit()
            
            assert asset.symbol is not None
            assert len(asset.symbol) == 3
            assert asset.initial_price == 100.0
            assert asset.is_active is True
            assert asset.expires_at > current_utc()
    
    def test_expire_asset(self, app, test_asset):
        """Test expiring an asset."""
        with app.app_context():
            asset = Asset.query.filter_by(symbol='TEST').first()
            
            asset.expire(final_price=95.0)
            db.session.commit()
            
            assert asset.is_active is False
            assert asset.final_price == 95.0
            assert asset.settled_at is not None
    
    def test_time_to_expiry(self, app):
        """Test time to expiry calculation."""
        with app.app_context():
            expires_in = timedelta(hours=2)
            asset = Asset(
                symbol='TTL',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                drift=0.0,
                color='#ff0000',
                expires_at=current_utc() + expires_in,
                is_active=True
            )
            db.session.add(asset)
            db.session.commit()
            
            ttl = asset.time_to_expiry()
            
            assert ttl is not None
            # Should be close to 2 hours (within 1 second tolerance)
            assert abs(ttl.total_seconds() - 7200) < 1
    
    def test_is_expired(self, app):
        """Test is_expired method."""
        with app.app_context():
            # Future expiration
            future_asset = Asset(
                symbol='FUTURE',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                drift=0.0,
                color='#ff0000',
                expires_at=current_utc() + timedelta(hours=1),
                is_active=True
            )
            db.session.add(future_asset)
            
            # Past expiration
            past_asset = Asset(
                symbol='PAST',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                drift=0.0,
                color='#ff0000',
                expires_at=current_utc() - timedelta(hours=1),
                is_active=False
            )
            db.session.add(past_asset)
            db.session.commit()
            
            assert not future_asset.is_expired()
            assert past_asset.is_expired()
    
    def test_to_dict(self, app, test_asset):
        """Test asset to dictionary conversion."""
        with app.app_context():
            asset = Asset.query.filter_by(symbol='TEST').first()
            asset_dict = asset.to_dict()
            
            assert asset_dict['symbol'] == 'TEST'
            assert asset_dict['price'] == 100.0
            assert asset_dict['is_active'] is True
            assert 'expires_at' in asset_dict
            assert 'time_to_expiry_seconds' in asset_dict


class TestSettlementModel:
    """Test Settlement model functionality."""
    
    def test_create_settlement(self, app, test_user_with_portfolio, expired_asset):
        """Test creating a settlement."""
        with app.app_context():
            settlement = Settlement(
                user_id=test_user_with_portfolio.id,
                asset_id=expired_asset.id,
                legacy_symbol=expired_asset.symbol,
                quantity=50.0,
                settlement_price=95.0,
                settlement_value=4750.0
            )
            db.session.add(settlement)
            db.session.commit()
            
            assert settlement.id is not None
            assert settlement.quantity == 50.0
            assert settlement.settlement_value == 4750.0
    
    def test_settlement_user_relationship(self, app, settlement_record):
        """Test settlement-user relationship."""
        with app.app_context():
            settlement = Settlement.query.first()
            
            assert settlement.user is not None
            assert settlement.user.username == 'testuser'
    
    def test_settlement_asset_relationship(self, app, settlement_record):
        """Test settlement-asset relationship."""
        with app.app_context():
            settlement = Settlement.query.first()
            
            assert settlement.asset is not None
            assert settlement.asset.symbol == 'EXPIRED'
    
    def test_positive_quantity_constraint(self, app, test_user_with_portfolio, expired_asset):
        """Test settlement quantity must be positive."""
        with app.app_context():
            settlement = Settlement(
                user_id=test_user_with_portfolio.id,
                asset_id=expired_asset.id,
                legacy_symbol=expired_asset.symbol,
                quantity=-50.0,  # Negative!
                settlement_price=95.0,
                settlement_value=4750.0
            )
            db.session.add(settlement)
            
            with pytest.raises(IntegrityError):
                db.session.commit()
    
    def test_symbol_property(self, app, settlement_record):
        """Test symbol property."""
        with app.app_context():
            settlement = Settlement.query.first()
            
            assert settlement.symbol == 'EXPIRED'
            assert settlement.symbol == settlement.asset.symbol


class TestDatabaseConstraints:
    """Test database constraints and data integrity."""
    
    def test_transaction_cascade_delete(self, app, test_user_with_portfolio, test_asset):
        """Test transactions are cascade deleted with user."""
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            
            # Create transaction
            transaction = Transaction(
                user_id=user.id,
                asset_id=test_asset.id,
                legacy_symbol=test_asset.symbol,
                timestamp=current_utc().timestamp() * 1000,
                type='buy',
                quantity=10.0,
                price=100.0,
                total_cost=1000.0
            )
            db.session.add(transaction)
            db.session.commit()
            
            transaction_id = transaction.id
            
            # Delete user
            db.session.delete(user)
            db.session.commit()
            
            # Transaction should be deleted
            assert Transaction.query.get(transaction_id) is None
    
    def test_settlement_cascade_delete(self, app, test_user_with_portfolio, expired_asset):
        """Test settlements are cascade deleted with asset."""
        with app.app_context():
            # Get the asset ID for later queries
            asset_id = expired_asset.id
            asset_symbol = expired_asset.symbol
            
            # Create settlement
            settlement = Settlement(
                user_id=test_user_with_portfolio.id,
                asset_id=asset_id,
                legacy_symbol=asset_symbol,
                quantity=50.0,
                settlement_price=95.0,
                settlement_value=4750.0
            )
            db.session.add(settlement)
            db.session.commit()
            
            settlement_id = settlement.id
            
            # Re-query asset to ensure it's in current session
            asset = Asset.query.get(asset_id)
            
            # Delete asset
            db.session.delete(asset)
            db.session.commit()
            
            # Settlement should be deleted
            assert Settlement.query.get(settlement_id) is None
