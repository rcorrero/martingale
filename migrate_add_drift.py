#!/usr/bin/env python
"""
Migration script to add drift column to existing assets table.
This ensures backward compatibility by setting drift=0.0 for existing assets.
"""
import os
os.environ.setdefault('FLASK_ENV', 'development')

from app import create_app
from models import db, Asset
from sqlalchemy import inspect, text

def check_column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def migrate_add_drift():
    """Add drift column to assets table if it doesn't exist."""
    app = create_app()
    
    with app.app_context():
        print("="*80)
        print("MIGRATION: Add drift column to assets table")
        print("="*80)
        
        # Check if drift column already exists
        if check_column_exists('assets', 'drift'):
            print("✓ Column 'drift' already exists in assets table - no migration needed")
            print("="*80)
            return True
        
        print("Adding 'drift' column to assets table...")
        
        try:
            # Add drift column with default value 0.0
            # This is database-agnostic SQL that works with both SQLite and PostgreSQL
            with db.engine.connect() as conn:
                # For SQLite and PostgreSQL
                conn.execute(text('ALTER TABLE assets ADD COLUMN drift FLOAT DEFAULT 0.0'))
                conn.commit()
            
            print("✓ Successfully added 'drift' column with default value 0.0")
            
            # Verify the column was added
            if check_column_exists('assets', 'drift'):
                print("✓ Verified: 'drift' column now exists in assets table")
                
                # Check existing assets
                existing_assets = Asset.query.all()
                print(f"✓ Found {len(existing_assets)} existing assets")
                
                if existing_assets:
                    # Verify drift values
                    zero_drift_count = sum(1 for a in existing_assets if a.drift == 0.0)
                    print(f"✓ {zero_drift_count}/{len(existing_assets)} assets have drift=0.0 (backward compatible)")
                
                print("="*80)
                print("✅ MIGRATION COMPLETED SUCCESSFULLY")
                print("="*80)
                return True
            else:
                print("✗ ERROR: Column was not added successfully")
                return False
                
        except Exception as e:
            print(f"✗ ERROR during migration: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = migrate_add_drift()
    exit(0 if success else 1)
