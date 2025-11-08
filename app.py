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
from collections import defaultdict
from sqlalchemy import inspect, text, or_
from sqlalchemy.exc import SQLAlchemyError
from config import config
from price_client import HybridPriceService
from models import db, User, Portfolio, Transaction, PriceData, Asset, Settlement, current_utc
from asset_manager import AssetManager
from validators import (
    ValidationError as InputValidationError,
    validate_trade,
    SymbolValidator,
    TradeValidator,
    PortfolioValidator,
    QueryValidator,
    safe_float_to_decimal
)

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
login_manager.login_view = 'login'  # type: ignore[assignment]

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
            user = User(username=username)  # type: ignore[call-arg]
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
    # Validate pagination parameters
    try:
        raw_limit = request.args.get('limit', 200, type=int) or 200
        transaction_limit = QueryValidator.validate_limit(raw_limit, max_limit=500)
    except InputValidationError as ve:
        logger.warning(f"Invalid limit parameter for user {current_user.id}: {ve}")
        return jsonify({'error': f'Invalid limit: {str(ve)}'}), 400
    
    portfolio = get_user_portfolio(current_user)
    
    # Validate portfolio cash balance
    try:
        PortfolioValidator.validate_cash_balance(safe_float_to_decimal(portfolio.cash))
    except InputValidationError as ve:
        logger.error(f"Invalid cash balance for user {current_user.id}: cash={portfolio.cash}, error={ve}")
        # Don't fail the request, but log the issue
    
    holdings_by_symbol = portfolio.get_holdings_by_symbol()
    position_info_by_symbol = portfolio.get_position_info_by_symbol()

    user_transactions = (
        Transaction.query
        .filter_by(user_id=current_user.id)
        .order_by(Transaction.timestamp.desc())
        .limit(transaction_limit)
        .all()
    )

    holdings_map = portfolio.get_holdings() or {}
    related_asset_ids = {asset_id for asset_id in holdings_map.keys() if asset_id}
    related_asset_ids.update(t.asset_id for t in user_transactions if t.asset_id)

    asset_colors = {}
    asset_lookup = {}
    if related_asset_ids:
        assets = Asset.query.filter(Asset.id.in_(related_asset_ids)).all()
        for asset in assets:
            if asset.symbol and asset.color:
                asset_colors[asset.symbol] = asset.color
            asset_lookup[asset.id] = asset

    transactions_payload = []
    for transaction in user_transactions:
        timestamp = int(transaction.timestamp) if transaction.timestamp is not None else 0
        color = None
        if transaction.asset and transaction.asset.color:
            color = transaction.asset.color
        elif transaction.symbol and transaction.symbol in asset_colors:
            color = asset_colors[transaction.symbol]

        if transaction.asset and transaction.asset.symbol and transaction.asset.color:
            asset_colors.setdefault(transaction.asset.symbol, transaction.asset.color)

        transactions_payload.append({
            'timestamp': timestamp,
            'symbol': transaction.symbol,
            'type': transaction.type,
            'asset_id': transaction.asset_id,
            'quantity': transaction.quantity,
            'price': transaction.price,
            'total_cost': transaction.total_cost,
            'user_id': transaction.user_id,
            'color': color
        })
    
    # Calculate per-asset P&L
    position_pnl = {}
    try:
        current_prices = price_service.get_current_prices()
        holdings_map = portfolio.get_holdings()
        position_info_map = portfolio.get_position_info()
        
        for asset_id, quantity in holdings_map.items():
            asset = asset_lookup.get(asset_id)
            if not asset or quantity <= 0:
                continue
                
            symbol = asset.symbol
            pos_info = position_info_map.get(asset_id, {})
            total_cost = float(pos_info.get('total_cost', 0.0))
            total_quantity = float(pos_info.get('total_quantity', 0.0))
            
            # Get current price
            price_data = current_prices.get(symbol, {})
            current_price = float(price_data.get('price', asset.current_price) if isinstance(price_data, dict) else asset.current_price)
            
            # Calculate P&L
            if total_quantity > 0:
                avg_cost = total_cost / total_quantity
                current_value = quantity * current_price
                cost_basis = quantity * avg_cost
                unrealized_pnl = current_value - cost_basis
                unrealized_pnl_percent = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0.0
                
                position_pnl[symbol] = {
                    'unrealized_pnl': unrealized_pnl,
                    'unrealized_pnl_percent': unrealized_pnl_percent,
                    'current_value': current_value,
                    'cost_basis': cost_basis,
                    'avg_cost': avg_cost
                }
    except Exception as e:
        logger.error(f"Error calculating position P&L: {e}")
    
    return jsonify({
        'user_id': current_user.id,
        'cash': portfolio.cash,
        'holdings': holdings_by_symbol,
        'position_info': position_info_by_symbol,
        'position_pnl': position_pnl,
        'asset_colors': asset_colors,
        'transactions': transactions_payload
    })

def calculate_portfolio_performance(portfolio, current_prices=None, active_assets=None, log_details=False):
    """Calculate performance metrics for a portfolio."""
    if portfolio is None:
        return {
            'portfolio_value': 0.0,
            'realized_pnl': 0.0,
            'unrealized_pnl': 0.0,
            'total_pnl': 0.0,
            'total_return': 0.0
        }

    # Starting values
    portfolio_cash = float(portfolio.cash or 0.0)
    total_portfolio_value = portfolio_cash
    total_unrealized_pnl = 0.0

    # Load active assets if not provided
    if active_assets is None:
        try:
            active_assets = Asset.query.filter_by(is_active=True).all()
        except Exception as exc:
            logger.error(f"Error loading active assets: {exc}")
            active_assets = []

    active_symbols = {asset.symbol for asset in active_assets if asset.symbol}

    # Load current prices if not provided
    if current_prices is None:
        try:
            current_prices = price_service.get_current_prices()
        except Exception as exc:
            if log_details:
                logger.error(f"Error getting current prices: {exc}")
            else:
                logger.debug(f"Error getting current prices: {exc}")
            current_prices = {}

    current_prices = current_prices or {}

    if active_symbols:
        current_prices = {
            symbol: data for symbol, data in current_prices.items()
            if symbol in active_symbols
        }

    if log_details:
        logger.info(f"Starting portfolio calculation - cash: {portfolio_cash}")
        logger.info(f"Current prices for performance calculation: {current_prices}")
    else:
        logger.debug(f"Calculating portfolio performance for user_id={portfolio.user_id}")

    holdings = portfolio.get_holdings()
    position_info = portfolio.get_position_info()

    if log_details:
        logger.info(f"Holdings: {holdings}, Position info: {position_info}")

    asset_lookup = {}
    if holdings:
        asset_ids = list(holdings.keys())
        assets = Asset.query.filter(Asset.id.in_(asset_ids)).all()
        asset_lookup = {asset.id: asset for asset in assets}

    # Guard against NaN portfolio values before processing
    if total_portfolio_value != total_portfolio_value:
        logger.error(f"Portfolio cash is NaN: {portfolio_cash}")
        total_portfolio_value = float(app.config.get('INITIAL_CASH', 100000.0))

    # Calculate market value and unrealized P&L
    for asset_id, quantity in (holdings or {}).items():
        try:
            asset = asset_lookup.get(asset_id)
            if not asset:
                continue

            symbol = asset.symbol
            if quantity > 0:
                price_record = current_prices.get(symbol)
                raw_price = price_record.get('price') if isinstance(price_record, dict) else None
                if raw_price is not None:
                    current_price = float(raw_price)
                else:
                    current_price = float(asset.current_price or 0.0)

                quantity = float(quantity) if quantity is not None else 0.0
                market_value = quantity * current_price

                if market_value == market_value:  # Ignore NaN results
                    total_portfolio_value += market_value

                symbol_position = position_info.get(asset_id, {}) if position_info else {}
                total_cost = symbol_position.get('total_cost') if symbol_position else 0.0
                total_quantity = symbol_position.get('total_quantity') if symbol_position else 0.0

                total_cost = float(total_cost) if total_cost is not None else 0.0
                total_quantity = float(total_quantity) if total_quantity is not None else 0.0

                if total_quantity > 0 and quantity > 0:
                    average_cost_per_share = total_cost / total_quantity
                    cost_basis_current = quantity * average_cost_per_share
                    unrealized_pnl = market_value - cost_basis_current
                    if unrealized_pnl == unrealized_pnl:  # Ignore NaN
                        total_unrealized_pnl += unrealized_pnl
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning(f"Error calculating market value for asset_id={asset_id}: {exc}")
            continue

    initial_value = float(app.config.get('INITIAL_CASH', 100000.0))
    total_pnl = total_portfolio_value - initial_value
    realized_pnl = total_pnl - total_unrealized_pnl

    if initial_value > 0:
        total_return_percent = ((total_portfolio_value - initial_value) / initial_value) * 100
    else:
        total_return_percent = 0.0

    # Sanitize NaN values
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

    if log_details:
        logger.info(
            f"Final portfolio values - Value: {total_portfolio_value}, P&L: {total_pnl}, Return: {total_return_percent}%"
        )

    return {
        'portfolio_value': total_portfolio_value,
        'realized_pnl': realized_pnl,
        'unrealized_pnl': total_unrealized_pnl,
        'total_pnl': total_pnl,
        'total_return': total_return_percent
    }

@app.route('/api/performance', methods=['GET'])
@login_required
def get_performance():
    portfolio = get_user_portfolio(current_user)
    performance = calculate_portfolio_performance(portfolio, log_details=True)

    return jsonify({
        'portfolio_value': round(performance['portfolio_value'], 2),
        'realized_pnl': round(performance['realized_pnl'], 2),
        'unrealized_pnl': round(performance['unrealized_pnl'], 2),
        'total_pnl': round(performance['total_pnl'], 2),
        'total_return': round(performance['total_return'], 2)
    })


@app.route('/api/performance/history', methods=['GET'])
@login_required
def get_performance_history():
    """Return a time series of portfolio value for the current user."""
    # Validate pagination parameters
    raw_limit = request.args.get('limit', 300, type=int) or 300
    limit = QueryValidator.validate_limit(raw_limit, max_limit=1000)
    # Ensure minimum of 50 for performance history
    limit = max(50, limit)

    portfolio = get_user_portfolio(current_user)
    transactions = (Transaction.query
                    .filter_by(user_id=current_user.id)
                    .order_by(Transaction.timestamp.asc())
                    .all())

    final_holdings = portfolio.get_holdings()
    relevant_asset_ids = set(final_holdings.keys())
    missing_symbols = set()

    for transaction in transactions:
        if transaction.asset_id:
            relevant_asset_ids.add(transaction.asset_id)
        elif transaction.legacy_symbol:
            missing_symbols.add(transaction.legacy_symbol)

    assets_from_symbols = []
    if missing_symbols:
        assets_from_symbols = Asset.query.filter(Asset.symbol.in_(missing_symbols)).all()
        for asset in assets_from_symbols:
            relevant_asset_ids.add(asset.id)

    assets = Asset.query.filter(Asset.id.in_(relevant_asset_ids)).all() if relevant_asset_ids else []
    asset_by_id = {asset.id: asset for asset in assets}
    asset_by_symbol = {asset.symbol: asset for asset in assets if asset.symbol}

    for asset in assets_from_symbols:
        asset_by_id[asset.id] = asset
        if asset.symbol:
            asset_by_symbol[asset.symbol] = asset

    for asset_id in final_holdings.keys():
        if asset_id not in asset_by_id:
            asset = Asset.query.get(asset_id)
            if asset:
                asset_by_id[asset.id] = asset
                if asset.symbol:
                    asset_by_symbol[asset.symbol] = asset

    current_cash = float(portfolio.cash or 0.0)
    initial_cash = current_cash

    for transaction in reversed(transactions):
        total_cost = float(transaction.total_cost or 0.0)
        tx_type = (transaction.type or '').lower()
        if tx_type == 'buy':
            initial_cash += total_cost
        elif tx_type in ('sell', 'settlement'):
            initial_cash -= total_cost

    snapshots = [{
        'timestamp': None,
        'cash': initial_cash,
        'holdings': {}
    }]
    holdings_state = defaultdict(float)
    cash_state = initial_cash

    now_ms = int(time.time() * 1000)

    for transaction in transactions:
        tx_type = (transaction.type or '').lower()
        total_cost = float(transaction.total_cost or 0.0)
        quantity = float(transaction.quantity or 0.0)
        asset_id = transaction.asset_id

        if not asset_id and transaction.legacy_symbol:
            asset = asset_by_symbol.get(transaction.legacy_symbol)
            if not asset:
                asset = Asset.query.filter_by(symbol=transaction.legacy_symbol).order_by(Asset.created_at.desc()).first()
                if asset:
                    asset_by_id[asset.id] = asset
                    if asset.symbol:
                        asset_by_symbol[asset.symbol] = asset
                        relevant_asset_ids.add(asset.id)
            if asset:
                asset_id = asset.id

        if tx_type not in ('buy', 'sell', 'settlement'):
            continue

        if asset_id is None and tx_type != 'settlement':
            # Without an asset reference we cannot value this trade
            continue

        if tx_type == 'buy':
            cash_state -= total_cost
            if asset_id is not None:
                holdings_state[asset_id] += quantity
        elif tx_type == 'sell':
            cash_state += total_cost
            if asset_id is not None:
                holdings_state[asset_id] -= quantity
        elif tx_type == 'settlement':
            cash_state += total_cost
            if asset_id is not None:
                holdings_state[asset_id] = 0.0

        if asset_id is not None and holdings_state[asset_id] < 0:
            holdings_state[asset_id] = 0.0

        keys_to_delete = [aid for aid, qty in holdings_state.items() if abs(qty) < 1e-8]
        for aid in keys_to_delete:
            holdings_state.pop(aid, None)

        sanitized_holdings = {aid: qty for aid, qty in holdings_state.items()}
        timestamp = int(transaction.timestamp) if transaction.timestamp is not None else now_ms
        snapshots.append({
            'timestamp': timestamp,
            'cash': cash_state,
            'holdings': sanitized_holdings
        })

    final_snapshot_holdings = {aid: float(qty) for aid, qty in final_holdings.items() if abs(float(qty)) > 1e-8}
    snapshots.append({
        'timestamp': now_ms,
        'cash': float(portfolio.cash or 0.0),
        'holdings': final_snapshot_holdings
    })

    relevant_symbols = {asset.symbol for asset in asset_by_id.values() if asset and asset.symbol}
    history_limit = max(limit * 2, 200)
    raw_history = price_service.get_price_history(limit=history_limit) if relevant_symbols else {}
    current_prices = price_service.get_current_prices() if relevant_symbols else {}

    filtered_history = {}
    min_history_time = None

    for symbol in relevant_symbols:
        history_points = raw_history.get(symbol, []) or []
        deduped = {}
        for point in history_points:
            ts = point.get('time')
            price_val = point.get('price')
            try:
                ts_int = int(ts)
                price_float = float(price_val)
            except (TypeError, ValueError):
                continue
            deduped[ts_int] = price_float

        current_info = current_prices.get(symbol)
        if current_info:
            last_update = current_info.get('last_update')
            try:
                current_ts = int(last_update) if last_update is not None else now_ms
            except (TypeError, ValueError):
                current_ts = now_ms
            try:
                price_float = float(current_info.get('price'))
            except (TypeError, ValueError):
                price_float = None
            if price_float is not None:
                deduped[current_ts] = price_float

        sorted_points = [{'time': ts, 'price': price} for ts, price in sorted(deduped.items())]
        filtered_history[symbol] = sorted_points
        if sorted_points:
            symbol_first_time = sorted_points[0]['time']
            if min_history_time is None or symbol_first_time < min_history_time:
                min_history_time = symbol_first_time

    timeline_set = set()
    for history in filtered_history.values():
        for point in history:
            timeline_set.add(point['time'])

    for snapshot in snapshots:
        snapshot_time = snapshot['timestamp']
        if snapshot_time is not None:
            timeline_set.add(int(snapshot_time))

    timeline_set.add(now_ms)
    timeline = sorted(timeline_set)

    if min_history_time is not None:
        timeline = [ts for ts in timeline if ts >= min_history_time]

    snapshots.sort(key=lambda snap: float('-inf') if snap['timestamp'] is None else snap['timestamp'])
    asset_symbol_by_id = {asset_id: asset.symbol for asset_id, asset in asset_by_id.items() if asset and asset.symbol}

    price_indices = {symbol: 0 for symbol in filtered_history.keys()}
    points = []
    snapshot_index = 0

    for timestamp in timeline:
        while snapshot_index + 1 < len(snapshots):
            next_snapshot = snapshots[snapshot_index + 1]
            next_time = next_snapshot['timestamp']
            if next_time is not None and next_time <= timestamp:
                snapshot_index += 1
            else:
                break

        current_snapshot = snapshots[snapshot_index]
        cash_value = float(current_snapshot['cash'])
        holdings = current_snapshot['holdings']
        holdings_value = 0.0
        missing_price = False

        for asset_id, quantity in holdings.items():
            if quantity <= 0:
                continue
            symbol = asset_symbol_by_id.get(asset_id)
            if not symbol:
                missing_price = True
                break
            history = filtered_history.get(symbol, [])
            if not history:
                missing_price = True
                break
            index = price_indices[symbol]
            while index + 1 < len(history) and history[index + 1]['time'] <= timestamp:
                index += 1
            price_indices[symbol] = index
            point = history[index]
            if point['time'] > timestamp:
                missing_price = True
                break
            price = point['price']
            holdings_value += quantity * price

        if missing_price:
            continue

        points.append({
            'time': int(timestamp),
            'value': round(cash_value + holdings_value, 2)
        })

    if not points:
        performance = calculate_portfolio_performance(portfolio)
        current_value = round(performance['portfolio_value'], 2)
        baseline_time = max(now_ms - 60000, 0)
        points = [
            {'time': baseline_time, 'value': current_value},
            {'time': now_ms, 'value': current_value}
        ]
    else:
        deduped_points = {point['time']: point['value'] for point in points}
        points = [{'time': ts, 'value': val} for ts, val in sorted(deduped_points.items())]
        if len(points) == 1:
            earlier_time = max(points[0]['time'] - 60000, 0)
            points.insert(0, {'time': earlier_time, 'value': points[0]['value']})

    if len(points) > limit:
        points = points[-limit:]

    return jsonify({'points': points})

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
    # Validate pagination parameters
    try:
        raw_limit = request.args.get('limit', 200, type=int) or 200
        limit = QueryValidator.validate_limit(raw_limit, max_limit=500)
    except InputValidationError as ve:
        logger.warning(f"Invalid limit parameter for user {current_user.id}: {ve}")
        return jsonify({'error': f'Invalid limit: {str(ve)}'}), 400

    transactions = (
        Transaction.query
        .filter_by(user_id=current_user.id)
        .order_by(Transaction.timestamp.desc())
        .limit(limit)
        .all()
    )

    payload = []
    for transaction in transactions:
        timestamp = int(transaction.timestamp) if transaction.timestamp is not None else 0
        color = transaction.asset.color if transaction.asset and transaction.asset.color else None
        payload.append({
            'timestamp': timestamp,
            'symbol': transaction.symbol,
            'type': transaction.type,
            'asset_id': transaction.asset_id,
            'quantity': transaction.quantity,
            'price': transaction.price,
            'total_cost': transaction.total_cost,
            'user_id': transaction.user_id,
            'color': color
        })

    return jsonify(payload)

@app.route('/api/transactions/all', methods=['GET'])
@login_required
def get_all_transactions():
    """Return anonymized transactions across all accounts."""
    # Validate pagination parameters
    try:
        raw_limit = request.args.get('limit', 100, type=int) or 100
        limit = QueryValidator.validate_limit(raw_limit, max_limit=200)
    except InputValidationError as ve:
        logger.warning(f"Invalid limit parameter in get_all_transactions: {ve}")
        return jsonify({'error': f'Invalid limit: {str(ve)}'}), 400

    transactions = (Transaction.query
                    .order_by(Transaction.timestamp.desc())
                    .limit(limit)
                    .all())

    return jsonify([{
        'timestamp': int(t.timestamp) if t.timestamp is not None else 0,
        'symbol': t.symbol,
        'type': t.type,
        'quantity': t.quantity,
        'price': t.price,
        'total_cost': t.total_cost,
        'user_id': t.user_id,
        'color': t.asset.color if t.asset and t.asset.color else None
    } for t in transactions])

@app.route('/api/leaderboard', methods=['GET'])
@login_required
def get_leaderboard():
    """Return users ranked by total profit & loss."""
    # Validate pagination parameters
    try:
        raw_limit = request.args.get('limit', 25, type=int) or 25
        limit = QueryValidator.validate_limit(raw_limit, max_limit=100)
    except InputValidationError as ve:
        logger.warning(f"Invalid limit parameter in leaderboard: {ve}")
        return jsonify({'error': f'Invalid limit: {str(ve)}'}), 400

    try:
        raw_prices = price_service.get_current_prices()
    except Exception as exc:
        logger.error(f"Error getting current prices for leaderboard: {exc}")
        raw_prices = {}

    active_assets = Asset.query.filter_by(is_active=True).all()
    active_symbols = {asset.symbol for asset in active_assets if asset.symbol}
    filtered_prices = {
        symbol: data for symbol, data in (raw_prices or {}).items()
        if symbol in active_symbols
    }

    portfolios = Portfolio.query.all()
    leaderboard = []

    for portfolio in portfolios:
        performance = calculate_portfolio_performance(
            portfolio,
            current_prices=filtered_prices,
            active_assets=active_assets,
            log_details=False
        )
        leaderboard.append({
            'user_id': portfolio.user_id,
            'total_pnl': performance['total_pnl']
        })

    leaderboard.sort(key=lambda entry: entry['total_pnl'], reverse=True)

    results = [
        {
            'user_id': entry['user_id'],
            'total_pnl': round(entry['total_pnl'], 2)
        }
        for entry in leaderboard[:limit]
    ]

    return jsonify(results)

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
    # Validate pagination parameters
    try:
        raw_limit = request.args.get('limit', 50, type=int) or 50
        limit = QueryValidator.validate_limit(raw_limit, max_limit=200)
    except InputValidationError as ve:
        logger.warning(f"Invalid limit parameter for user {current_user.id} in settlements: {ve}")
        return jsonify({'error': f'Invalid limit: {str(ve)}'}), 400
    
    settlements = Settlement.query.filter_by(user_id=current_user.id).order_by(Settlement.settled_at.desc()).limit(limit).all()
    
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
        # Step 1: INPUT VALIDATION - Validate all inputs before any processing
        raw_symbol = data.get('symbol', '')
        try:
            raw_quantity = data.get('quantity', 0)
            raw_type = data.get('type', '')
            
            # Validate trade type first (simple check)
            validated_type = TradeValidator.validate_trade_type(raw_type)
            
            # Validate and sanitize symbol
            validated_symbol = SymbolValidator.validate_symbol(raw_symbol)
            
            # Validate quantity (detailed validation)
            validated_quantity = TradeValidator.validate_quantity(raw_quantity)
            
        except InputValidationError as ve:
            logger.warning(f"Trade validation failed for user {current_user.id}: {ve}")
            emit('trade_confirmation', {
                'success': False,
                'message': f'Invalid input: {str(ve)}',
                'symbol': raw_symbol
            })
            return
        
        # Step 2: ASSET VALIDATION - Check asset exists and is tradeable
        asset = Asset.query.filter_by(symbol=validated_symbol, is_active=True).first()
        if not asset:
            emit('trade_confirmation', {
                'success': False, 
                'message': f'Asset {validated_symbol} is not available for trading (may have expired)', 
                'symbol': validated_symbol
            })
            return
        
        # Step 3: PRICE VALIDATION - Get and validate current price
        current_prices = price_service.get_current_prices()
        if validated_symbol not in current_prices:
            emit('trade_confirmation', {
                'success': False,
                'message': f'Price not available for {validated_symbol}',
                'symbol': validated_symbol
            })
            return
        
        try:
            validated_price = TradeValidator.validate_price(current_prices[validated_symbol]['price'])
        except InputValidationError as ve:
            logger.error(f"Invalid price from price service for {validated_symbol}: {ve}")
            emit('trade_confirmation', {
                'success': False,
                'message': f'Invalid price for {validated_symbol}',
                'symbol': validated_symbol
            })
            return
        
        # Step 4: TRADE VALUE VALIDATION - Calculate and validate total cost
        try:
            validated_cost = TradeValidator.validate_trade_value(validated_quantity, validated_price)
        except InputValidationError as ve:
            logger.warning(f"Trade value validation failed: {ve}")
            emit('trade_confirmation', {
                'success': False,
                'message': str(ve),
                'symbol': validated_symbol
            })
            return
        
        # Convert validated Decimal values back to float for database (temporary until full Decimal migration)
        quantity = float(validated_quantity)
        price = float(validated_price)
        cost = float(validated_cost)
        trade_type = validated_type
        symbol = validated_symbol
        
        timestamp = time.time() * 1000  # JavaScript-compatible timestamp
        
        # Step 5: Get portfolio (now safe to proceed)
        portfolio = get_user_portfolio(current_user)

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
            # Validate sufficient funds before executing buy
            try:
                PortfolioValidator.validate_sufficient_funds(
                    safe_float_to_decimal(portfolio.cash),
                    validated_cost
                )
            except InputValidationError as ve:
                logger.warning(f"Insufficient funds for user {current_user.id}: cash={portfolio.cash}, cost={cost}")
                emit('trade_confirmation', {
                    'success': False, 
                    'message': 'Insufficient funds', 
                    'symbol': symbol, 
                    'type': 'buy', 
                    'quantity': quantity
                })
                return
            
            # Execute buy transaction
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
                'user_id': current_user.id,
                'color': asset.color
            })
            socketio.emit('global_transaction_update', {
                'timestamp': int(timestamp),
                'symbol': symbol,
                'type': 'buy',
                'quantity': quantity,
                'price': price,
                'total_cost': cost,
                'user_id': current_user.id,
                'color': asset.color
            })
                
        elif trade_type == 'sell':
            # Validate sufficient holdings before executing sell
            try:
                PortfolioValidator.validate_sufficient_holdings(
                    safe_float_to_decimal(holdings[asset_id]),
                    validated_quantity
                )
            except InputValidationError as ve:
                logger.warning(f"Insufficient holdings for user {current_user.id}: has={holdings[asset_id]}, needs={quantity}")
                emit('trade_confirmation', {
                    'success': False, 
                    'message': 'Insufficient holdings', 
                    'symbol': symbol, 
                    'type': 'sell', 
                    'quantity': quantity
                })
                return
            
            # Execute sell transaction
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
                'user_id': current_user.id,
                'color': asset.color
            })
            socketio.emit('global_transaction_update', {
                'timestamp': int(timestamp),
                'symbol': symbol,
                'type': 'sell',
                'quantity': quantity,
                'price': price,
                'total_cost': cost,
                'user_id': current_user.id,
                'color': asset.color
            })
        
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
            
            # Track assets that dropped below threshold
            worthless_assets = []
            
            # Enrich price data with expiration info
            enriched_prices = {}
            for asset in active_assets:
                if asset.symbol in current_prices:
                    price = current_prices[asset.symbol]['price']
                    
                    # Update database with current price
                    asset.current_price = price
                    
                    # Check if asset has fallen below worthless threshold
                    if price < 0.01:
                        logger.warning(f"Asset {asset.symbol} dropped to ${price:.4f} - will be auto-settled")
                        worthless_assets.append(asset)
                    
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
            
            # Process worthless assets immediately if any found
            if worthless_assets:
                logger.info(f"Immediately settling {len(worthless_assets)} worthless asset(s)")
                
                # Mark them as expired with their worthless price
                for asset in worthless_assets:
                    asset.expire(final_price=asset.current_price)
                db.session.commit()
                
                # Settle positions
                settlement_stats = asset_manager.settle_expired_positions(worthless_assets)
                
                # Remove from enriched prices since they're no longer active
                for asset in worthless_assets:
                    if asset.symbol in enriched_prices:
                        del enriched_prices[asset.symbol]
                    # Remove from price service
                    if hasattr(price_service, 'fallback') and asset.symbol in price_service.fallback.assets:
                        del price_service.fallback.assets[asset.symbol]
                
                # Build symbol list for notification
                symbols = [asset.symbol for asset in worthless_assets]
                symbols_str = ', '.join(symbols)
                
                # Notify clients about the settlement
                socketio.emit('assets_updated', {
                    'message': f"{len(worthless_assets)} asset(s) auto-settled ({symbols_str})",
                    'stats': {
                        'expired_assets': 0,
                        'worthless_assets': len(worthless_assets),
                        'total_settled': len(worthless_assets),
                        'settlement_stats': settlement_stats
                    }
                })
                
                # Signal clients to refresh portfolio
                socketio.emit('portfolio_refresh_needed', {})
                
                logger.info(f"Auto-settled {len(worthless_assets)} worthless assets")
            
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
                    
                    # Build symbol list for notification
                    symbols = stats.get('expired_symbols', [])
                    symbols_str = ', '.join(symbols) if symbols else ''
                    
                    # Give database a moment to ensure all commits are complete
                    time.sleep(0.5)
                    
                    # Notify all connected clients about settlements
                    socketio.emit('assets_updated', {
                        'message': f"{stats['expired_assets']} asset(s) expired and settled ({symbols_str})",
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
