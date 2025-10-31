"""
Test script for expiring assets system.
Run this to verify the asset lifecycle works correctly.
"""
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Asset, User, Portfolio, Settlement, Transaction
from asset_manager import AssetManager
from config import config

def test_asset_creation():
    """Test creating new assets."""
    print("\n=== Testing Asset Creation ===")
    
    with app.app_context():
        # Create a few test assets
        asset1 = Asset.create_new_asset(initial_price=100.0, days_to_expiry=1)
        asset2 = Asset.create_new_asset(initial_price=100.0, days_to_expiry=15)
        asset3 = Asset.create_new_asset(initial_price=100.0, days_to_expiry=30)
        
        db.session.add_all([asset1, asset2, asset3])
        db.session.commit()
        
        print(f"✓ Created asset {asset1.symbol} (expires in 1 day)")
        print(f"✓ Created asset {asset2.symbol} (expires in 15 days)")
        print(f"✓ Created asset {asset3.symbol} (expires in 30 days)")
        
        # Verify
        active_count = Asset.query.filter_by(is_active=True).count()
        print(f"✓ Total active assets: {active_count}")
        
        return asset1, asset2, asset3

def test_asset_expiration():
    """Test expiring an asset immediately."""
    print("\n=== Testing Asset Expiration ===")
    
    with app.app_context():
        # Create asset that expires in 1 second
        asset = Asset(
            symbol=Asset.generate_symbol(),
            initial_price=100.0,
            current_price=105.0,
            volatility=0.05,
            expires_at=datetime.utcnow() + timedelta(seconds=1),
            is_active=True
        )
        db.session.add(asset)
        db.session.commit()
        
        print(f"✓ Created asset {asset.symbol} expiring in 1 second")
        
        # Wait for expiration
        import time
        time.sleep(2)
        
        # Mark as expired
        asset.expire(final_price=105.0)
        db.session.commit()
        
        print(f"✓ Expired asset {asset.symbol} at ${asset.final_price}")
        print(f"  - is_active: {asset.is_active}")
        print(f"  - settled_at: {asset.settled_at}")
        
        return asset

def test_settlement():
    """Test settling a user position in an expired asset."""
    print("\n=== Testing Settlement ===")
    
    with app.app_context():
        # Create test user
        user = User.query.filter_by(username='test_settlement_user').first()
        if not user:
            user = User()
            user.username = 'test_settlement_user'
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()
        
        # Create portfolio with holdings
        portfolio = Portfolio.query.filter_by(user_id=user.id).first()
        if not portfolio:
            portfolio = Portfolio(user_id=user.id, cash=100000.0)
            db.session.add(portfolio)
        
        # Create expired asset
        asset = Asset(
            symbol=Asset.generate_symbol(),
            initial_price=100.0,
            current_price=110.0,
            volatility=0.05,
            expires_at=datetime.utcnow() - timedelta(seconds=1),
            is_active=True
        )
        db.session.add(asset)
        db.session.commit()
        
        # Add holding
        holdings = portfolio.get_holdings()
        holdings[asset.symbol] = 10.0
        portfolio.set_holdings(holdings)
        
        position_info = portfolio.get_position_info()
        position_info[asset.symbol] = {'total_cost': 1000.0, 'total_quantity': 10.0}
        portfolio.set_position_info(position_info)
        
        initial_cash = portfolio.cash
        db.session.commit()
        
        print(f"✓ Created user with 10 shares of {asset.symbol}")
        print(f"  - Initial cash: ${initial_cash:.2f}")
        print(f"  - Asset price: ${asset.current_price:.2f}")
        
        # Expire and settle
        asset.expire(final_price=110.0)
        db.session.commit()
        
        # Create settlement
        settlement_value = 10.0 * 110.0
        settlement = Settlement(
            user_id=user.id,
            asset_id=asset.id,
            symbol=asset.symbol,
            quantity=10.0,
            settlement_price=110.0,
            settlement_value=settlement_value
        )
        db.session.add(settlement)
        
        # Update portfolio
        portfolio.cash += settlement_value
        holdings = portfolio.get_holdings()
        holdings[asset.symbol] = 0
        portfolio.set_holdings(holdings)
        
        db.session.commit()
        
        print(f"✓ Settled 10 shares at ${asset.final_price:.2f}")
        print(f"  - Settlement value: ${settlement_value:.2f}")
        print(f"  - New cash balance: ${portfolio.cash:.2f}")
        print(f"  - Cash increase: ${portfolio.cash - initial_cash:.2f}")

def test_asset_manager():
    """Test the AssetManager class."""
    print("\n=== Testing AssetManager ===")
    
    with app.app_context():
        manager = AssetManager(app.config)
        
        # Initialize pool
        print("Initializing asset pool...")
        assets = manager.initialize_asset_pool(count=5)
        print(f"✓ Created {len(assets)} assets")
        
        for asset in assets[:3]:
            ttl = asset.time_to_expiry()
            print(f"  - {asset.symbol}: volatility={asset.volatility:.4f}, expires in {ttl.days} days {ttl.seconds//3600} hours")
        
        # Get summary
        summary = manager.get_asset_summary()
        print(f"\n✓ Asset Summary:")
        print(f"  - Active assets: {summary['active_count']}")
        print(f"  - Average time to expiry: {summary['average_ttl_hours']:.1f} hours")
        print(f"  - Active symbols: {', '.join(summary['active_symbols'][:5])}...")
        
        # Test maintenance
        print(f"\nTesting pool maintenance...")
        maintenance = manager.maintain_asset_pool()
        print(f"✓ Maintenance complete:")
        print(f"  - Active assets: {maintenance['active_assets']}")
        print(f"  - Created assets: {maintenance['created_assets']}")

def test_full_lifecycle():
    """Test complete asset lifecycle: create -> trade -> expire -> settle -> replace."""
    print("\n=== Testing Full Lifecycle ===")
    
    with app.app_context():
        manager = AssetManager(app.config)
        
        # Create asset expiring soon
        asset = Asset(
            symbol=Asset.generate_symbol(),
            initial_price=100.0,
            current_price=100.0,
            volatility=0.05,
            expires_at=datetime.utcnow() + timedelta(seconds=2),
            is_active=True
        )
        db.session.add(asset)
        db.session.commit()
        
        print(f"✓ Created asset {asset.symbol}")
        
        # Create user with holdings
        user = User.query.filter_by(username='test_lifecycle_user').first()
        if not user:
            user = User()
            user.username = 'test_lifecycle_user'
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()
        
        portfolio = Portfolio.query.filter_by(user_id=user.id).first()
        if not portfolio:
            portfolio = Portfolio(user_id=user.id, cash=100000.0)
            db.session.add(portfolio)
        
        holdings = portfolio.get_holdings()
        holdings[asset.symbol] = 5.0
        portfolio.set_holdings(holdings)
        
        position_info = portfolio.get_position_info()
        position_info[asset.symbol] = {'total_cost': 500.0, 'total_quantity': 5.0}
        portfolio.set_position_info(position_info)
        
        initial_cash = portfolio.cash
        db.session.commit()
        
        print(f"✓ User holds 5 shares, cash: ${initial_cash:.2f}")
        
        # Wait for expiration
        import time
        print("⏱  Waiting for expiration...")
        time.sleep(3)
        
        # Update price before expiring
        asset.current_price = 105.0
        
        # Process expirations
        print("Processing expirations...")
        stats = manager.process_expirations()
        
        print(f"✓ Expiration processing complete:")
        print(f"  - Assets expired: {stats['expired_assets']}")
        print(f"  - Positions settled: {stats['settlement_stats'].get('positions_settled', 0)}")
        print(f"  - Total value settled: ${stats['settlement_stats'].get('total_value_settled', 0):.2f}")
        print(f"  - New assets created: {stats['maintenance_stats'].get('created_assets', 0)}")
        
        # Verify portfolio updated
        db.session.refresh(portfolio)
        print(f"✓ User portfolio updated:")
        print(f"  - New cash: ${portfolio.cash:.2f}")
        print(f"  - Cash increase: ${portfolio.cash - initial_cash:.2f}")
        
        # Verify settlement record
        settlement = Settlement.query.filter_by(user_id=user.id, symbol=asset.symbol).first()
        if settlement:
            print(f"✓ Settlement record created:")
            print(f"  - Quantity: {settlement.quantity}")
            print(f"  - Price: ${settlement.settlement_price:.2f}")
            print(f"  - Value: ${settlement.settlement_value:.2f}")

def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("EXPIRING ASSETS SYSTEM TEST SUITE")
    print("=" * 60)
    
    try:
        with app.app_context():
            # Initialize database
            db.create_all()
            print("✓ Database initialized")
        
        # Run tests
        test_asset_creation()
        test_asset_expiration()
        test_settlement()
        test_asset_manager()
        test_full_lifecycle()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == '__main__':
    config_name = os.environ.get('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    
    success = run_all_tests()
    sys.exit(0 if success else 1)
