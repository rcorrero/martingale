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
from sqlalchemy import inspect, text, or_
from sqlalchemy.exc import SQLAlchemyError
from config import config
from price_client import HybridPriceService
from models import db, User, Portfolio, Transaction, PriceData, Asset, Settlement, current_utc
from asset_manager import AssetManager

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


def ensure_transaction_asset_schema():
    """Ensure transactions table has asset_id column and backfill values."""
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            if 'transactions' not in inspector.get_table_names():
                return

            column_names = {col['name'] for col in inspector.get_columns('transactions')}
            if 'asset_id' not in column_names:
                logger.info("Adding asset_id column to transactions table")
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE transactions ADD COLUMN asset_id INTEGER'))

            # Ensure supporting index exists (no-op if already present)
            with db.engine.begin() as conn:
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_transactions_asset_id ON transactions(asset_id)'))

            # Backfill asset_id for historical transactions
            missing_transactions = Transaction.query.filter(Transaction.asset_id.is_(None)).all()
            if missing_transactions:
                logger.info("Backfilling asset_id for %d transactions", len(missing_transactions))
                for transaction in missing_transactions:
                    asset = Asset.query.filter_by(symbol=transaction.symbol).order_by(Asset.created_at.desc()).first()
                    if asset:
                        transaction.asset_id = asset.id
                db.session.commit()

            missing_symbols = Transaction.query.filter(or_(Transaction.legacy_symbol.is_(None), Transaction.legacy_symbol == '')).all()
            if missing_symbols:
                logger.info("Backfilling legacy symbols for %d transactions", len(missing_symbols))
                for transaction in missing_symbols:
                    if transaction.asset:
                        transaction.legacy_symbol = transaction.asset.symbol
                    elif transaction.asset_id:
                        asset = Asset.query.get(transaction.asset_id)
                        if asset:
                            transaction.legacy_symbol = asset.symbol
                db.session.commit()

        except SQLAlchemyError as exc:
            logger.error("Schema synchronization failed: %s", exc)
            db.session.rollback()


ensure_transaction_asset_schema()


def ensure_settlement_asset_schema():
    """Ensure settlements table uses asset_id while preserving legacy symbol column."""
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            if 'settlements' not in inspector.get_table_names():
                return

            column_names = {col['name'] for col in inspector.get_columns('settlements')}
            if 'asset_id' not in column_names:
                logger.info("Adding asset_id column to settlements table")
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE settlements ADD COLUMN asset_id INTEGER'))

            if 'symbol' not in column_names:
                logger.info("Adding legacy symbol column to settlements table")
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE settlements ADD COLUMN symbol VARCHAR(10)'))

            missing_asset_ids = Settlement.query.filter(Settlement.asset_id.is_(None)).all()
            if missing_asset_ids:
                logger.info("Backfilling asset_id for %d settlement records", len(missing_asset_ids))
                for settlement in missing_asset_ids:
                    legacy_symbol = settlement.legacy_symbol
                    if legacy_symbol:
                        asset = Asset.query.filter_by(symbol=legacy_symbol).order_by(Asset.created_at.desc()).first()
                        if asset:
                            settlement.asset_id = asset.id

            missing_symbols = Settlement.query.filter(or_(Settlement.legacy_symbol.is_(None), Settlement.legacy_symbol == '')).all()
            if missing_symbols:
                logger.info("Backfilling legacy symbol for %d settlement records", len(missing_symbols))
                for settlement in missing_symbols:
                    if settlement.asset:
                        settlement.legacy_symbol = settlement.asset.symbol

            if missing_asset_ids or missing_symbols:
                db.session.commit()

        except SQLAlchemyError as exc:
            logger.error("Settlement schema synchronization failed: %s", exc)
            db.session.rollback()


ensure_settlement_asset_schema()

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
    password = field.data or ''

    if len(password) < 8:
        raise ValidationError('Password must be at least 8 characters long.')

    if not password.strip():
        raise ValidationError('Password cannot be only whitespace characters.')

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
        # Create new portfolio - holdings start empty
        # Assets are added dynamically as user trades
        portfolio = Portfolio(user_id=user.id, cash=app.config['INITIAL_CASH'])
        portfolio.set_holdings({})
        portfolio.set_position_info({})
        
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
        asset = None
        asset_id = transaction_data.get('asset_id')
        if asset_id is not None:
            asset = Asset.query.get(asset_id)
        if not asset:
            symbol = transaction_data.get('symbol')
            if symbol:
                asset = Asset.query.filter_by(symbol=symbol).order_by(Asset.created_at.desc()).first()
        if not asset:
            logger.error("Unable to record transaction; asset reference missing or not found")
            return

        transaction = Transaction(
            user_id=user.id,
            asset_id=asset.id,
            legacy_symbol=asset.symbol,
            timestamp=transaction_data.get('timestamp', time.time() * 1000),
            type=transaction_data['type'],
            quantity=transaction_data['quantity'],
            price=transaction_data['price'],
            total_cost=transaction_data['total_cost']
        )
        db.session.add(transaction)
        db.session.commit()

# Initialize price service (hybrid mode - uses API if available, fallback otherwise)
price_service = HybridPriceService(
    assets_config=app.config['ASSETS'],
    api_url=app.config.get('PRICE_SERVICE_URL')
)

# Initialize asset manager
asset_manager = AssetManager(app.config, price_service, socketio)

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
    holdings_by_symbol = portfolio.get_holdings_by_symbol()
    position_info_by_symbol = portfolio.get_position_info_by_symbol()
    
    return jsonify({
        'user_id': current_user.id,
        'cash': portfolio.cash,
        'holdings': holdings_by_symbol,
        'position_info': position_info_by_symbol,
        'transactions': [{
            'timestamp': int(t.timestamp),  # t.timestamp is already a float in milliseconds
            'symbol': t.symbol,
            'type': t.type,  # Use 'type' not 'transaction_type'
            'asset_id': t.asset_id,
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
    
    # Get current prices from price service (only active assets)
    try:
        current_prices = price_service.get_current_prices()
        # Filter to only active assets
        active_assets = Asset.query.filter_by(is_active=True).all()
        active_symbols = {a.symbol for a in active_assets}
        current_prices = {s: p for s, p in current_prices.items() if s in active_symbols}
        logger.info(f"Current prices for performance calculation: {current_prices}")
    except Exception as e:
        logger.error(f"Error getting current prices: {e}")
        current_prices = {}
    
    holdings = portfolio.get_holdings()
    position_info = portfolio.get_position_info()
    logger.info(f"Holdings: {holdings}, Position info: {position_info}")

    asset_lookup = {}
    if holdings:
        assets = Asset.query.filter(Asset.id.in_(holdings.keys())).all()
        asset_lookup = {asset.id: asset for asset in assets}
    
    # Validate that total_portfolio_value is not NaN before proceeding
    if total_portfolio_value != total_portfolio_value:  # Check for NaN
        logger.error(f"Portfolio cash is NaN: {portfolio_cash}")
        total_portfolio_value = 100000.0  # Default to initial cash
    
    # Calculate current market value of holdings and unrealized P&L (only for active assets)
    for asset_id, quantity in holdings.items():
        try:
            asset = asset_lookup.get(asset_id)
            if not asset:
                continue
            symbol = asset.symbol
            if quantity > 0:
                price_record = current_prices.get(symbol)
                raw_price = price_record.get('price') if price_record else None
                if raw_price is not None:
                    current_price = float(raw_price)
                else:
                    current_price = float(asset.current_price or 0.0)
                quantity = float(quantity) if quantity is not None else 0.0
                market_value = quantity * current_price
                
                if not (market_value != market_value):  # Check for NaN
                    total_portfolio_value += market_value
                
                # Calculate unrealized P&L using position_info
                symbol_position = position_info.get(asset_id, {})
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
            logger.warning(f"Error calculating market value for asset_id={asset_id}: {e}")
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
        'holdings': portfolio.get_holdings_by_symbol(),
        'holdings_by_asset_id': portfolio.get_holdings(),
        'position_info': portfolio.get_position_info_by_symbol(),
        'position_info_by_asset_id': portfolio.get_position_info()
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
    """Get current asset prices and expiration info for active assets."""
    # Get active assets from database (only those not yet expired)
    now = current_utc()
    active_assets = Asset.query.filter_by(is_active=True).filter(Asset.expires_at > now).all()
    
    # Get current prices from price service
    current_prices = price_service.get_current_prices()
    
    # Combine asset info with current prices
    assets_data = {}
    for asset in active_assets:
        price = current_prices.get(asset.symbol, {}).get('price', asset.current_price)
        assets_data[asset.symbol] = {
            'price': price,
            'expires_at': asset.expires_at.isoformat(),
            'time_to_expiry_seconds': asset.time_to_expiry().total_seconds() if asset.time_to_expiry() else 0,
            'initial_price': asset.initial_price,
            'volatility': asset.volatility,
            'color': asset.color,
            'created_at': asset.created_at.isoformat()
        }
    
    return jsonify(assets_data)

@app.route('/api/assets/history', methods=['GET'])
def get_assets_history():
    """Get price history for active assets."""
    # Get active assets from database
    active_assets = Asset.query.filter_by(is_active=True).all()
    active_symbols = [a.symbol for a in active_assets]
    
    # Get full history from price service
    all_history = price_service.get_price_history()
    
    # Filter to only active assets
    active_history = {
        symbol: history 
        for symbol, history in all_history.items() 
        if symbol in active_symbols
    }
    
    return jsonify(active_history)

@app.route('/api/assets/summary', methods=['GET'])
def get_assets_summary():
    """Get summary of asset lifecycle status."""
    summary = asset_manager.get_asset_summary()
    return jsonify(summary)

@app.route('/api/settlements', methods=['GET'])
@login_required
def get_settlements():
    """Get settlement history for current user."""
    settlements = Settlement.query.filter_by(user_id=current_user.id).order_by(Settlement.settled_at.desc()).limit(50).all()
    
    return jsonify([{
        'symbol': s.symbol,
        'quantity': s.quantity,
        'settlement_price': s.settlement_price,
        'settlement_value': s.settlement_value,
        'settled_at': s.settled_at.isoformat()
    } for s in settlements])

@app.route('/api/open-interest', methods=['GET'])
def get_open_interest():
    """Calculate total open interest for each asset by summing all users' holdings."""
    # Get active assets
    active_assets = Asset.query.filter_by(is_active=True).all()
    id_to_symbol = {asset.id: asset.symbol for asset in active_assets}
    open_interest = {asset_id: 0 for asset_id in id_to_symbol.keys()}
    
    # Sum holdings across all users
    portfolios = Portfolio.query.all()
    for portfolio in portfolios:
        holdings = portfolio.get_holdings()
        for asset_id, quantity in holdings.items():
            if asset_id in open_interest:
                open_interest[asset_id] += quantity

    open_interest_by_symbol = {id_to_symbol[asset_id]: quantity for asset_id, quantity in open_interest.items() if id_to_symbol.get(asset_id)}
    return jsonify(open_interest_by_symbol)

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
        
        # Validate asset is active
        asset = Asset.query.filter_by(symbol=symbol, is_active=True).first()
        if not asset:
            emit('trade_confirmation', {
                'success': False, 
                'message': f'Asset {symbol} is not available for trading (may have expired)', 
                'symbol': symbol
            })
            return
        
        # Get current price from price service
        current_prices = price_service.get_current_prices()
        if symbol not in current_prices:
            emit('trade_confirmation', {'success': False, 'message': f'Price not available for {symbol}', 'symbol': symbol})
            return
            
        price = current_prices[symbol]['price']
        cost = quantity * price
        timestamp = time.time() * 1000  # JavaScript-compatible timestamp

        # Get current holdings and position info
        holdings = portfolio.get_holdings()
        position_info = portfolio.get_position_info()
        asset_id = asset.id
        
        # Ensure data exists for this asset
        if asset_id not in holdings:
            holdings[asset_id] = 0.0
        if asset_id not in position_info:
            position_info[asset_id] = {'total_cost': 0.0, 'total_quantity': 0.0}

        if trade_type == 'buy':
            if portfolio.cash >= cost:
                portfolio.cash -= cost
                holdings[asset_id] += quantity
                
                # Update position info for VWAP calculation
                position_info[asset_id]['total_cost'] += cost
                position_info[asset_id]['total_quantity'] += quantity
                
                # Update portfolio in database
                portfolio.set_holdings(holdings)
                portfolio.set_position_info(position_info)
                
                # Record transaction in database
                transaction = Transaction(
                    user_id=current_user.id,
                    asset_id=asset.id,
                    legacy_symbol=asset.symbol,
                    timestamp=timestamp,
                    type='buy',
                    quantity=quantity,
                    price=price,
                    total_cost=cost
                )
                db.session.add(transaction)
                db.session.commit()
                
                emit('trade_confirmation', {'success': True, 'message': f'Bought {quantity} {symbol}', 'symbol': symbol, 'type': 'buy', 'quantity': quantity})
                emit('transaction_added', {
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'type': 'buy',
                    'asset_id': asset.id,
                    'quantity': quantity,
                    'price': price,
                    'total_cost': cost,
                    'user_id': current_user.id
                })
            else:
                emit('trade_confirmation', {'success': False, 'message': 'Insufficient funds', 'symbol': symbol, 'type': 'buy', 'quantity': quantity})
                
        elif trade_type == 'sell':
            if holdings[asset_id] >= quantity:
                portfolio.cash += cost
                holdings[asset_id] -= quantity
                
                # Update position info for VWAP calculation
                if position_info[asset_id]['total_quantity'] > 0:
                    # Calculate proportion of position being sold
                    proportion_sold = quantity / position_info[asset_id]['total_quantity']
                    cost_basis_sold = position_info[asset_id]['total_cost'] * proportion_sold
                    
                    position_info[asset_id]['total_cost'] -= cost_basis_sold
                    position_info[asset_id]['total_quantity'] -= quantity
                
                # Update portfolio in database
                portfolio.set_holdings(holdings)
                portfolio.set_position_info(position_info)
                
                # Record transaction in database
                transaction = Transaction(
                    user_id=current_user.id,
                    asset_id=asset.id,
                    legacy_symbol=asset.symbol,
                    timestamp=timestamp,
                    type='sell',
                    quantity=quantity,
                    price=price,
                    total_cost=cost
                )
                db.session.add(transaction)
                db.session.commit()
                
                emit('trade_confirmation', {'success': True, 'message': f'Sold {quantity} {symbol}', 'symbol': symbol, 'type': 'sell', 'quantity': quantity})
                emit('transaction_added', {
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'type': 'sell',
                    'asset_id': asset.id,
                    'quantity': quantity,
                    'price': price,
                    'total_cost': cost,
                    'user_id': current_user.id
                })
            else:
                emit('trade_confirmation', {'success': False, 'message': 'Insufficient holdings', 'symbol': symbol, 'type': 'sell', 'quantity': quantity})
        
        # Emit portfolio update to the user
        emit('portfolio_update', {
            'cash': portfolio.cash,
            'holdings': portfolio.get_holdings_by_symbol(),
            'position_info': portfolio.get_position_info_by_symbol()
        })
        
    except Exception as e:
        import traceback
        logger.error(f"Trade error: {e}")
        logger.error(f"Trade error traceback: {traceback.format_exc()}")
        emit('trade_confirmation', {'success': False, 'message': f'Trade processing error: {str(e)}'})

def update_prices():
    """Get updated prices from price service and emit to clients."""
    try:
        with app.app_context():
            # Get active assets and sync with price service
            # Double-check they're actually active and not expired
            now = current_utc()
            active_assets = Asset.query.filter_by(is_active=True).filter(Asset.expires_at > now).all()
            
            # Sync price service with active assets from database
            price_service.sync_assets_from_db(active_assets)
            
            # Get current prices from the price service
            current_prices = price_service.get_current_prices()
            
            # Enrich price data with expiration info
            enriched_prices = {}
            for asset in active_assets:
                if asset.symbol in current_prices:
                    price = current_prices[asset.symbol]['price']
                    
                    # Update database with current price
                    asset.current_price = price
                    
                    enriched_prices[asset.symbol] = {
                        'price': price,
                        'expires_at': asset.expires_at.isoformat(),
                        'time_to_expiry_seconds': asset.time_to_expiry().total_seconds() if asset.time_to_expiry() else 0,
                        'initial_price': asset.initial_price,
                        'volatility': asset.volatility,
                        'color': asset.color,
                        'created_at': asset.created_at.isoformat()
                    }
            
            # Commit price updates to database
            db.session.commit()
            
            socketio.emit('price_update', enriched_prices)
            
            # Emit individual price updates for charts
            for symbol, data in current_prices.items():
                # Only emit for active assets
                if any(a.symbol == symbol for a in active_assets):
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

# Background thread for expiration checking
def expiration_check_thread():
    """Background thread to check for and process expired assets."""
    while True:
        time.sleep(app.config.get('EXPIRATION_CHECK_INTERVAL', 60))  # Check every minute by default
        
        try:
            with app.app_context():
                logger.info("Checking for expired assets...")
                stats = asset_manager.process_expirations()
                
                if stats['expired_assets'] > 0:
                    logger.info(f"Processed {stats['expired_assets']} expired assets")
                    logger.info(f"Settled {stats.get('settlement_stats', {}).get('positions_settled', 0)} positions")
                    
                    # Give database a moment to ensure all commits are complete
                    time.sleep(0.5)
                    
                    # Notify all connected clients about settlements
                    socketio.emit('assets_updated', {
                        'message': f"{stats['expired_assets']} assets expired and settled",
                        'stats': stats
                    })
                    
                    # Signal all clients to refresh their portfolio data
                    socketio.emit('portfolio_refresh_needed', {})
                    
                    logger.info("Emitted settlement notifications to all clients")
                
        except Exception as e:
            logger.error(f"Error in expiration check thread: {e}")
            import traceback
            logger.error(traceback.format_exc())

# Start background threads
price_thread = threading.Thread(target=price_update_thread, daemon=True)
price_thread.start()

expiration_thread = threading.Thread(target=expiration_check_thread, daemon=True)
expiration_thread.start()

if __name__ == '__main__':
    # Initialize database tables
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created")
            
            # Initialize asset pool if empty
            active_assets = Asset.query.filter_by(is_active=True).count()
            if active_assets == 0:
                logger.info("No active assets found, initializing asset pool...")
                new_assets = asset_manager.initialize_asset_pool()
                logger.info(f"Created {len(new_assets)} initial assets")
            else:
                logger.info(f"Found {active_assets} active assets in database")
            
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT') or os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    logger.info(f"Starting application on port {port}, debug={debug}")
    
    # Run with appropriate settings for production vs development
    socketio.run(app, debug=debug, port=port, host='0.0.0.0')
