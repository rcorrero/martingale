#!/usr/bin/env python
"""Check current assets in the database."""
import os
os.environ.setdefault('FLASK_ENV', 'development')

from app import create_app
from models import Asset, current_utc

app = create_app()

with app.app_context():
    # Get all assets
    all_assets = Asset.query.all()
    active_assets = Asset.query.filter_by(is_active=True).all()
    
    print(f"\n{'='*80}")
    print(f"ASSET DATABASE STATUS")
    print(f"{'='*80}")
    print(f"Total assets in database: {len(all_assets)}")
    print(f"Active assets: {len(active_assets)}")
    print(f"Inactive assets: {len(all_assets) - len(active_assets)}")
    
    if active_assets:
        print(f"\n{'='*80}")
        print(f"ACTIVE ASSETS")
        print(f"{'='*80}")
        print(f"{'Symbol':<8} {'Created':<20} {'Expires':<20} {'Hours Until':<12} {'Days Until':<12}")
        print(f"{'-'*80}")
        
        for asset in sorted(active_assets, key=lambda a: a.expires_at):
            now = current_utc()
            hours_until = (asset.expires_at - now).total_seconds() / 3600
            days_until = hours_until / 24
            
            print(f"{asset.symbol:<8} {asset.created_at.strftime('%Y-%m-%d %H:%M'):<20} "
                  f"{asset.expires_at.strftime('%Y-%m-%d %H:%M'):<20} "
                  f"{hours_until:>10.2f}h  {days_until:>10.2f}d")
    
    print(f"\n{'='*80}\n")
