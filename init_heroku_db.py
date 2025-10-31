#!/usr/bin/env python3
"""
Initialize the Heroku database with required tables and default data.
Run this script once after deploying to Heroku to set up the database.
"""
import os
import sys
from flask import Flask
from models import db, User, Portfolio, Transaction, PriceData
from config import config

def init_database():
    """Initialize database tables and default data."""
    print("🚀 Initializing Heroku database...")
    
    # Create Flask app with production config
    app = Flask(__name__)
    env = os.environ.get('FLASK_ENV', 'production')
    app.config.from_object(config[env])
    
    # Initialize database
    db.init_app(app)
    
    with app.app_context():
        try:
            # Create all tables
            print("📋 Creating database tables...")
            db.create_all()
            print("✅ Database tables created successfully")
            
            # Initialize default price data if needed
            if PriceData.query.count() == 0:
                print("💰 Initializing price data...")
                for symbol, config_data in app.config['ASSETS'].items():
                    price_data = PriceData(
                        symbol=symbol,
                        current_price=config_data['price'],
                        volatility=config_data['volatility'],
                        history='[]'
                    )
                    db.session.add(price_data)
                
                db.session.commit()
                print(f"✅ Initialized {len(app.config['ASSETS'])} assets in database")
            else:
                print(f"✅ Found {PriceData.query.count()} assets in database")
            
            print("🎉 Database initialization completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
            db.session.rollback()
            return False

if __name__ == '__main__':
    success = init_database()
    sys.exit(0 if success else 1)