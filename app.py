"""
Martingale - A paper trading web application for simulated asset trading.
"""
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, Regexp
from werkzeug.security import generate_password_hash, check_password_hash
import threading
import time
import json
import os
import logging
import re
from datetime import datetime, timedelta
from config import config
from price_client import HybridPriceService
from models import db, User, Portfolio, Transaction, PriceData

# Configure logging
if os.environ.get('FLASK_ENV') == 'production':
    # Production logging - only to stdout for Heroku
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
else:
    # Development logging - to file and stdout
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
    
    # Initialize database
    db.init_app(app)
    
    return app

# Create Flask app
config_name = os.environ.get('FLASK_ENV', 'development')
app = create_app(config_name)
socketio = SocketIO(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Security: Rate limiting for login attempts
login_attempts = {}
RATE_LIMIT_ATTEMPTS = 5
RATE_LIMIT_WINDOW = 300  # 5 minutes in seconds

def validate_password_strength(form, field):
    """Custom validator for password strength."""
    password = field.data
    
    # Check minimum length
    if len(password) < 8:
        raise ValidationError('Password must be at least 8 characters long.')
    
    # Check for uppercase
    if not re.search(r'[A-Z]', password):
        raise ValidationError('Password must contain at least one uppercase letter.')
    
    # Check for lowercase
    if not re.search(r'[a-z]', password):
        raise ValidationError('Password must contain at least one lowercase letter.')
    
    # Check for digit
    if not re.search(r'\d', password):
        raise ValidationError('Password must contain at least one number.')
    
    # Check for special character
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValidationError('Password must contain at least one special character (!@#$%^&*(),.?":{}|<>).')

def validate_username(form, field):
    """Custom validator for username."""
    username = field.data
    
    # Check for valid characters (alphanumeric and underscore only)
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        raise ValidationError('Username can only contain letters, numbers, and underscores.')
    
    # Check if username is reserved
    reserved_usernames = ['admin', 'root', 'system', 'test', 'api', 'public', 'private']
    if username.lower() in reserved_usernames:
        raise ValidationError('This username is reserved and cannot be used.')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(), 
        Length(min=3, max=20, message='Username must be between 3 and 20 characters.'),
        validate_username
    ])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=8, message='Password must be at least 8 characters long.'),
        validate_password_strength
    ])
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match.')
    ])
    submit = SubmitField('Register')

@login_manager.user_loader
def load_user(user_id):
    try:
        # Try to convert to int first (normal case)
        return User.query.get(int(user_id))
    except ValueError:
        # If it's not a number, try to find by username
        return User.query.filter_by(username=user_id).first()

@login_manager.unauthorized_handler
def unauthorized():
    """Handle unauthorized access - return JSON for AJAX requests, redirect for browser requests."""
    # Check if this is an AJAX/API request
    if request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'Authentication required', 'authenticated': False}), 401
    # For regular browser requests, redirect to login
    return redirect(url_for('login'))

def get_user_portfolio(user):
    """Get or create user portfolio with default values."""
    if not user.portfolio:
        # Create new portfolio with assets from configuration
        portfolio = Portfolio(user_id=user.id, cash=app.config['INITIAL_CASH'])
        holdings = {symbol: 0 for symbol in app.config['ASSETS'].keys()}
        position_info = {symbol: {'total_cost': 0, 'total_quantity': 0} for symbol in app.config['ASSETS'].keys()}
        
        portfolio.set_holdings(holdings)
        portfolio.set_position_info(position_info)
        
        db.session.add(portfolio)
        db.session.commit()
    
    return user.portfolio

def update_user_portfolio(user, portfolio_data):
    """Update user portfolio in database."""
    portfolio = user.portfolio
    if portfolio:
        portfolio.cash = portfolio_data.get('cash', portfolio.cash)
        if 'holdings' in portfolio_data:
            portfolio.set_holdings(portfolio_data['holdings'])
        if 'position_info' in portfolio_data:
            portfolio.set_position_info(portfolio_data['position_info'])
        db.session.commit()

def add_global_transaction(transaction_data):
    """Add a transaction to the database."""
    user = User.query.filter_by(username=transaction_data['username']).first()
    if user:
        transaction = Transaction(
            user_id=user.id,
            symbol=transaction_data['symbol'],
            transaction_type=transaction_data['type'],
            quantity=transaction_data['quantity'],
            price=transaction_data['price'],
            total_cost=transaction_data['total_cost']
        )
        db.session.add(transaction)
        db.session.commit()

def get_global_transactions(limit=50):
    """Get recent global transactions from database."""
    transactions = Transaction.query.order_by(Transaction.timestamp.desc()).limit(limit).all()
    return [{
        'timestamp': int(t.timestamp),  # t.timestamp is already a float in milliseconds
        'username': t.user.username,
        'symbol': t.symbol,
        'type': t.type,  # Use 'type' not 'transaction_type'
        'quantity': t.quantity,
        'price': t.price,
        'total_cost': t.total_cost
    } for t in transactions]

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

def check_rate_limit(username):
    """Check if user has exceeded login rate limit."""
    current_time = datetime.now()
    
    if username in login_attempts:
        attempts, first_attempt_time = login_attempts[username]
        
        # Check if we're still within the rate limit window
        if (current_time - first_attempt_time).total_seconds() < RATE_LIMIT_WINDOW:
            if attempts >= RATE_LIMIT_ATTEMPTS:
                remaining_time = int(RATE_LIMIT_WINDOW - (current_time - first_attempt_time).total_seconds())
                return False, remaining_time
            else:
                # Increment attempts
                login_attempts[username] = (attempts + 1, first_attempt_time)
        else:
            # Reset the counter if window has passed
            login_attempts[username] = (1, current_time)
    else:
        # First attempt
        login_attempts[username] = (1, current_time)
    
    return True, 0

def reset_rate_limit(username):
    """Reset rate limit for a user after successful login."""
    if username in login_attempts:
        del login_attempts[username]

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        
        # Check rate limiting
        allowed, remaining_time = check_rate_limit(username)
        if not allowed:
            flash(f'Too many login attempts. Please try again in {remaining_time} seconds.')
            logger.warning(f"Rate limit exceeded for user: {username}")
            return render_template('login.html', form=form)
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(form.password.data):
            # Successful login
            reset_rate_limit(username)
            login_user(user)
            logger.info(f"Successful login: {username}")
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
            logger.warning(f"Failed login attempt for user: {username}")
    
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return render_template('register.html', form=form)
        
        try:
            # Create new user
            user = User(username=username)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            
            # Create portfolio for the new user
            get_user_portfolio(user)
            
            login_user(user)
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Registration error: {e}")
            flash('Registration failed. Please try again.')
            return render_template('register.html', form=form)
    
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
    portfolio = get_user_portfolio(current_user)
    
    return jsonify({
        'cash': portfolio.cash,
        'holdings': portfolio.get_holdings(),
        'position_info': portfolio.get_position_info(),
        'transactions': [{
            'timestamp': int(t.timestamp),  # t.timestamp is already a float in milliseconds
            'symbol': t.symbol,
            'type': t.type,  # Use 'type' not 'transaction_type'
            'quantity': t.quantity,
            'price': t.price,
            'total_cost': t.total_cost
        } for t in portfolio.user.transactions]
    })

@app.route('/api/performance', methods=['GET'])
@login_required
def get_performance():
    portfolio = get_user_portfolio(current_user)
    
    # Calculate portfolio value and performance
    # Ensure cash is a valid number
    portfolio_cash = portfolio.cash if portfolio.cash is not None else 0.0
    total_portfolio_value = float(portfolio_cash)
    total_unrealized_pnl = 0.0
    
    logger.info(f"Starting portfolio calculation - cash: {portfolio_cash}")
    
    # Get current prices from price service
    try:
        current_prices = price_service.get_current_prices()
        logger.info(f"Current prices for performance calculation: {current_prices}")
    except Exception as e:
        logger.error(f"Error getting current prices: {e}")
        current_prices = {}
    
    holdings = portfolio.get_holdings()
    position_info = portfolio.get_position_info()
    logger.info(f"Holdings: {holdings}, Position info: {position_info}")
    
    # Validate that total_portfolio_value is not NaN before proceeding
    if total_portfolio_value != total_portfolio_value:  # Check for NaN
        logger.error(f"Portfolio cash is NaN: {portfolio_cash}")
        total_portfolio_value = 100000.0  # Default to initial cash
    
    # Calculate current market value of holdings and unrealized P&L
    for symbol, quantity in holdings.items():
        try:
            if quantity > 0 and symbol in current_prices:
                current_price = float(current_prices[symbol]['price']) if current_prices[symbol]['price'] is not None else 0.0
                quantity = float(quantity) if quantity is not None else 0.0
                market_value = quantity * current_price
                
                if not (market_value != market_value):  # Check for NaN
                    total_portfolio_value += market_value
                
                # Calculate unrealized P&L using position_info
                symbol_position = position_info.get(symbol, {})
                total_cost = float(symbol_position.get('total_cost', 0)) if symbol_position.get('total_cost') is not None else 0.0
                total_quantity = float(symbol_position.get('total_quantity', 0)) if symbol_position.get('total_quantity') is not None else 0.0
                
                # Calculate cost basis for current holdings only
                # Average cost per share = total_cost / total_quantity
                # Cost basis for current position = quantity × average_cost_per_share
                if total_quantity > 0 and quantity > 0:
                    average_cost_per_share = total_cost / total_quantity
                    cost_basis_current = quantity * average_cost_per_share
                    unrealized_pnl = market_value - cost_basis_current
                    if not (unrealized_pnl != unrealized_pnl):  # Check for NaN
                        total_unrealized_pnl += unrealized_pnl
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Error calculating market value for {symbol}: {e}")
            continue
    
    # Calculate total P&L
    # Total P&L = (current portfolio value) - initial value
    # This includes both realized (from closed positions) and unrealized (from open positions)
    initial_value = float(app.config.get('INITIAL_CASH', 100000.0))
    total_pnl = total_portfolio_value - initial_value
    
    # Realized P&L = Total P&L - Unrealized P&L
    # This represents gains/losses from positions that have been closed
    realized_pnl = total_pnl - total_unrealized_pnl
    
    # Calculate total return percentage
    if initial_value > 0:
        total_return_percent = ((total_portfolio_value - initial_value) / initial_value) * 100
    else:
        total_return_percent = 0.0
    # Final validation - ensure no NaN values are returned
    if total_portfolio_value != total_portfolio_value:
        total_portfolio_value = float(app.config.get('INITIAL_CASH', 100000.0))
    if total_pnl != total_pnl:
        total_pnl = 0.0
    if total_return_percent != total_return_percent:
        total_return_percent = 0.0
    if realized_pnl != realized_pnl:
        realized_pnl = 0.0
    if total_unrealized_pnl != total_unrealized_pnl:
        total_unrealized_pnl = 0.0
    
    logger.info(f"Final portfolio values - Value: {total_portfolio_value}, P&L: {total_pnl}, Return: {total_return_percent}%")
    
    return jsonify({
        'portfolio_value': round(total_portfolio_value, 2),
        'realized_pnl': round(realized_pnl, 2),
        'unrealized_pnl': round(total_unrealized_pnl, 2),
        'total_pnl': round(total_pnl, 2),
        'total_return': round(total_return_percent, 2)
    })

@app.route('/api/debug/portfolio', methods=['GET'])
@login_required
def debug_portfolio():
    portfolio = get_user_portfolio(current_user)
    return jsonify({
        'cash': portfolio.cash,
        'holdings': portfolio.get_holdings(),
        'position_info': portfolio.get_position_info()
    })

@app.route('/api/transactions', methods=['GET'])
@login_required
def get_transactions():
    transactions = [{
        'timestamp': int(t.timestamp),  # t.timestamp is already a float in milliseconds
        'symbol': t.symbol,
        'type': t.type,  # Use 'type' not 'transaction_type'
        'quantity': t.quantity,
        'price': t.price,
        'total_cost': t.total_cost
    } for t in current_user.transactions]
    return jsonify(transactions)

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
    open_interest = {}
    
    # Initialize open interest for all assets
    for symbol in app.config['ASSETS'].keys():
        open_interest[symbol] = 0
    
    # Sum holdings across all users
    portfolios = Portfolio.query.all()
    for portfolio in portfolios:
        holdings = portfolio.get_holdings()
        for symbol, quantity in holdings.items():
            if symbol in open_interest:
                open_interest[symbol] += quantity
    
    return jsonify(open_interest)

@app.route('/api/global-transactions', methods=['GET'])
def get_global_transactions_api():
    """Get the last 50 global transactions for Time & Sales display."""
    transactions = get_global_transactions(50)
    return jsonify(transactions[::-1])  # Most recent first

@socketio.on('trade')
def handle_trade(data):
    """Handle a trade request from the client."""
    if not current_user.is_authenticated:
        emit('trade_confirmation', {'success': False, 'message': 'Please log in'})
        return
        
    try:
        portfolio = get_user_portfolio(current_user)
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

        # Get current holdings and position info
        holdings = portfolio.get_holdings()
        position_info = portfolio.get_position_info()
        
        # Ensure data exists for this symbol
        if symbol not in holdings:
            holdings[symbol] = 0
        if symbol not in position_info:
            position_info[symbol] = {'total_cost': 0, 'total_quantity': 0}

        if trade_type == 'buy':
            if portfolio.cash >= cost:
                portfolio.cash -= cost
                holdings[symbol] += quantity
                
                # Update position info for VWAP calculation
                position_info[symbol]['total_cost'] += cost
                position_info[symbol]['total_quantity'] += quantity
                
                # Update portfolio in database
                portfolio.set_holdings(holdings)
                portfolio.set_position_info(position_info)
                
                # Record transaction in database
                transaction = Transaction(
                    user_id=current_user.id,
                    timestamp=timestamp,
                    symbol=symbol,
                    type='buy',
                    quantity=quantity,
                    price=price,
                    total_cost=cost
                )
                db.session.add(transaction)
                db.session.commit()
                
                # Create transaction data for global feed
                transaction_data = {
                    'timestamp': timestamp,
                    'username': current_user.username,
                    'symbol': symbol,
                    'type': 'buy',
                    'quantity': quantity,
                    'price': price,
                    'total_cost': cost
                }
                
                emit('trade_confirmation', {'success': True, 'message': f'Bought {quantity} {symbol}', 'symbol': symbol, 'type': 'buy', 'quantity': quantity})
                emit('transaction_added', {
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'type': 'buy',
                    'quantity': quantity,
                    'price': price,
                    'total_cost': cost
                })
                
                # Broadcast global transaction update to all clients for Time & Sales
                socketio.emit('global_transaction_update', transaction_data)
            else:
                emit('trade_confirmation', {'success': False, 'message': 'Insufficient funds', 'symbol': symbol, 'type': 'buy', 'quantity': quantity})
                
        elif trade_type == 'sell':
            if holdings[symbol] >= quantity:
                portfolio.cash += cost
                holdings[symbol] -= quantity
                
                # Update position info for VWAP calculation
                if position_info[symbol]['total_quantity'] > 0:
                    # Calculate proportion of position being sold
                    proportion_sold = quantity / position_info[symbol]['total_quantity']
                    cost_basis_sold = position_info[symbol]['total_cost'] * proportion_sold
                    
                    position_info[symbol]['total_cost'] -= cost_basis_sold
                    position_info[symbol]['total_quantity'] -= quantity
                
                # Update portfolio in database
                portfolio.set_holdings(holdings)
                portfolio.set_position_info(position_info)
                
                # Record transaction in database
                transaction = Transaction(
                    user_id=current_user.id,
                    timestamp=timestamp,
                    symbol=symbol,
                    type='sell',
                    quantity=quantity,
                    price=price,
                    total_cost=cost
                )
                db.session.add(transaction)
                db.session.commit()
                
                # Create transaction data for global feed
                transaction_data = {
                    'timestamp': timestamp,
                    'username': current_user.username,
                    'symbol': symbol,
                    'type': 'sell',
                    'quantity': quantity,
                    'price': price,
                    'total_cost': cost
                }
                
                emit('trade_confirmation', {'success': True, 'message': f'Sold {quantity} {symbol}', 'symbol': symbol, 'type': 'sell', 'quantity': quantity})
                emit('transaction_added', {
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'type': 'sell',
                    'quantity': quantity,
                    'price': price,
                    'total_cost': cost
                })
                
                # Broadcast global transaction update to all clients for Time & Sales
                socketio.emit('global_transaction_update', transaction_data)
            else:
                emit('trade_confirmation', {'success': False, 'message': 'Insufficient holdings', 'symbol': symbol, 'type': 'sell', 'quantity': quantity})
        
        # Emit portfolio update to the user
        socketio.emit('portfolio_update', {
            'cash': portfolio.cash,
            'holdings': portfolio.get_holdings(),
            'position_info': portfolio.get_position_info()
        }, room=request.sid)
        
    except Exception as e:
        import traceback
        logger.error(f"Trade error: {e}")
        logger.error(f"Trade error traceback: {traceback.format_exc()}")
        emit('trade_confirmation', {'success': False, 'message': f'Trade processing error: {str(e)}'})

def update_prices():
    """Get updated prices from price service and emit to clients."""
    try:
        current_prices = price_service.get_current_prices()
        socketio.emit('price_update', current_prices)
        
        # Emit individual price updates for charts
        for symbol, data in current_prices.items():
            socketio.emit('price_chart_update', {
                'symbol': symbol,
                'time': data.get('last_update', time.time() * 1000),
                'price': data['price']
            })
    except Exception as e:
        logger.error(f"Price update error: {e}")

# Background thread for price updates
def price_update_thread():
    """Background thread to update prices periodically."""
    while True:
        time.sleep(app.config.get('PRICE_UPDATE_INTERVAL', 1))  # Update every second
        update_prices()

# Start the price update thread
price_thread = threading.Thread(target=price_update_thread, daemon=True)
price_thread.start()

if __name__ == '__main__':
    # Initialize database tables
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT') or os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    logger.info(f"Starting application on port {port}, debug={debug}")
    
    # Run with appropriate settings for production vs development
    socketio.run(app, debug=debug, port=port, host='0.0.0.0')
