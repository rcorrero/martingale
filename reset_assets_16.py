#!/usr/bin/env python
"""
Reset asset pool to exactly 16 assets with minute-based expiration.
This will:
1. Deactivate ALL existing assets
2. Settle all user positions and return cash
3. Create exactly 16 new assets with 5-480 minute expiration times
"""
import os
os.environ.setdefault('FLASK_ENV', 'development')

from app import create_app
from models import db, Asset, Portfolio, Settlement, current_utc

def reset_assets():
    """Reset asset pool to 16 minute-based assets."""
    app = create_app()
    
    with app.app_context():
        try:
            print("\n" + "="*80)
            print("RESETTING ASSET POOL TO 16 MINUTE-BASED ASSETS")
            print("="*80 + "\n")
            
            # Step 1: Get all existing assets
            all_assets = Asset.query.all()
            active_assets = [a for a in all_assets if a.is_active]
            print(f"Current status:")
            print(f"  - Total assets in database: {len(all_assets)}")
            print(f"  - Active assets: {len(active_assets)}")
            print(f"  - Inactive assets: {len(all_assets) - len(active_assets)}")
            
            # Step 2: Check expiration times of current active assets
            if active_assets:
                print(f"\nCurrent active asset expiration times:")
                now = current_utc()
                for asset in sorted(active_assets, key=lambda a: a.expires_at):
                    hours_until = (asset.expires_at - now).total_seconds() / 3600
                    days_until = hours_until / 24
                    print(f"  {asset.symbol}: {hours_until:.1f} hours ({days_until:.1f} days)")
            
            # Step 3: Mark all assets as inactive and settle positions
            print(f"\nDeactivating all {len(all_assets)} assets...")
            settled_count = 0
            for asset in all_assets:
                if asset.is_active:
                    # Mark as expired with current price as final
                    asset.expire(final_price=asset.current_price)
                    
                    # Return value to users who hold this asset
                    portfolios = Portfolio.query.all()
                    for portfolio in portfolios:
                        holdings = portfolio.get_holdings()
                        if asset.id in holdings and holdings[asset.id] > 0:
                            quantity = holdings[asset.id]
                            value = quantity * asset.current_price
                            
                            # Create settlement record
                            settlement = Settlement(
                                user_id=portfolio.user_id,
                                asset_id=asset.id,
                                legacy_symbol=asset.symbol,
                                quantity=quantity,
                                settlement_price=asset.current_price,
                                settlement_value=value
                            )
                            db.session.add(settlement)
                            
                            # Return cash
                            portfolio.cash += value
                            
                            # Remove holding
                            del holdings[asset.id]
                            portfolio.set_holdings(holdings)
                            
                            # Remove position info
                            position_info = portfolio.get_position_info()
                            if asset.id in position_info:
                                del position_info[asset.id]
                                portfolio.set_position_info(position_info)
                            
                            print(f"  ✓ Settled {quantity} {asset.symbol} for user {portfolio.user_id}: ${value:.2f}")
                            settled_count += 1
            
            db.session.commit()
            print(f"\n✓ Deactivated all assets and settled {settled_count} positions")
            
            # Step 4: Create exactly 16 new assets
            print(f"\nCreating 16 new assets with minute-based expiration...")
            new_assets = []
            for i in range(16):
                asset = Asset.create_new_asset(
                    initial_price=100.0,
                    volatility=None,  # Random 0.1% - 20%
                    minutes_to_expiry=None  # Random 5-480 minutes (exponential distribution)
                )
                db.session.add(asset)
                new_assets.append(asset)
                
                time_to_expiry_minutes = (asset.expires_at - current_utc()).total_seconds() / 60
                print(f"  {i+1:2d}. {asset.symbol}: "
                      f"volatility={asset.volatility*100:5.2f}%, "
                      f"expires in {time_to_expiry_minutes:6.1f} minutes "
                      f"({time_to_expiry_minutes/60:5.2f} hours), "
                      f"color={asset.color}")
            
            db.session.commit()
            
            # Step 5: Verify
            final_active = Asset.query.filter_by(is_active=True).count()
            
            print("\n" + "="*80)
            print("RESET COMPLETE")
            print("="*80)
            print(f"✓ Deactivated {len(all_assets)} old assets")
            print(f"✓ Settled {settled_count} positions")
            print(f"✓ Created {len(new_assets)} new assets")
            print(f"✓ Final active asset count: {final_active}")
            print(f"\nAll assets now use minute-based expiration (5-480 minutes)")
            print("="*80 + "\n")
            
        except Exception as e:
            print(f"\n✗ Failed to reset assets: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == '__main__':
    reset_assets()
