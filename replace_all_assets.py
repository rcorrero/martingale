#!/usr/bin/env python
"""
Replace all existing assets with new assets using updated expiration times.
This will:
1. Mark all existing assets as inactive
2. Clear all user holdings
3. Return holdings value to users' cash
4. Create 16 new assets with 5-480 minute expiration times
"""
import os

os.environ.setdefault('FLASK_ENV', 'development')

from app import create_app
from models import db, Asset, Portfolio, current_utc

def replace_all_assets():
    """Replace all existing assets with new ones."""
    app = create_app()
    
    with app.app_context():
        try:
            # Get all existing assets
            all_assets = Asset.query.all()
            print(f"Found {len(all_assets)} existing assets")
            
            # Mark all assets as inactive and settle any holdings
            settled_count = 0
            for asset in all_assets:
                if asset.is_active:
                    # Mark as expired with current price as final
                    asset.expire(final_price=asset.current_price)
                    print(f"  Marked {asset.symbol} as inactive")
                    
                    # Return value to users who hold this asset
                    portfolios = Portfolio.query.all()
                    for portfolio in portfolios:
                        holdings = portfolio.get_holdings()
                        if asset.id in holdings and holdings[asset.id] > 0:
                            quantity = holdings[asset.id]
                            value = quantity * asset.current_price
                            
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
                            
                            print(f"    Settled {quantity} shares for user {portfolio.user_id} at ${asset.current_price:.2f} = ${value:.2f}")
                            settled_count += 1
            
            db.session.commit()
            print(f"\nSettled {settled_count} positions")
            
            # Create 16 new assets with updated expiration times
            print("\nCreating 16 new assets...")
            new_assets = []
            for i in range(16):
                asset = Asset.create_new_asset(
                    initial_price=100.0,
                    volatility=None,  # Random
                    minutes_to_expiry=None  # Random 5-480 minutes
                )
                db.session.add(asset)
                new_assets.append(asset)
                
                time_to_expiry = (asset.expires_at - current_utc()).total_seconds() / 60
                print(f"  {i+1}. {asset.symbol}: volatility={asset.volatility:.4f}, expires in {time_to_expiry:.1f} minutes, color={asset.color}")
            
            db.session.commit()
            
            print(f"\n✓ Successfully replaced all assets")
            print(f"  - Deactivated {len(all_assets)} old assets")
            print(f"  - Settled {settled_count} positions")
            print(f"  - Created {len(new_assets)} new assets")
            
        except Exception as e:
            print(f"\n✗ Failed to replace assets: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == '__main__':
    replace_all_assets()
