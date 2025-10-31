"""
Local debugging script for Martingale trading platform.
Use this for local development with enhanced debugging features.
"""
import os
import sys
import logging
from dotenv import load_dotenv

# Load local environment variables FIRST
load_dotenv('.env')

# Ensure we're in development mode
os.environ['FLASK_ENV'] = 'development'
os.environ['FLASK_DEBUG'] = 'True'

# Ensure DATABASE_URL is set for local development  
os.environ['DATABASE_URL'] = 'sqlite:///martingale.db'

# Ensure SECRET_KEY is set
if 'SECRET_KEY' not in os.environ:
    os.environ['SECRET_KEY'] = 'dev-secret-key-for-local-development'

# Set up enhanced logging for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

print("🔧 Environment setup:")
print(f"   FLASK_ENV: {os.environ.get('FLASK_ENV')}")
print(f"   DATABASE_URL: {os.environ.get('DATABASE_URL')}")
print(f"   SECRET_KEY: {'SET' if os.environ.get('SECRET_KEY') else 'NOT SET'}")

# Import your main app AFTER environment setup
try:
    from app import app, socketio
    print("✅ App imported successfully")
except Exception as e:
    print(f"❌ Error importing app: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

def run_debug_server():
    """Run the application in debug mode with enhanced error handling."""
    
    print("🚀 Starting Martingale in DEBUG mode...")
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"🐍 Python executable: {sys.executable}")
    print(f"📊 Flask environment: {os.environ.get('FLASK_ENV', 'development')}")
    print(f"🔧 Debug mode: {os.environ.get('FLASK_DEBUG', 'True')}")
    print(f"🌐 Port: {os.environ.get('FLASK_PORT', 5000)}")
    
    # Check for required files
    required_files = ['templates/index.html', 'static/css/style.css', 'static/js/main.js']
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ Found: {file_path}")
        else:
            print(f"❌ Missing: {file_path}")
    
    # Initialize the database
    print("\n🔧 Setting up database...")
    with app.app_context():
        from models import db, PriceData
        db.create_all()
        print("✅ Database tables created successfully")
        
        # Initialize default price data in database if needed
        if PriceData.query.count() == 0:
            print("� Initializing price data in database...")
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
    
    # Run the app
    try:
        port = int(os.environ.get('FLASK_PORT', 5000))
        debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
        
        print(f"\n🌐 Starting server on http://localhost:{port}")
        print("👤 Create an account or login to start trading!")
        print("🛑 Press Ctrl+C to stop the server\n")
        
        socketio.run(
            app, 
            debug=debug, 
            port=port, 
            host='0.0.0.0',
            use_reloader=True,  # Auto-restart on code changes
            log_output=True     # Show all logs
        )
        
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        logging.exception("Server startup error")

if __name__ == '__main__':
    run_debug_server()