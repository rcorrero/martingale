"""
DEPRECATED: This file was used for the old JSON file storage system.
The application now uses PostgreSQL database for data storage.

For database initialization, use:
- debug_server.py (automatically initializes database)
- init_db.py (manual database setup)

This file is kept for reference but should not be used in production.
"""
import json
import os
from config import config

def create_default_data_files():
    """
    DEPRECATED: Creates JSON files for the old storage system.
    Do not use this in production - use database initialization instead.
    """
    print("⚠️ WARNING: This is the legacy JSON file initialization system.")
    print("The application now uses PostgreSQL database storage.")
    print("Use debug_server.py or init_db.py instead.")
    return
    
    # Legacy code kept for reference (not executed)
    
    # 1. Create users.json if missing
    if not os.path.exists('users.json'):
        print("Creating default users.json...")
        with open('users.json', 'w') as f:
            json.dump({}, f, indent=2)
        print("✅ Created users.json")
    
    # 2. Create portfolios.json if missing
    if not os.path.exists('portfolios.json'):
        print("Creating default portfolios.json...")
        with open('portfolios.json', 'w') as f:
            json.dump({}, f, indent=2)
        print("✅ Created portfolios.json")
    
    # 3. Create price_data.json with initial data
    print("Creating default price_data.json with asset data...")
    
    # Get assets from config
    dev_config = config['development']()
    assets = dev_config.ASSETS
    
    price_data = {}
    current_time = int(time.time() * 1000)  # Current timestamp in milliseconds
    
    for symbol, asset_info in assets.items():
        price = asset_info['price']
        volatility = asset_info['volatility']
            
            # Create some initial price history (last 50 points)
            history = []
            base_time = current_time - (50 * 1000)  # 50 seconds ago
            
            for i in range(50):
                timestamp = base_time + (i * 1000)
                # Add some realistic price variation
                price_variation = price * (0.95 + (i / 50) * 0.1)  # Slight upward trend
                history.append({
                    'time': timestamp,
                    'price': round(price_variation, 2)
                })
            
            price_data[symbol] = {
                'price': price,
                'volatility': volatility,
                'history': history
            }
        
        with open('price_data.json', 'w') as f:
            json.dump(price_data, f, indent=2)
        
        print(f"✅ Created price_data.json with {len(assets)} assets")
        print(f"   Assets: {', '.join(assets.keys())}")
    
    # 4. Create global_transactions.json if missing
    if not os.path.exists('global_transactions.json'):
        print("Creating default global_transactions.json...")
        with open('global_transactions.json', 'w') as f:
            json.dump([], f, indent=2)
        print("✅ Created global_transactions.json")
    
    print("\n🎉 All data files initialized successfully!")
    print("You can now run the application with: python app.py")

if __name__ == '__main__':
    import time
    create_default_data_files()