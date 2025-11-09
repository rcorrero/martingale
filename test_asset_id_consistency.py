"""
Unit tests for consistent asset ID usage and backward compatibility.

Tests that assets are consistently referenced by ID throughout the application,
with proper fallback to symbol-based lookups for backward compatibility.
"""

import pytest
import json
from datetime import timedelta
from models import User, Asset, Portfolio, Transaction, Settlement, current_utc, db


class TestAssetIDConsistency:
    """Test asset ID consistency and backward compatibility."""

    @pytest.fixture(autouse=True)
    def setup(self, app):
        """Set up test fixtures for each test."""
        with app.app_context():
            # Create test user
            user = User(username='testuser', password_hash='dummy')
            db.session.add(user)
            db.session.commit()
            
            # Create test portfolio
            portfolio = Portfolio(user_id=user.id, cash=100000.0)
            db.session.add(portfolio)
            db.session.commit()
            
            self.user = user
            self.portfolio = portfolio
            
            yield
    
    def test_asset_get_by_id_or_symbol_with_id(self, app):
        """Test Asset.get_by_id_or_symbol prefers ID lookup."""
        with app.app_context():
            # Create asset
            asset = Asset(
                symbol='TST',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                color='#FF0000',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=True
            )
            db.session.add(asset)
            db.session.commit()
            
            # Lookup by ID should work
            found = Asset.get_by_id_or_symbol(asset_id=asset.id)
            assert found is not None
            assert found.id == asset.id
            assert found.symbol == 'TST'
    
    def test_asset_get_by_id_or_symbol_with_symbol(self, app):
        """Test Asset.get_by_id_or_symbol falls back to symbol."""
        with app.app_context():
            # Create asset
            asset = Asset(
                symbol='TST2',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                color='#00FF00',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=True
            )
            db.session.add(asset)
            db.session.commit()
            
            # Lookup by symbol should work
            found = Asset.get_by_id_or_symbol(symbol='TST2')
            assert found is not None
            assert found.symbol == 'TST2'
    
    def test_asset_get_by_id_or_symbol_active_only(self, app):
        """Test Asset.get_by_id_or_symbol respects active_only filter."""
        with app.app_context():
            # Create expired asset
            asset = Asset(
                symbol='EXP',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                color='#0000FF',
                expires_at=current_utc() - timedelta(minutes=1),
                is_active=False
            )
            db.session.add(asset)
            db.session.commit()
            
            # Should find with active_only=False
            found = Asset.get_by_id_or_symbol(asset_id=asset.id, active_only=False)
            assert found is not None
            
            # Should NOT find with active_only=True
            not_found = Asset.get_by_id_or_symbol(asset_id=asset.id, active_only=True)
            assert not_found is None
    
    def test_asset_get_by_id_or_symbol_id_preferred_over_symbol(self, app):
        """Test Asset.get_by_id_or_symbol prefers ID when both provided."""
        with app.app_context():
            # Create two different assets
            asset1 = Asset(
                symbol='ABC',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                color='#FF0000',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=True
            )
            asset2 = Asset(
                symbol='XYZ',
                initial_price=110.0,
                current_price=110.0,
                volatility=0.03,
                color='#00FF00',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=True
            )
            db.session.add_all([asset1, asset2])
            db.session.commit()
            
            # If both ID and symbol provided, ID should take precedence
            found = Asset.get_by_id_or_symbol(asset_id=asset1.id, symbol='XYZ')
            assert found is not None
            assert found.id == asset1.id
            assert found.symbol == 'ABC'  # asset1's symbol, not XYZ
    
    def test_portfolio_holdings_use_asset_id(self, app):
        """Test Portfolio holdings consistently use integer asset IDs."""
        with app.app_context():
            # Create asset
            asset = Asset(
                symbol='TST3',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                color='#FF00FF',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=True
            )
            db.session.add(asset)
            db.session.commit()
            
            # Set holdings using asset ID
            holdings = {asset.id: 150.5}
            self.portfolio.set_holdings(holdings)
            db.session.commit()
            
            # Retrieve holdings - should be keyed by integer ID
            retrieved = self.portfolio.get_holdings_map()
            assert asset.id in retrieved
            assert retrieved[asset.id] == 150.5
            assert isinstance(list(retrieved.keys())[0], int)
    
    def test_portfolio_get_asset_from_holdings(self, app):
        """Test Portfolio.get_asset_from_holdings method."""
        with app.app_context():
            # Create asset
            asset = Asset(
                symbol='TST4',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                color='#FFFF00',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=True
            )
            db.session.add(asset)
            db.session.commit()
            
            # Add to holdings
            holdings = {asset.id: 100.0}
            self.portfolio.set_holdings(holdings)
            db.session.commit()
            
            # Should retrieve asset from holdings
            found = self.portfolio.get_asset_from_holdings(asset.id)
            assert found is not None
            assert found.id == asset.id
            assert found.symbol == 'TST4'
            
            # Should return None for asset not in holdings
            not_found = self.portfolio.get_asset_from_holdings(99999)
            assert not_found is None
    
    def test_portfolio_backward_compatible_symbol_holdings(self, app):
        """Test Portfolio handles legacy symbol-based holdings."""
        with app.app_context():
            # Create asset
            asset = Asset(
                symbol='LEG',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                color='#00FFFF',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=True
            )
            db.session.add(asset)
            db.session.commit()
            
            # Simulate legacy storage with symbol as key
            legacy_holdings = json.dumps({'LEG': 75.0})
            self.portfolio.holdings = legacy_holdings
            db.session.commit()
            
            # get_holdings_map should normalize to ID
            retrieved = self.portfolio.get_holdings_map()
            assert asset.id in retrieved
            assert retrieved[asset.id] == 75.0
    
    def test_transaction_uses_asset_id(self, app):
        """Test Transaction correctly uses asset_id."""
        with app.app_context():
            # Create asset
            asset = Asset(
                symbol='TXN',
                initial_price=100.0,
                current_price=105.0,
                volatility=0.02,
                color='#FF8800',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=True
            )
            db.session.add(asset)
            db.session.commit()
            
            # Create transaction with asset_id
            from datetime import datetime
            txn = Transaction(
                user_id=self.user.id,
                asset_id=asset.id,
                legacy_symbol=asset.symbol,
                timestamp=datetime.now().timestamp() * 1000,
                type='buy',
                quantity=10.0,
                price=105.0,
                total_cost=1050.0
            )
            db.session.add(txn)
            db.session.commit()
            
            # Verify asset_id is set
            assert txn.asset_id == asset.id
            
            # Verify relationship works
            assert txn.asset is not None
            assert txn.asset.symbol == 'TXN'
    
    def test_settlement_uses_asset_id(self, app):
        """Test Settlement correctly uses asset_id."""
        with app.app_context():
            # Create asset
            asset = Asset(
                symbol='STL',
                initial_price=100.0,
                current_price=120.0,
                volatility=0.02,
                color='#8800FF',
                expires_at=current_utc() - timedelta(minutes=1),
                is_active=False,
                final_price=120.0
            )
            db.session.add(asset)
            db.session.commit()
            
            # Create settlement with asset_id
            settlement = Settlement(
                user_id=self.user.id,
                asset_id=asset.id,
                legacy_symbol=asset.symbol,
                quantity=50.0,
                settlement_price=120.0,
                settlement_value=6000.0
            )
            db.session.add(settlement)
            db.session.commit()
            
            # Verify asset_id is set
            assert settlement.asset_id == asset.id
            
            # Verify relationship works
            assert settlement.asset is not None
            assert settlement.asset.symbol == 'STL'
    
    def test_mixed_id_and_symbol_holdings(self, app):
        """Test Portfolio handles mixed ID and symbol holdings data."""
        with app.app_context():
            # Create two assets
            asset1 = Asset(
                symbol='MIX1',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                color='#FF0088',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=True
            )
            asset2 = Asset(
                symbol='MIX2',
                initial_price=200.0,
                current_price=200.0,
                volatility=0.03,
                color='#88FF00',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=True
            )
            db.session.add_all([asset1, asset2])
            db.session.commit()
            
            # Simulate mixed storage: one by ID (string), one by symbol
            mixed_holdings = json.dumps({
                str(asset1.id): 100.0,
                'MIX2': 200.0
            })
            self.portfolio.holdings = mixed_holdings
            db.session.commit()
            
            # get_holdings_map should normalize both to IDs
            retrieved = self.portfolio.get_holdings_map()
            assert asset1.id in retrieved
            assert asset2.id in retrieved
            assert retrieved[asset1.id] == 100.0
            assert retrieved[asset2.id] == 200.0


class TestAssetIDRaceConditions:
    """Test that asset ID usage prevents race conditions from symbol reuse."""

    @pytest.fixture(autouse=True)
    def setup(self, app):
        """Set up test fixtures for each test."""
        with app.app_context():
            user = User(username='testuser2', password_hash='dummy')
            db.session.add(user)
            db.session.commit()
            
            portfolio = Portfolio(user_id=user.id, cash=100000.0)
            db.session.add(portfolio)
            db.session.commit()
            
            self.user = user
            self.portfolio = portfolio
            
            yield
    
    def test_holdings_isolated_by_asset_id(self, app):
        """Test holdings for different assets remain properly isolated by ID."""
        with app.app_context():
            # Create first asset
            asset1 = Asset(
                symbol='AAA',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                color='#FF0000',
                expires_at=current_utc() + timedelta(minutes=5),
                is_active=True
            )
            db.session.add(asset1)
            db.session.commit()
            
            # Buy some of asset1
            holdings = {asset1.id: 50.0}
            self.portfolio.set_holdings(holdings)
            db.session.commit()
            
            # Expire asset1
            asset1.is_active = False
            asset1.final_price = 110.0
            db.session.commit()
            
            # Create new asset with different symbol
            asset2 = Asset(
                symbol='BBB',
                initial_price=90.0,
                current_price=90.0,
                volatility=0.02,
                color='#00FF00',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=True
            )
            db.session.add(asset2)
            db.session.commit()
            
            # Verify holdings still reference asset1, not asset2
            retrieved_holdings = self.portfolio.get_holdings_map()
            assert asset1.id in retrieved_holdings
            assert asset2.id not in retrieved_holdings
            assert retrieved_holdings[asset1.id] == 50.0
            
            # Verify we can look up the correct asset
            held_asset = self.portfolio.get_asset_from_holdings(asset1.id)
            assert held_asset.id == asset1.id
            assert held_asset.initial_price == 100.0  # Original asset
            assert not held_asset.is_active
    
    def test_transactions_track_correct_asset_by_id(self, app):
        """Test transactions reference correct asset via asset_id."""
        with app.app_context():
            from datetime import datetime
            
            # Create and trade asset1
            asset1 = Asset(
                symbol='CCC',
                initial_price=100.0,
                current_price=105.0,
                volatility=0.02,
                color='#FF0000',
                expires_at=current_utc() + timedelta(minutes=5),
                is_active=True
            )
            db.session.add(asset1)
            db.session.commit()
            
            txn1 = Transaction(
                user_id=self.user.id,
                asset_id=asset1.id,
                legacy_symbol='CCC',
                timestamp=datetime.now().timestamp() * 1000,
                type='buy',
                quantity=10.0,
                price=105.0,
                total_cost=1050.0
            )
            db.session.add(txn1)
            db.session.commit()
            
            # Expire asset1 and create asset2 with different symbol
            asset1.is_active = False
            db.session.commit()
            
            asset2 = Asset(
                symbol='DDD',
                initial_price=95.0,
                current_price=98.0,
                volatility=0.02,
                color='#00FF00',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=True
            )
            db.session.add(asset2)
            db.session.commit()
            
            txn2 = Transaction(
                user_id=self.user.id,
                asset_id=asset2.id,
                legacy_symbol='DDD',
                timestamp=datetime.now().timestamp() * 1000,
                type='buy',
                quantity=20.0,
                price=98.0,
                total_cost=1960.0
            )
            db.session.add(txn2)
            db.session.commit()
            
            # Verify transactions reference correct assets
            assert txn1.asset_id == asset1.id
            assert txn1.asset.initial_price == 100.0
            
            assert txn2.asset_id == asset2.id
            assert txn2.asset.initial_price == 95.0
            
            # Query transactions by asset_id
            asset1_txns = Transaction.query.filter_by(asset_id=asset1.id).all()
            asset2_txns = Transaction.query.filter_by(asset_id=asset2.id).all()
            
            assert len(asset1_txns) == 1
            assert len(asset2_txns) == 1
            assert asset1_txns[0].quantity == 10.0
            assert asset2_txns[0].quantity == 20.0
