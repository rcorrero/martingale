"""
Test that price service properly syncs drift and volatility from database at startup.
"""
import pytest
from app import app, price_service
from models import Asset, current_utc, db


def test_price_service_syncs_from_database_at_startup():
    """Test that price service initializes with correct drift and volatility from database."""
    with app.app_context():
        # Get active assets from database
        now = current_utc()
        active_assets = Asset.query.filter_by(is_active=True).filter(Asset.expires_at > now).all()
        
        # Ensure we have some active assets to test
        assert len(active_assets) > 0, "Database should have active assets"
        
        # Verify each database asset has matching values in price service
        for asset in active_assets:
            assert asset.symbol in price_service.fallback.assets, \
                f"Asset {asset.symbol} from database should be in price service"
            
            fallback_data = price_service.fallback.assets[asset.symbol]
            
            # Check volatility matches
            assert fallback_data['volatility'] == asset.volatility, \
                f"Volatility mismatch for {asset.symbol}: " \
                f"DB={asset.volatility}, Service={fallback_data['volatility']}"
            
            # Check drift matches
            assert fallback_data['drift'] == asset.drift, \
                f"Drift mismatch for {asset.symbol}: " \
                f"DB={asset.drift}, Service={fallback_data['drift']}"
            
            # Check price matches (should be current_price from DB)
            assert fallback_data['price'] == asset.current_price, \
                f"Price mismatch for {asset.symbol}: " \
                f"DB={asset.current_price}, Service={fallback_data['price']}"


def test_price_service_removes_inactive_assets():
    """Test that price service doesn't contain inactive or expired assets."""
    with app.app_context():
        now = current_utc()
        
        # Get all inactive or expired assets
        inactive_assets = Asset.query.filter(
            (Asset.is_active == False) | (Asset.expires_at <= now)
        ).all()
        
        # Verify none of these are in the price service
        for asset in inactive_assets:
            assert asset.symbol not in price_service.fallback.assets, \
                f"Inactive/expired asset {asset.symbol} should not be in price service"


def test_sync_assets_from_db_updates_existing_assets():
    """Test that sync_assets_from_db updates volatility and drift for existing assets."""
    with app.app_context():
        now = current_utc()
        active_assets = Asset.query.filter_by(is_active=True).filter(Asset.expires_at > now).all()
        
        if not active_assets:
            pytest.skip("No active assets to test")
        
        # Get first asset
        test_asset = active_assets[0]
        original_vol = test_asset.volatility
        original_drift = test_asset.drift
        
        # Manually modify the price service values
        price_service.fallback.assets[test_asset.symbol]['volatility'] = 0.999
        price_service.fallback.assets[test_asset.symbol]['drift'] = 0.888
        
        # Sync should restore correct values
        price_service.sync_assets_from_db(active_assets)
        
        # Verify values are restored
        assert price_service.fallback.assets[test_asset.symbol]['volatility'] == original_vol
        assert price_service.fallback.assets[test_asset.symbol]['drift'] == original_drift


def test_drift_constrained_to_volatility():
    """Test that drift values are constrained to [-volatility, volatility] range."""
    with app.app_context():
        now = current_utc()
        active_assets = Asset.query.filter_by(is_active=True).filter(Asset.expires_at > now).all()
        
        for asset in active_assets:
            fallback_data = price_service.fallback.assets[asset.symbol]
            
            # When prices are updated, drift should be clamped
            # Verify the constraint: |drift| <= volatility
            assert abs(fallback_data['drift']) <= fallback_data['volatility'], \
                f"Drift {fallback_data['drift']} exceeds volatility {fallback_data['volatility']} " \
                f"for asset {asset.symbol}"
