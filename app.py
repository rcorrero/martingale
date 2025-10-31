"""
Martingale - A paper trading web application for simulated asset trading.
"""
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
import threading
import time
import json
import os
import logging
from config import config
from price_client import HybridPriceService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('martingale.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_app(config_name='default'):
    """Application factory pattern."""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    return app

# Create Flask app
config_name = os.environ.get('FLASK_ENV', 'development')
app = create_app(config_name)
socketio = SocketIO(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# File paths from configuration
USERS_FILE = app.config['USERS_FILE']
PORTFOLIOS_FILE = app.config['PORTFOLIOS_FILE']
GLOBAL_TRANSACTIONS_FILE = app.config['GLOBAL_TRANSACTIONS_FILE']

class User(UserMixin):
    def __init__(self, username, password_hash):
        self.id = username
        self.username = username
        self.password_hash = password_hash

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

@login_manager.user_loader
def load_user(username):
    users = load_users()
    if username in users:
        return User(username, users[username]['password_hash'])
    return None

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

def load_portfolios():
    if os.path.exists(PORTFOLIOS_FILE):
        with open(PORTFOLIOS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_portfolios(portfolios):
    with open(PORTFOLIOS_FILE, 'w') as f:
        json.dump(portfolios, f)

def load_global_transactions():
    """Load the global transactions list."""
    if os.path.exists(GLOBAL_TRANSACTIONS_FILE):
        with open(GLOBAL_TRANSACTIONS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_global_transactions(transactions):
    """Save the global transactions list."""
    with open(GLOBAL_TRANSACTIONS_FILE, 'w') as f:
        json.dump(transactions, f)

def add_global_transaction(transaction):
    """Add a transaction to the global transactions list."""
    transactions = load_global_transactions()
    transactions.append(transaction)
    
    # Keep only the most recent 1000 transactions to prevent file from growing too large
    if len(transactions) > 1000:
        transactions = transactions[-1000:]
    
    save_global_transactions(transactions)

def get_user_portfolio(username):
    """Get or create user portfolio with default values."""
    portfolios = load_portfolios()
    if username not in portfolios:
        # Initialize portfolio with assets from configuration
        holdings = {symbol: 0 for symbol in app.config['ASSETS'].keys()}
        position_info = {symbol: {'total_cost': 0, 'total_quantity': 0} for symbol in app.config['ASSETS'].keys()}
        
        portfolios[username] = {
            'cash': app.config['INITIAL_CASH'],
            'holdings': holdings,
            'transactions': [],
            'position_info': position_info
        }
        save_portfolios(portfolios)
    return portfolios[username]

def update_user_portfolio(username, portfolio):
    portfolios = load_portfolios()
    portfolios[username] = portfolio
    save_portfolios(portfolios)

# Initialize price service (hybrid mode - uses API if available, fallback otherwise)
price_service = HybridPriceService(
    assets_config=app.config['ASSETS'],
    api_url=os.environ.get('PRICE_SERVICE_URL', 'http://localhost:5001')
)

def update_prices():
    """Get updated prices from price service and emit to clients."""
    while True:
        try:
            # Get current prices from the price service
            current_prices = price_service.get_current_prices()
            
            if current_prices:
                # Emit individual price updates for charts
                for symbol, price_data in current_prices.items():
                    if 'price' in price_data and 'last_update' in price_data:
                        socketio.emit('price_chart_update', {
                            'symbol': symbol,
                            'time': price_data['last_update'],
                            'price': price_data['price']
                        })
                
                # Emit all current prices for the table
                all_current_prices = {s: {'price': d['price']} for s, d in current_prices.items()}
                socketio.emit('price_update', all_current_prices)
                
                # Emit performance update for all users
                socketio.emit('performance_update')
            
        except Exception as e:
            logger.error(f"Error in price update loop: {e}")
        
        time.sleep(app.config['PRICE_UPDATE_INTERVAL'])

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        users = load_users()
        username = form.username.data
        
        if username in users and check_password_hash(users[username]['password_hash'], form.password.data):
            user = User(username, users[username]['password_hash'])
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        users = load_users()
        username = form.username.data
        
        if username in users:
            flash('Username already exists')
        else:
            password_hash = generate_password_hash(form.password.data)
            users[username] = {'password_hash': password_hash}
            save_users(users)
            
            user = User(username, password_hash)
            login_user(user)
            return redirect(url_for('index'))
    
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/api/portfolio', methods=['GET'])
@login_required
def get_portfolio():
    portfolio = get_user_portfolio(current_user.username)
    return jsonify(portfolio)

@app.route('/api/performance', methods=['GET'])
@login_required
def get_performance():
    portfolio = get_user_portfolio(current_user.username)
    
    # Calculate portfolio value and performance
    total_portfolio_value = portfolio['cash']
    total_unrealized_pnl = 0
    
    # Get current prices from price service
    current_prices = price_service.get_current_prices()
    
    # Calculate current market value of holdings and unrealized P&L
    for symbol, quantity in portfolio['holdings'].items():
        if quantity > 0 and symbol in current_prices:
            current_price = current_prices[symbol]['price']
            market_value = quantity * current_price
            total_portfolio_value += market_value
            
            # Calculate unrealized P&L using position_info
            position_info = portfolio.get('position_info', {}).get(symbol, {})
            cost_basis = position_info.get('total_cost', 0)
            if cost_basis > 0:
                unrealized_pnl = market_value - cost_basis
                total_unrealized_pnl += unrealized_pnl
    
    # Calculate realized P&L by analyzing all transactions
    initial_value = app.config['INITIAL_CASH']  # Starting cash from configuration
    total_buys = 0
    total_sells = 0
    
    # Sum all buy and sell transactions
    for transaction in portfolio.get('transactions', []):
        if transaction['type'] == 'buy':
            total_buys += transaction['total_cost']
        else:  # sell
            total_sells += transaction['total_cost']
    
    # Current value of holdings at cost
    current_holdings_cost = 0
    for symbol in portfolio['holdings']:
        if portfolio['holdings'][symbol] > 0:
            position_info = portfolio.get('position_info', {}).get(symbol, {})
            current_holdings_cost += position_info.get('total_cost', 0)
    
    # Realized P&L = sell proceeds - buy costs for completed positions
    # For positions still held, their cost is excluded from realized P&L
    total_realized_pnl = total_sells - (total_buys - current_holdings_cost)
    
    # Calculate total P&L and performance metrics
    total_pnl = total_realized_pnl + total_unrealized_pnl
    total_return_pct = ((total_portfolio_value - initial_value) / initial_value) * 100 if initial_value > 0 else 0
    
    performance = {
        'total_portfolio_value': round(total_portfolio_value, 2),
        'cash': round(portfolio['cash'], 2),
        'total_pnl': round(total_pnl, 2),
        'realized_pnl': round(total_realized_pnl, 2),
        'unrealized_pnl': round(total_unrealized_pnl, 2),
        'total_return_percent': round(total_return_pct, 2),
        'initial_value': initial_value
    }
    
    return jsonify(performance)

@app.route('/api/debug/portfolio', methods=['GET'])
@login_required
def debug_portfolio():
    portfolio = get_user_portfolio(current_user.username)
    return jsonify(portfolio)

@app.route('/api/transactions', methods=['GET'])
@login_required
def get_transactions():
    portfolio = get_user_portfolio(current_user.username)
    return jsonify(portfolio.get('transactions', []))

@app.route('/api/assets', methods=['GET'])
def get_assets():
    """Get current asset prices."""
    current_prices = price_service.get_current_prices()
    return jsonify(current_prices)

@app.route('/api/assets/history', methods=['GET'])
def get_assets_history():
    """Get price history for all assets."""
    history = price_service.get_price_history()
    return jsonify(history)

@app.route('/api/open-interest', methods=['GET'])
def get_open_interest():
    """Calculate total open interest for each asset by summing all users' holdings."""
    portfolios = load_portfolios()
    open_interest = {}
    
    # Initialize open interest for all assets
    for symbol in app.config['ASSETS'].keys():
        open_interest[symbol] = 0
    
    # Sum holdings across all users
    for username, portfolio in portfolios.items():
        holdings = portfolio.get('holdings', {})
        for symbol, quantity in holdings.items():
            if symbol in open_interest:
                open_interest[symbol] += quantity
    
    return jsonify(open_interest)

@app.route('/api/global-transactions', methods=['GET'])
def get_global_transactions():
    """Get the last 50 global transactions for Time & Sales display."""
    transactions = load_global_transactions()
    # Return the last 50 transactions, most recent first
    last_50 = transactions[-50:] if len(transactions) >= 50 else transactions
    return jsonify(last_50[::-1])  # Reverse to show most recent first

@socketio.on('trade')
def handle_trade(data):
    """Handle a trade request from the client."""
    if not current_user.is_authenticated:
        emit('trade_confirmation', {'success': False, 'message': 'Please log in'})
        return
        
    try:
        portfolio = get_user_portfolio(current_user.username)
        symbol = data['symbol'].upper()
        trade_type = data['type']
        quantity = float(data['quantity'])
        
        # Get current price from price service
        current_prices = price_service.get_current_prices()
        if symbol not in current_prices:
            emit('trade_confirmation', {'success': False, 'message': f'Unknown asset: {symbol}', 'symbol': symbol})
            return
            
        price = current_prices[symbol]['price']
        cost = quantity * price
        timestamp = time.time() * 1000  # JavaScript-compatible timestamp

        # Ensure position_info exists for this symbol
        if 'position_info' not in portfolio:
            portfolio['position_info'] = {}
        if symbol not in portfolio['position_info']:
            portfolio['position_info'][symbol] = {'total_cost': 0, 'total_quantity': 0}

        # Ensure holdings exists for this symbol
        if symbol not in portfolio['holdings']:
            portfolio['holdings'][symbol] = 0

        # Ensure transactions list exists
        if 'transactions' not in portfolio:
            portfolio['transactions'] = []

        if trade_type == 'buy':
            if portfolio['cash'] >= cost:
                portfolio['cash'] -= cost
                portfolio['holdings'][symbol] += quantity
                
                # Update position info for VWAP calculation
                portfolio['position_info'][symbol]['total_cost'] += cost
                portfolio['position_info'][symbol]['total_quantity'] += quantity
                
                # Record transaction
                transaction = {
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'type': 'buy',
                    'quantity': quantity,
                    'price': price,
                    'total_cost': cost
                }
                portfolio['transactions'].append(transaction)
                
                # Add transaction to global transactions (anonymous)
                global_transaction = {
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'type': 'buy',
                    'quantity': quantity,
                    'price': price,
                    'total_cost': cost
                }
                add_global_transaction(global_transaction)
                
                update_user_portfolio(current_user.username, portfolio)
                emit('trade_confirmation', {'success': True, 'message': f'Bought {quantity} {symbol}', 'symbol': symbol, 'type': 'buy', 'quantity': quantity})
                emit('transaction_added', transaction)
                
                # Broadcast global transaction update to all clients for Time & Sales
                socketio.emit('global_transaction_update', global_transaction)
            else:
                emit('trade_confirmation', {'success': False, 'message': 'Insufficient funds', 'symbol': symbol, 'type': 'buy', 'quantity': quantity})
                
        elif trade_type == 'sell':
            if portfolio['holdings'][symbol] >= quantity:
                portfolio['cash'] += cost
                portfolio['holdings'][symbol] -= quantity
                
                # Update position info for VWAP calculation
                if portfolio['position_info'][symbol]['total_quantity'] > 0:
                    # Calculate proportion being sold
                    sell_proportion = quantity / portfolio['position_info'][symbol]['total_quantity']
                    cost_to_remove = portfolio['position_info'][symbol]['total_cost'] * sell_proportion
                    portfolio['position_info'][symbol]['total_cost'] -= cost_to_remove
                    portfolio['position_info'][symbol]['total_quantity'] -= quantity
                    
                    # If position is completely closed, reset position info
                    if portfolio['holdings'][symbol] <= 0:
                        portfolio['position_info'][symbol] = {'total_cost': 0, 'total_quantity': 0}
                
                # Record transaction
                transaction = {
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'type': 'sell',
                    'quantity': quantity,
                    'price': price,
                    'total_cost': cost
                }
                portfolio['transactions'].append(transaction)
                
                # Add transaction to global transactions (anonymous)
                global_transaction = {
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'type': 'sell',
                    'quantity': quantity,
                    'price': price,
                    'total_cost': cost
                }
                add_global_transaction(global_transaction)
                
                update_user_portfolio(current_user.username, portfolio)
                emit('trade_confirmation', {'success': True, 'message': f'Sold {quantity} {symbol}', 'symbol': symbol, 'type': 'sell', 'quantity': quantity})
                emit('transaction_added', transaction)
                
                # Broadcast global transaction update to all clients for Time & Sales
                socketio.emit('global_transaction_update', global_transaction)
            else:
                emit('trade_confirmation', {'success': False, 'message': 'Insufficient holdings', 'symbol': symbol, 'type': 'sell', 'quantity': quantity})
        
        emit('portfolio_update', portfolio)
        
    except (ValueError, KeyError) as e:
        symbol = data.get('symbol', 'unknown') if isinstance(data, dict) else 'unknown'
        emit('trade_confirmation', {'success': False, 'message': f'Invalid trade data: {str(e)}', 'symbol': symbol})


if __name__ == '__main__':
    # Start price update thread
    price_thread = threading.Thread(target=update_prices)
    price_thread.daemon = True
    price_thread.start()
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT') or os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Run with appropriate settings for production vs development
    socketio.run(app, debug=debug, port=port, host='0.0.0.0')
