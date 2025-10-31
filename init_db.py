"""
Database initialization and migration script.
Run this to set up the database schema.
"""
from app import app
from models import db, User, Portfolio, Transaction, PriceData
import json
import os

def init_database():
    """Initialize database with tables."""
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created successfully!")
        
        # Initialize default price data if needed
        if PriceData.query.count() == 0:
            print("Initializing default asset data...")
            assets = app.config['ASSETS']
            
            for symbol, data in assets.items():
                price_data = PriceData(
                    symbol=symbol,
                    current_price=data['price'],
                    volatility=data['volatility'],
                    history='[]'
                )
                db.session.add(price_data)
            
            db.session.commit()
            print(f"Initialized {len(assets)} assets")

def migrate_json_data():
    """Migrate existing JSON data to database (one-time operation)."""
    with app.app_context():
        # Migrate users
        if os.path.exists('users.json'):
            with open('users.json', 'r') as f:
                users_data = json.load(f)
            
            for username, user_data in users_data.items():
                if not User.query.filter_by(username=username).first():
                    user = User(username=username)
                    user.password_hash = user_data['password_hash']
                    db.session.add(user)
                    db.session.flush()  # Get user ID
                    
                    # Create portfolio
                    portfolio = Portfolio(user_id=user.id)
                    db.session.add(portfolio)
            
            db.session.commit()
            print(f"Migrated {len(users_data)} users")
        
        # Migrate portfolios
        if os.path.exists('portfolios.json'):
            with open('portfolios.json', 'r') as f:
                portfolios_data = json.load(f)
            
            for username, portfolio_data in portfolios_data.items():
                user = User.query.filter_by(username=username).first()
                if user and user.portfolio:
                    user.portfolio.cash = portfolio_data.get('cash', 100000)
                    user.portfolio.set_holdings(portfolio_data.get('holdings', {}))
                    user.portfolio.set_position_info(portfolio_data.get('position_info', {}))
                    
                    # Migrate transactions
                    for transaction in portfolio_data.get('transactions', []):
                        trans = Transaction(
                            user_id=user.id,
                            timestamp=transaction['timestamp'],
                            symbol=transaction['symbol'],
                            type=transaction['type'],
                            quantity=transaction['quantity'],
                            price=transaction['price'],
                            total_cost=transaction['total_cost']
                        )
                        db.session.add(trans)
            
            db.session.commit()
            print("Migrated portfolio and transaction data")

if __name__ == '__main__':
    print("Initializing database...")
    init_database()
    
    print("Checking for JSON data to migrate...")
    migrate_json_data()
    
    print("Database setup complete!")