#!/usr/bin/env python
"""
Add an asset that expires in 5 minutes for testing.
"""
import os
from datetime import datetime, timedelta

os.environ.setdefault('FLASK_ENV', 'development')

from app import create_app
from models import db, Asset

def add_short_expiry_asset():
    """Add an asset that expires in 5 minutes."""
    app = create_app()
    
    with app.app_context():
        try:
            # Create asset with 5 minute expiration
            minutes_to_expiry = 1
            expires_at = datetime.utcnow() + timedelta(minutes=minutes_to_expiry)
            
            symbol = Asset.generate_symbol()
            
            asset = Asset(
                symbol=symbol,
                initial_price=100.0,
                current_price=100.0,
                volatility=0.05,  # 5% volatility
                color=Asset.get_random_color(),
                expires_at=expires_at,
                is_active=True
            )
            
            db.session.add(asset)
            db.session.commit()
            
            print(f"✓ Created asset {symbol}")
            print(f"  Initial price: ${asset.initial_price}")
            print(f"  Volatility: {asset.volatility * 100}%")
            print(f"  Color: {asset.color}")
            print(f"  Expires at: {asset.expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"  Time to expiry: {minutes_to_expiry} minutes")
            
        except Exception as e:
            print(f"✗ Failed to create asset: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == '__main__':
    add_short_expiry_asset()
