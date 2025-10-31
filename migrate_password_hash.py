#!/usr/bin/env python3
"""
Database migration to fix password_hash column size.
Run this to update the password_hash column from VARCHAR(120) to VARCHAR(255).
"""
import os
import sys
from flask import Flask
from models import db
from config import config
from sqlalchemy import text

def migrate_password_hash_column():
    """Migrate password_hash column to support longer hashes."""
    print("🔧 Migrating password_hash column size...")
    
    # Create Flask app with production config
    app = Flask(__name__)
    env = os.environ.get('FLASK_ENV', 'production')
    app.config.from_object(config[env])
    
    # Initialize database
    db.init_app(app)
    
    with app.app_context():
        try:
            # Execute raw SQL to alter the column
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ALTER COLUMN password_hash TYPE VARCHAR(255);"))
            print("✅ Successfully migrated password_hash column to VARCHAR(255)")
            return True
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            # If the column is already the right size, that's okay
            if "does not exist" in str(e) or "already exists" in str(e):
                print("ℹ️ Column might already be the correct size")
                return True
            return False

if __name__ == '__main__':
    success = migrate_password_hash_column()
    sys.exit(0 if success else 1)