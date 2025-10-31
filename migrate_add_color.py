#!/usr/bin/env python
"""
Migration script to add color column to assets table.
Run this once to update existing databases.
"""
import os
import sys
from sqlalchemy import text

# Set up the app context
os.environ.setdefault('FLASK_ENV', 'development')

from app import create_app
from models import db, Asset

def migrate_add_color():
    """Add color column to assets table and assign random colors to existing assets."""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if color column exists
            result = db.session.execute(text("PRAGMA table_info(assets)"))
            columns = [row[1] for row in result]
            
            if 'color' in columns:
                print("✓ Color column already exists")
            else:
                print("Adding color column to assets table...")
                db.session.execute(text("ALTER TABLE assets ADD COLUMN color VARCHAR(7)"))
                db.session.commit()
                print("✓ Color column added")
            
            # Update existing assets without colors
            assets_without_color = Asset.query.filter(
                (Asset.color == None) | (Asset.color == '')
            ).all()
            
            if assets_without_color:
                print(f"Assigning colors to {len(assets_without_color)} existing assets...")
                for asset in assets_without_color:
                    asset.color = Asset.get_random_color()
                db.session.commit()
                print(f"✓ Assigned colors to {len(assets_without_color)} assets")
            else:
                print("✓ All assets already have colors assigned")
            
            print("\n✓ Migration completed successfully!")
            
        except Exception as e:
            print(f"✗ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            sys.exit(1)

if __name__ == '__main__':
    migrate_add_color()
