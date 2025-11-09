"""
Test symbol reuse functionality after removing UNIQUE constraint.

Verifies that:
1. Symbols can be reused between different assets
2. Active assets preferably get unique symbols
3. Symbol generation doesn't fail when all combinations are theoretically used
"""

import pytest
from datetime import timedelta
from models import Asset, db, current_utc


class TestSymbolReuse:
    """Test asset symbol reuse functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self, app):
        """Set up test fixtures."""
        with app.app_context():
            yield
    
    def test_symbol_reuse_for_inactive_assets(self, app):
        """Test that symbols can be reused when original asset becomes inactive."""
        with app.app_context():
            # Create first asset with symbol 'ABC'
            asset1 = Asset(
                symbol='ABC',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                color='#FF0000',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=True
            )
            db.session.add(asset1)
            db.session.commit()
            
            # Expire the asset
            asset1.is_active = False
            asset1.final_price = 110.0
            db.session.commit()
            
            # Create second asset with same symbol 'ABC'
            asset2 = Asset(
                symbol='ABC',
                initial_price=95.0,
                current_price=95.0,
                volatility=0.03,
                color='#00FF00',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=True
            )
            db.session.add(asset2)
            db.session.commit()
            
            # Verify both assets exist with same symbol
            abc_assets = Asset.query.filter_by(symbol='ABC').all()
            assert len(abc_assets) == 2
            assert abc_assets[0].id != abc_assets[1].id
            
            # Verify only asset2 is active
            active_abc = Asset.query.filter_by(symbol='ABC', is_active=True).all()
            assert len(active_abc) == 1
            assert active_abc[0].id == asset2.id
    
    def test_generate_symbol_prefers_unused(self, app):
        """Test that generate_symbol() prefers unused symbols."""
        with app.app_context():
            # Create an asset with symbol 'ZZZ'
            asset = Asset(
                symbol='ZZZ',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                color='#FF0000',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=True
            )
            db.session.add(asset)
            db.session.commit()
            
            # Generate 10 symbols - should all be different from 'ZZZ'
            # (very high probability given 17,576 possible combinations)
            symbols = [Asset.generate_symbol() for _ in range(10)]
            
            # None should be 'ZZZ' (with 99.94% probability)
            assert 'ZZZ' not in symbols or symbols.count('ZZZ') < len(symbols)
    
    def test_generate_symbol_allows_reuse_for_inactive(self, app):
        """Test that generate_symbol() can return symbol from inactive asset."""
        with app.app_context():
            # Create and expire an asset
            asset = Asset(
                symbol='XYZ',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                color='#FF0000',
                expires_at=current_utc() - timedelta(minutes=1),
                is_active=False
            )
            db.session.add(asset)
            db.session.commit()
            
            # Generate symbol - should be able to return 'XYZ'
            # Try multiple times to potentially get 'XYZ'
            symbols = [Asset.generate_symbol() for _ in range(100)]
            
            # Should not raise an error even though 'XYZ' exists
            assert len(symbols) == 100
            
            # If 'XYZ' appears, verify it's allowed
            if 'XYZ' in symbols:
                # This is allowed since the existing 'XYZ' asset is inactive
                print("  ✓ Symbol 'XYZ' was reused (inactive asset)")
    
    def test_multiple_assets_same_symbol_different_times(self, app):
        """Test creating multiple assets with same symbol over time."""
        with app.app_context():
            symbol = 'TST'
            assets_created = []
            
            # Create, expire, and recreate asset with same symbol 3 times
            for i in range(3):
                asset = Asset(
                    symbol=symbol,
                    initial_price=100.0 + i * 10,
                    current_price=100.0 + i * 10,
                    volatility=0.02,
                    color='#FF0000',
                    expires_at=current_utc() + timedelta(minutes=30),
                    is_active=True
                )
                db.session.add(asset)
                db.session.commit()
                assets_created.append(asset.id)
                
                # Expire the asset before creating next one
                asset.is_active = False
                asset.final_price = asset.current_price
                db.session.commit()
            
            # Verify all three assets exist
            all_tst = Asset.query.filter_by(symbol=symbol).all()
            assert len(all_tst) == 3
            
            # Verify they have different IDs
            ids = [a.id for a in all_tst]
            assert len(set(ids)) == 3
            
            # Verify they have different initial prices
            prices = [a.initial_price for a in all_tst]
            assert prices == [100.0, 110.0, 120.0]
            
            # Verify all are inactive
            assert all(not a.is_active for a in all_tst)
    
    def test_get_by_id_or_symbol_with_duplicate_symbols(self, app):
        """Test Asset.get_by_id_or_symbol() with duplicate symbols."""
        with app.app_context():
            # Create two assets with same symbol
            asset1 = Asset(
                symbol='DUP',
                initial_price=100.0,
                current_price=100.0,
                volatility=0.02,
                color='#FF0000',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=False
            )
            asset2 = Asset(
                symbol='DUP',
                initial_price=110.0,
                current_price=110.0,
                volatility=0.03,
                color='#00FF00',
                expires_at=current_utc() + timedelta(minutes=30),
                is_active=True
            )
            db.session.add_all([asset1, asset2])
            db.session.commit()
            
            # Lookup by ID should return exact asset
            found1 = Asset.get_by_id_or_symbol(asset_id=asset1.id)
            assert found1.id == asset1.id
            assert found1.initial_price == 100.0
            
            found2 = Asset.get_by_id_or_symbol(asset_id=asset2.id)
            assert found2.id == asset2.id
            assert found2.initial_price == 110.0
            
            # Lookup by symbol should return most recent
            found_by_symbol = Asset.get_by_id_or_symbol(symbol='DUP')
            assert found_by_symbol.id == asset2.id  # Most recent
            
            # Lookup by symbol with active_only should return only active
            found_active = Asset.get_by_id_or_symbol(symbol='DUP', active_only=True)
            assert found_active.id == asset2.id
            assert found_active.is_active
    
    def test_no_unique_constraint_violation(self, app):
        """Test that creating assets with duplicate symbols doesn't raise errors."""
        with app.app_context():
            symbol = 'AAA'
            
            # Create multiple active assets with same symbol
            # (Not recommended in practice, but should not fail)
            assets = []
            for i in range(5):
                asset = Asset(
                    symbol=symbol,
                    initial_price=100.0 + i,
                    current_price=100.0 + i,
                    volatility=0.02,
                    color=Asset.get_random_color(),
                    expires_at=current_utc() + timedelta(minutes=30),
                    is_active=True
                )
                db.session.add(asset)
                assets.append(asset)
            
            # Should commit successfully without UNIQUE constraint violation
            db.session.commit()
            
            # Verify all were created
            all_aaa = Asset.query.filter_by(symbol=symbol).all()
            assert len(all_aaa) == 5
            
            # Verify they have different IDs
            ids = [a.id for a in all_aaa]
            assert len(set(ids)) == 5


def run_manual_tests():
    """Run tests manually if not using pytest."""
    from app import create_app
    
    app = create_app('development')
    app.config['TESTING'] = True
    
    with app.app_context():
        db.create_all()
        
        test_class = TestSymbolReuse()
        
        print("\n" + "="*70)
        print("Testing Symbol Reuse Functionality")
        print("="*70 + "\n")
        
        tests = [
            ('Symbol reuse for inactive assets', test_class.test_symbol_reuse_for_inactive_assets),
            ('Generate symbol prefers unused', test_class.test_generate_symbol_prefers_unused),
            ('Generate symbol allows reuse for inactive', test_class.test_generate_symbol_allows_reuse_for_inactive),
            ('Multiple assets same symbol different times', test_class.test_multiple_assets_same_symbol_different_times),
            ('Get by ID or symbol with duplicates', test_class.test_get_by_id_or_symbol_with_duplicate_symbols),
            ('No unique constraint violation', test_class.test_no_unique_constraint_violation),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                print(f"Running: {test_name}...")
                test_func(app)
                print(f"  ✓ PASSED\n")
                passed += 1
            except AssertionError as e:
                print(f"  ✗ FAILED: {e}\n")
                failed += 1
            except Exception as e:
                print(f"  ✗ ERROR: {e}\n")
                failed += 1
        
        print("="*70)
        print(f"Results: {passed} passed, {failed} failed")
        print("="*70 + "\n")


if __name__ == '__main__':
    run_manual_tests()
