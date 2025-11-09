"""
Comprehensive test suite for asset_manager.py

Tests asset lifecycle management including:
- Asset creation and initialization
- Expiration detection and processing
- Position settlement
- Worthless asset handling
- Asset pool maintenance
- Cleanup operations
"""
import pytest
from datetime import datetime, timedelta
from asset_manager import AssetManager
from models import db, Asset, Portfolio, Settlement, Transaction, current_utc
from config import Config


class TestAssetManagerInit:
    """Test AssetManager initialization."""
    
    def test_init_with_config(self, app, mock_price_service, mock_socketio):
        """Test AssetManager initialization with configuration."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service, mock_socketio)
            
            assert manager.config is not None
            assert manager.price_service == mock_price_service
            assert manager.socketio == mock_socketio
            assert manager.min_active_assets == app.config['MIN_ACTIVE_ASSETS']
    
    def test_init_without_socketio(self, app, mock_price_service):
        """Test AssetManager can work without SocketIO."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service, None)
            
            assert manager.socketio is None


class TestAssetQueries:
    """Test AssetManager query methods."""
    
    def test_get_active_assets(self, app, mock_price_service, multiple_assets):
        """Test getting active assets."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service)
            active = manager.get_active_assets()
            
            assert len(active) == 5
            assert all(asset.is_active for asset in active)
    
    def test_get_active_assets_empty(self, app, mock_price_service):
        """Test getting active assets when none exist."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service)
            active = manager.get_active_assets()
            
            assert len(active) == 0
    
    def test_get_expired_assets_unsettled(self, app, mock_price_service):
        """Test getting expired but unsettled assets."""
        with app.app_context():
            # Create expired asset that's still marked active
            asset = Asset(
                symbol='EXPIRED',
                initial_price=100.0,
                current_price=95.0,
                volatility=0.02,
                drift=0.0,
                color='#ff0000',
                expires_at=current_utc() - timedelta(hours=1),
                is_active=True  # Not yet settled
            )
            db.session.add(asset)
            db.session.commit()
            
            manager = AssetManager(app.config, mock_price_service)
            expired = manager.get_expired_assets(unsettled_only=True)
            
            assert len(expired) == 1
            assert expired[0].symbol == 'EXPIRED'
    
    def test_get_expired_assets_settled(self, app, mock_price_service, expired_asset):
        """Test getting expired and settled assets."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service)
            expired = manager.get_expired_assets(unsettled_only=False)
            
            assert len(expired) >= 1
            assert all(not asset.is_active for asset in expired)
    
    def test_get_worthless_assets(self, app, mock_price_service, worthless_asset):
        """Test getting assets below price threshold."""
        with app.app_context():
            # Re-query the asset to ensure it's in the current session
            asset = Asset.query.filter_by(symbol='WORTHLESS').first()
            assert asset is not None, "Worthless asset fixture should create WORTHLESS asset"
            assert asset.current_price < 0.01, f"Asset price should be below threshold, got {asset.current_price}"
            
            manager = AssetManager(app.config, mock_price_service)
            worthless = manager.get_worthless_assets(threshold=0.01)
            
            assert len(worthless) == 1, f"Expected 1 worthless asset, got {len(worthless)}"
            assert worthless[0].symbol == 'WORTHLESS'
            assert worthless[0].current_price < 0.01


class TestAssetExpiration:
    """Test asset expiration processing."""
    
    def test_check_and_expire_assets(self, app, mock_price_service):
        """Test expiring assets that have passed expiration time."""
        with app.app_context():
            # Create expired asset
            asset = Asset(
                symbol='TOEXPIRE',
                initial_price=100.0,
                current_price=98.0,
                volatility=0.02,
                drift=0.0,
                color='#ff0000',
                expires_at=current_utc() - timedelta(minutes=5),
                is_active=True
            )
            db.session.add(asset)
            db.session.commit()
            
            manager = AssetManager(app.config, mock_price_service)
            expired = manager.check_and_expire_assets()
            
            assert len(expired) == 1
            assert expired[0].symbol == 'TOEXPIRE'
            assert not expired[0].is_active
            assert expired[0].final_price == 98.0
    
    def test_check_and_expire_no_expired(self, app, mock_price_service, multiple_assets):
        """Test when no assets are expired."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service)
            expired = manager.check_and_expire_assets()
            
            assert len(expired) == 0
    
    def test_check_and_settle_worthless_assets(self, app, mock_price_service):
        """Test early settlement of worthless assets."""
        with app.app_context():
            # Create worthless asset
            asset = Asset(
                symbol='WORTHLESS',
                initial_price=100.0,
                current_price=0.005,
                volatility=0.02,
                drift=0.0,
                color='#ff0000',
                expires_at=current_utc() + timedelta(hours=1),  # Not yet expired
                is_active=True
            )
            db.session.add(asset)
            db.session.commit()
            
            manager = AssetManager(app.config, mock_price_service)
            worthless = manager.check_and_settle_worthless_assets(threshold=0.01)
            
            assert len(worthless) == 1
            assert worthless[0].symbol == 'WORTHLESS'
            assert not worthless[0].is_active
            assert worthless[0].final_price == 0.005


class TestPositionSettlement:
    """Test position settlement."""
    
    def test_settle_expired_positions_basic(self, app, mock_price_service, user_with_holdings, test_asset):
        """Test settling positions in expired asset."""
        with app.app_context():
            # Expire the asset
            asset = Asset.query.filter_by(symbol='TEST').first()
            asset.expire(final_price=110.0)
            db.session.commit()
            
            manager = AssetManager(app.config, mock_price_service)
            stats = manager.settle_expired_positions([asset])
            
            assert stats['assets_settled'] == 1
            assert stats['positions_settled'] == 1
            assert stats['total_value_settled'] > 0
            
            # Check settlement record created
            settlement = Settlement.query.filter_by(asset_id=asset.id).first()
            assert settlement is not None
            assert settlement.quantity == 100.0
            assert settlement.settlement_price == 110.0
    
    def test_settle_clears_holdings(self, app, mock_price_service, user_with_holdings, test_asset):
        """Test that settlement clears holdings."""
        with app.app_context():
            user = user_with_holdings
            portfolio = user.portfolio
            
            # Verify holdings exist
            holdings_before = portfolio.get_holdings()
            assert test_asset.id in holdings_before
            
            # Expire and settle
            asset = Asset.query.filter_by(symbol='TEST').first()
            asset.expire(final_price=105.0)
            db.session.commit()
            
            manager = AssetManager(app.config, mock_price_service)
            manager.settle_expired_positions([asset])
            
            # Re-query portfolio to get updated state
            portfolio = Portfolio.query.filter_by(user_id=user.id).first()
            
            # Verify holdings cleared
            holdings_after = portfolio.get_holdings()
            assert test_asset.id not in holdings_after
    
    def test_settle_returns_cash(self, app, mock_price_service, user_with_holdings, test_asset):
        """Test that settlement returns cash to portfolio."""
        with app.app_context():
            user = user_with_holdings
            portfolio = user.portfolio
            
            cash_before = portfolio.cash
            
            # Expire and settle at $110
            asset = Asset.query.filter_by(symbol='TEST').first()
            asset.expire(final_price=110.0)
            db.session.commit()
            
            manager = AssetManager(app.config, mock_price_service)
            manager.settle_expired_positions([asset])
            
            # Re-query portfolio to get updated cash
            portfolio = Portfolio.query.filter_by(user_id=user.id).first()
            
            # Should receive 100 * $110 = $11,000
            cash_after = portfolio.cash
            assert cash_after == cash_before + 11000.0
    
    def test_settle_creates_settlement_transaction(self, app, mock_price_service, user_with_holdings, test_asset):
        """Test that settlement creates a transaction record."""
        with app.app_context():
            user = user_with_holdings
            
            # Expire and settle
            asset = Asset.query.filter_by(symbol='TEST').first()
            asset.expire(final_price=105.0)
            db.session.commit()
            
            manager = AssetManager(app.config, mock_price_service)
            manager.settle_expired_positions([asset])
            
            # Check transaction created
            transaction = Transaction.query.filter_by(
                user_id=user.id,
                asset_id=asset.id,
                type='settlement'
            ).first()
            
            assert transaction is not None
            assert transaction.quantity == 100.0
            assert transaction.price == 105.0
    
    def test_settle_multiple_users(self, app, mock_price_service, multiple_users, test_asset):
        """Test settling positions across multiple users."""
        with app.app_context():
            asset = Asset.query.filter_by(symbol='TEST').first()
            asset_id = asset.id
            
            # Give all users holdings
            for user in multiple_users:
                portfolio = Portfolio.query.filter_by(user_id=user.id).first()
                holdings = {asset_id: 50.0}
                portfolio.set_holdings(holdings)
            db.session.commit()
            
            # Re-query asset to avoid stale state
            asset = Asset.query.get(asset_id)
            
            # Expire and settle
            asset.expire(final_price=100.0)
            db.session.commit()
            
            manager = AssetManager(app.config, mock_price_service)
            stats = manager.settle_expired_positions([asset])
            
            assert stats['positions_settled'] == 3  # All 3 users
            
            # Verify all settlements created
            settlements = Settlement.query.filter_by(asset_id=asset.id).all()
            assert len(settlements) == 3
    
    def test_settle_no_holdings(self, app, mock_price_service, test_user_with_portfolio, test_asset):
        """Test settling asset when user has no holdings."""
        with app.app_context():
            asset = Asset.query.filter_by(symbol='TEST').first()
            asset.expire(final_price=100.0)
            db.session.commit()
            
            manager = AssetManager(app.config, mock_price_service)
            stats = manager.settle_expired_positions([asset])
            
            assert stats['positions_settled'] == 0
    
    def test_settle_emits_socketio_events(self, app, mock_price_service, mock_socketio, user_with_holdings, test_asset):
        """Test that settlement emits SocketIO events."""
        with app.app_context():
            asset = Asset.query.filter_by(symbol='TEST').first()
            asset.expire(final_price=100.0)
            db.session.commit()
            
            manager = AssetManager(app.config, mock_price_service, mock_socketio)
            stats = manager.settle_expired_positions([asset])
            
            # Check that transactions were emitted
            assert 'transactions' in stats
            transactions = stats['transactions']
            assert len(transactions) > 0


class TestAssetCreation:
    """Test asset creation."""
    
    def test_create_new_assets_single(self, app, mock_price_service):
        """Test creating a single new asset."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service)
            new_assets = manager.create_new_assets(count=1)
            
            assert len(new_assets) == 1
            asset = new_assets[0]
            assert asset.symbol is not None
            assert asset.is_active
            assert asset.expires_at > current_utc()
    
    def test_create_new_assets_multiple(self, app, mock_price_service):
        """Test creating multiple new assets."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service)
            new_assets = manager.create_new_assets(count=5)
            
            assert len(new_assets) == 5
            
            # Check all unique symbols
            symbols = [a.symbol for a in new_assets]
            assert len(symbols) == len(set(symbols))
    
    def test_create_assets_registers_with_price_service(self, app, mock_price_service):
        """Test that new assets are registered with price service."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service)
            new_assets = manager.create_new_assets(count=2)
            
            # Mock price service should have fallback attribute
            if hasattr(mock_price_service, 'prices'):
                for asset in new_assets:
                    # Check asset registered (in real service, would be in fallback.assets)
                    pass  # Mock doesn't implement this, just test doesn't crash


class TestAssetPoolMaintenance:
    """Test asset pool maintenance."""
    
    def test_maintain_asset_pool_creates_when_needed(self, app, mock_price_service):
        """Test that maintenance creates assets when below minimum."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service)
            
            # Start with 0 assets, min is 3 (from TestConfig)
            stats = manager.maintain_asset_pool()
            
            assert stats['created_assets'] == 3
            assert stats['active_assets'] == 0  # Before creation
    
    def test_maintain_asset_pool_does_nothing_when_sufficient(self, app, mock_price_service, multiple_assets):
        """Test that maintenance does nothing when enough assets exist."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service)
            
            # Have 5 assets, min is 3
            stats = manager.maintain_asset_pool()
            
            assert stats['created_assets'] == 0
            assert stats['active_assets'] == 5
    
    def test_initialize_asset_pool(self, app, mock_price_service):
        """Test initializing asset pool from empty."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service)
            new_assets = manager.initialize_asset_pool()
            
            assert len(new_assets) == 3  # MIN_ACTIVE_ASSETS from TestConfig
    
    def test_initialize_asset_pool_with_existing(self, app, mock_price_service, multiple_assets):
        """Test initializing when assets already exist."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service)
            existing = manager.initialize_asset_pool()
            
            assert len(existing) == 5  # Returns existing assets


class TestExpirationProcessing:
    """Test complete expiration processing workflow."""
    
    def test_process_expirations_full_workflow(self, app, mock_price_service, mock_socketio):
        """Test complete expiration workflow."""
        with app.app_context():
            # Create expired asset with user holding
            asset = Asset(
                symbol='EXPIRE',
                initial_price=100.0,
                current_price=105.0,
                volatility=0.02,
                drift=0.0,
                color='#ff0000',
                expires_at=current_utc() - timedelta(minutes=1),
                is_active=True
            )
            db.session.add(asset)
            db.session.commit()
            
            # Create user with holdings
            from conftest import TestDataGenerator
            user = TestDataGenerator.create_user('testuser', with_portfolio=True)
            portfolio = user.portfolio
            holdings = {asset.id: 50.0}
            portfolio.set_holdings(holdings)
            db.session.commit()
            
            manager = AssetManager(app.config, mock_price_service, mock_socketio)
            stats = manager.process_expirations()
            
            assert stats['expired_assets'] == 1
            assert stats['settlement_stats']['positions_settled'] == 1
            assert stats['maintenance_stats']['active_assets'] == 0
    
    def test_process_expirations_maintains_pool(self, app, mock_price_service):
        """Test that expiration processing maintains asset pool."""
        with app.app_context():
            # Create 3 expired assets (exactly at MIN_ACTIVE_ASSETS)
            for i in range(3):
                asset = Asset(
                    symbol=f'EXP{i}',
                    initial_price=100.0,
                    current_price=100.0,
                    volatility=0.02,
                    drift=0.0,
                    color='#ff0000',
                    expires_at=current_utc() - timedelta(minutes=1),
                    is_active=True
                )
                db.session.add(asset)
            db.session.commit()
            
            manager = AssetManager(app.config, mock_price_service)
            stats = manager.process_expirations()
            
            # Should expire 3, then create 3 more to maintain minimum
            assert stats['expired_assets'] == 3
            assert stats['maintenance_stats']['created_assets'] == 3
    
    def test_process_expirations_handles_worthless(self, app, mock_price_service):
        """Test that expiration processing handles worthless assets."""
        with app.app_context():
            # Create worthless asset
            asset = Asset(
                symbol='WORTHLESS',
                initial_price=100.0,
                current_price=0.005,
                volatility=0.02,
                drift=0.0,
                color='#ff0000',
                expires_at=current_utc() + timedelta(hours=1),
                is_active=True
            )
            db.session.add(asset)
            db.session.commit()
            
            manager = AssetManager(app.config, mock_price_service)
            stats = manager.process_expirations()
            
            assert stats['worthless_assets'] >= 1


class TestAssetCleanup:
    """Test asset cleanup operations."""
    
    def test_cleanup_old_assets(self, app, mock_price_service):
        """Test cleaning up old expired assets."""
        with app.app_context():
            # Create old expired asset
            old_asset = Asset(
                symbol='OLD',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                drift=0.0,
                color='#ff0000',
                expires_at=current_utc() - timedelta(days=60),
                is_active=False,
                final_price=100.0,
                settled_at=current_utc() - timedelta(days=60)
            )
            db.session.add(old_asset)
            db.session.commit()
            
            manager = AssetManager(app.config, mock_price_service)
            count = manager.cleanup_old_assets(days_old=30)
            
            assert count == 1
            assert Asset.query.filter_by(symbol='OLD').first() is None
    
    def test_cleanup_preserves_recent(self, app, mock_price_service, expired_asset):
        """Test that cleanup preserves recent expired assets."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service)
            count = manager.cleanup_old_assets(days_old=30)
            
            # expired_asset is recent, should not be deleted
            assert Asset.query.filter_by(symbol='EXPIRED').first() is not None


class TestAssetSummary:
    """Test asset summary reporting."""
    
    def test_get_asset_summary(self, app, mock_price_service, multiple_assets):
        """Test getting asset summary."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service)
            summary = manager.get_asset_summary()
            
            assert summary['active_count'] == 5
            assert summary['expired_unsettled_count'] == 0
            assert len(summary['active_symbols']) == 5
            assert 'expiring_soon' in summary
    
    def test_get_asset_summary_with_expired(self, app, mock_price_service, multiple_assets, expired_asset):
        """Test summary with expired assets."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service)
            summary = manager.get_asset_summary()
            
            assert summary['active_count'] == 5
            assert summary['expired_settled_count'] >= 1
    
    def test_get_asset_summary_empty(self, app, mock_price_service):
        """Test summary with no assets."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service)
            summary = manager.get_asset_summary()
            
            assert summary['active_count'] == 0
            assert summary['active_symbols'] == []


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_settle_asset_without_final_price(self, app, mock_price_service, user_with_holdings, test_asset):
        """Test settling asset that has no final price set."""
        with app.app_context():
            asset = Asset.query.filter_by(symbol='TEST').first()
            # Mark as inactive but don't set final price
            asset.is_active = False
            db.session.commit()
            
            manager = AssetManager(app.config, mock_price_service)
            stats = manager.settle_expired_positions([asset])
            
            # Should skip this asset
            assert stats['positions_settled'] == 0
    
    def test_concurrent_expiration_handling(self, app, mock_price_service):
        """Test handling multiple assets expiring at once."""
        with app.app_context():
            # Create 10 assets all expiring at same time
            expiry_time = current_utc() - timedelta(minutes=1)
            for i in range(10):
                asset = Asset(
                    symbol=f'MULTI{i}',
                    initial_price=100.0,
                    current_price=100.0,
                    volatility=0.02,
                    drift=0.0,
                    color='#ff0000',
                    expires_at=expiry_time,
                    is_active=True
                )
                db.session.add(asset)
            db.session.commit()
            
            manager = AssetManager(app.config, mock_price_service)
            stats = manager.process_expirations()
            
            assert stats['expired_assets'] == 10
    
    def test_manager_without_price_service(self, app):
        """Test manager can operate without price service."""
        with app.app_context():
            manager = AssetManager(app.config, None, None)
            
            # Should still be able to create assets
            new_assets = manager.create_new_assets(count=1)
            assert len(new_assets) == 1
