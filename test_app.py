"""
Comprehensive test suite for app.py

Tests Flask application including:
- Authentication (login, register, logout)
- API endpoints (portfolio, transactions, assets, etc.)
- Trade handling via WebSocket
- Performance calculations
- Error handling and edge cases
"""
import pytest
import json
from flask import url_for
from flask_socketio import SocketIOTestClient
from models import db, User, Portfolio, Asset, Transaction, Settlement, current_utc
from datetime import timedelta


class TestAuthentication:
    """Test user authentication flows."""
    
    def test_register_success(self, client, app):
        """Test successful user registration."""
        with app.app_context():
            response = client.post('/register', data={
                'username': 'newuser',
                'password': 'ValidPass123!',
                'password2': 'ValidPass123!',
                'csrf_token': 'test'  # CSRF disabled in testing
            }, follow_redirects=True)
            
            assert response.status_code == 200
            user = User.query.filter_by(username='newuser').first()
            assert user is not None
            assert user.portfolio is not None
    
    def test_register_duplicate_username(self, client, app, test_user):
        """Test registration with duplicate username fails."""
        with app.app_context():
            response = client.post('/register', data={
                'username': 'testuser',  # Already exists
                'password': 'ValidPass123!',
                'password2': 'ValidPass123!',
                'csrf_token': 'test'
            })
            
            assert b'already exists' in response.data.lower()
    
    def test_register_password_mismatch(self, client, app):
        """Test registration fails when passwords don't match."""
        with app.app_context():
            response = client.post('/register', data={
                'username': 'newuser',
                'password': 'ValidPass123!',
                'password2': 'DifferentPass123!',
                'csrf_token': 'test'
            })
            
            assert b'must match' in response.data.lower()
    
    def test_register_weak_password(self, client, app):
        """Test registration fails with weak password."""
        with app.app_context():
            response = client.post('/register', data={
                'username': 'newuser',
                'password': 'weak',  # Too short
                'password2': 'weak',
                'csrf_token': 'test'
            })
            
            assert response.status_code == 200
            assert b'at least 8 characters' in response.data.lower()
    
    def test_register_invalid_username(self, client, app):
        """Test registration fails with invalid username."""
        with app.app_context():
            response = client.post('/register', data={
                'username': 'ab',  # Too short
                'password': 'ValidPass123!',
                'password2': 'ValidPass123!',
                'csrf_token': 'test'
            })
            
            assert b'between 3 and 20' in response.data.lower()
    
    def test_login_success(self, client, app, test_user):
        """Test successful login."""
        with app.app_context():
            response = client.post('/login', data={
                'username': 'testuser',
                'password': 'TestPass123!',
                'csrf_token': 'test'
            }, follow_redirects=True)
            
            assert response.status_code == 200
    
    def test_login_wrong_password(self, client, app, test_user):
        """Test login fails with wrong password."""
        with app.app_context():
            response = client.post('/login', data={
                'username': 'testuser',
                'password': 'WrongPassword123!',
                'csrf_token': 'test'
            })
            
            assert b'invalid' in response.data.lower()
    
    def test_login_nonexistent_user(self, client, app):
        """Test login fails for non-existent user."""
        with app.app_context():
            response = client.post('/login', data={
                'username': 'nonexistent',
                'password': 'TestPass123!',
                'csrf_token': 'test'
            })
            
            assert b'invalid' in response.data.lower()
    
    def test_logout(self, authenticated_client, app):
        """Test logout."""
        with app.app_context():
            response = authenticated_client.get('/logout', follow_redirects=True)
            
            assert response.status_code == 200
            # Should redirect to login page
            assert b'login' in response.data.lower()
    
    def test_rate_limiting(self, client, app, test_user):
        """Test login rate limiting."""
        with app.app_context():
            # Make multiple failed login attempts
            for _ in range(6):
                client.post('/login', data={
                    'username': 'testuser',
                    'password': 'wrongpassword',
                    'csrf_token': 'test'
                })
            
            # Next attempt should be rate limited
            response = client.post('/login', data={
                'username': 'testuser',
                'password': 'TestPass123!',
                'csrf_token': 'test'
            })
            
            assert b'too many' in response.data.lower()


class TestPortfolioEndpoints:
    """Test portfolio-related API endpoints."""
    
    def test_get_portfolio(self, authenticated_client, app, test_user_with_portfolio):
        """Test getting portfolio data."""
        with app.app_context():
            response = authenticated_client.get('/api/portfolio')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'cash' in data
            assert 'holdings' in data
            assert data['cash'] == 100000.0
    
    def test_get_portfolio_unauthorized(self, client, app):
        """Test portfolio endpoint requires authentication."""
        with app.app_context():
            response = client.get('/api/portfolio')
            
            assert response.status_code == 401
    
    def test_get_portfolio_with_holdings(self, authenticated_client_with_holdings, app):
        """Test portfolio with actual holdings."""
        with app.app_context():
            response = authenticated_client_with_holdings.get('/api/portfolio')
            
            data = json.loads(response.data)
            assert 'holdings' in data
            assert len(data['holdings']) > 0
    
    def test_get_portfolio_with_transactions(self, authenticated_client, app, buy_transaction):
        """Test portfolio includes transaction history."""
        with app.app_context():
            response = authenticated_client.get('/api/portfolio')
            
            data = json.loads(response.data)
            assert 'transactions' in data
            assert len(data['transactions']) > 0
    
    def test_get_portfolio_pagination(self, authenticated_client, app, test_user_with_portfolio):
        """Test portfolio transaction pagination."""
        with app.app_context():
            response = authenticated_client.get('/api/portfolio?limit=10')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data['transactions']) <= 10


class TestPerformanceEndpoints:
    """Test performance calculation endpoints."""
    
    def test_get_performance(self, authenticated_client, app, test_user_with_portfolio):
        """Test getting performance metrics."""
        with app.app_context():
            response = authenticated_client.get('/api/performance')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'portfolio_value' in data
            assert 'realized_pnl' in data
            assert 'unrealized_pnl' in data
            assert 'total_pnl' in data
            assert 'total_return' in data
    
    def test_get_performance_history(self, authenticated_client, app, test_user_with_portfolio):
        """Test getting performance history."""
        with app.app_context():
            response = authenticated_client.get('/api/performance/history')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'points' in data
            assert isinstance(data['points'], list)
    
    def test_performance_history_pagination(self, authenticated_client, app, test_user_with_portfolio):
        """Test performance history pagination."""
        with app.app_context():
            response = authenticated_client.get('/api/performance/history?limit=50')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data['points']) <= 50


class TestTransactionEndpoints:
    """Test transaction-related endpoints."""
    
    def test_get_transactions(self, authenticated_client, app, buy_transaction):
        """Test getting user transactions."""
        with app.app_context():
            response = authenticated_client.get('/api/transactions')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert isinstance(data, list)
            assert len(data) > 0
    
    def test_get_all_transactions(self, authenticated_client, app, buy_transaction):
        """Test getting all transactions (anonymized)."""
        with app.app_context():
            response = authenticated_client.get('/api/transactions/all')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert isinstance(data, list)
    
    def test_transactions_pagination(self, authenticated_client, app, test_user_with_portfolio):
        """Test transaction pagination."""
        with app.app_context():
            response = authenticated_client.get('/api/transactions?limit=5')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data) <= 5


class TestAssetEndpoints:
    """Test asset-related endpoints."""
    
    def test_get_assets(self, client, app, multiple_assets):
        """Test getting active assets."""
        with app.app_context():
            response = client.get('/api/assets')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data) == 5
            for symbol, info in data.items():
                assert 'price' in info
                assert 'expires_at' in info
    
    def test_get_assets_history(self, client, app, multiple_assets):
        """Test getting asset price history."""
        with app.app_context():
            response = client.get('/api/assets/history')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert isinstance(data, dict)
    
    def test_get_assets_summary(self, client, app, multiple_assets):
        """Test getting asset lifecycle summary."""
        with app.app_context():
            response = client.get('/api/assets/summary')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'active_count' in data
    
    def test_get_open_interest(self, client, app, user_with_holdings):
        """Test getting open interest data."""
        with app.app_context():
            response = client.get('/api/open-interest')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert isinstance(data, dict)


class TestSettlementEndpoints:
    """Test settlement-related endpoints."""
    
    def test_get_settlements(self, authenticated_client, app, settlement_record):
        """Test getting user settlements."""
        with app.app_context():
            response = authenticated_client.get('/api/settlements')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert isinstance(data, list)
            assert len(data) > 0
    
    def test_settlements_pagination(self, authenticated_client, app, settlement_record):
        """Test settlement pagination."""
        with app.app_context():
            response = authenticated_client.get('/api/settlements?limit=10')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data) <= 10


class TestLeaderboardEndpoint:
    """Test leaderboard endpoint."""
    
    def test_get_leaderboard(self, authenticated_client, app, multiple_users):
        """Test getting leaderboard."""
        with app.app_context():
            response = authenticated_client.get('/api/leaderboard')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert isinstance(data, list)
    
    def test_leaderboard_pagination(self, authenticated_client, app, multiple_users):
        """Test leaderboard pagination."""
        with app.app_context():
            response = authenticated_client.get('/api/leaderboard?limit=2')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data) <= 2


class TestErrorHandling:
    """Test error handling and validation."""
    
    def test_invalid_limit_parameter(self, authenticated_client, app):
        """Test invalid limit parameter handling."""
        with app.app_context():
            response = authenticated_client.get('/api/portfolio?limit=invalid')
            
            # Should still work with default limit
            assert response.status_code == 200
    
    def test_negative_limit_parameter(self, authenticated_client, app):
        """Test negative limit parameter handling."""
        with app.app_context():
            response = authenticated_client.get('/api/portfolio?limit=-10')
            
            # Should clamp to minimum valid value
            assert response.status_code == 200
    
    def test_excessive_limit_parameter(self, authenticated_client, app):
        """Test excessive limit parameter handling."""
        with app.app_context():
            response = authenticated_client.get('/api/portfolio?limit=99999')
            
            # Should clamp to maximum
            assert response.status_code == 200
    
    def test_unauthorized_endpoints(self, client, app):
        """Test unauthorized access to protected endpoints."""
        with app.app_context():
            protected_endpoints = [
                '/api/portfolio',
                '/api/performance',
                '/api/transactions',
                '/api/settlements',
                '/api/leaderboard'
            ]
            
            for endpoint in protected_endpoints:
                response = client.get(endpoint)
                assert response.status_code in [302, 401]  # Redirect or unauthorized


class TestStaticPages:
    """Test static page routes."""
    
    def test_about_page(self, client, app):
        """Test about page loads."""
        with app.app_context():
            response = client.get('/about')
            
            assert response.status_code == 200
    
    def test_index_requires_auth(self, client, app):
        """Test index page requires authentication."""
        with app.app_context():
            response = client.get('/')
            
            # Should redirect to login
            assert response.status_code == 302


class TestPortfolioCalculations:
    """Test portfolio calculation functions."""
    
    def test_calculate_portfolio_value(self, app, user_with_holdings, test_asset, mock_price_service):
        """Test portfolio value calculation."""
        with app.app_context():
            from app import calculate_portfolio_performance
            
            # Set current price
            mock_price_service.set_price('TEST', 110.0)
            
            user = user_with_holdings
            portfolio = user.portfolio
            
            performance = calculate_portfolio_performance(
                portfolio,
                current_prices=mock_price_service.get_current_prices(),
                active_assets=[test_asset]
            )
            
            # Portfolio should be: $50,000 cash + (100 shares * $110) = $61,000
            assert performance['portfolio_value'] == 61000.0
    
    def test_calculate_unrealized_pnl(self, app, user_with_holdings, test_asset, mock_price_service):
        """Test unrealized P&L calculation."""
        with app.app_context():
            from app import calculate_portfolio_performance
            
            # Set current price higher than cost basis
            mock_price_service.set_price('TEST', 110.0)
            
            user = user_with_holdings
            portfolio = user.portfolio
            
            performance = calculate_portfolio_performance(
                portfolio,
                current_prices=mock_price_service.get_current_prices(),
                active_assets=[test_asset]
            )
            
            # Unrealized P&L: (100 shares * $110) - $10,000 cost = $1,000
            assert performance['unrealized_pnl'] == 1000.0
    
    def test_calculate_total_return(self, app, user_with_holdings, test_asset, mock_price_service):
        """Test total return percentage calculation."""
        with app.app_context():
            from app import calculate_portfolio_performance
            
            mock_price_service.set_price('TEST', 110.0)
            
            user = user_with_holdings
            portfolio = user.portfolio
            
            performance = calculate_portfolio_performance(
                portfolio,
                current_prices=mock_price_service.get_current_prices(),
                active_assets=[test_asset]
            )
            
            # Total P&L: $61,000 - $100,000 initial = -$39,000 (-39%)
            assert performance['total_return'] < 0


class TestInputValidation:
    """Test input validation throughout the application."""
    
    def test_sql_injection_protection_username(self, client, app):
        """Test SQL injection attempts in username are blocked."""
        with app.app_context():
            response = client.post('/register', data={
                'username': "admin'; DROP TABLE users;--",
                'password': 'ValidPass123!',
                'password2': 'ValidPass123!',
                'csrf_token': 'test'
            })
            
            # Should fail validation before reaching database
            assert User.query.filter_by(username="admin'; DROP TABLE users;--").first() is None
    
    def test_xss_protection(self, client, app):
        """Test XSS attempts are sanitized."""
        with app.app_context():
            response = client.post('/register', data={
                'username': '<script>alert("xss")</script>',
                'password': 'ValidPass123!',
                'password2': 'ValidPass123!',
                'csrf_token': 'test'
            })
            
            # Should fail validation
            assert User.query.filter_by(username='<script>alert("xss")</script>').first() is None


class TestDatabaseIntegrity:
    """Test database integrity and constraints."""
    
    def test_portfolio_cash_constraint(self, app, test_user_with_portfolio):
        """Test portfolio cash constraints are enforced."""
        with app.app_context():
            from sqlalchemy.exc import IntegrityError
            
            user = User.query.filter_by(username='testuser').first()
            portfolio = user.portfolio
            
            # Try to set negative cash
            portfolio.cash = -1000.0
            
            with pytest.raises(IntegrityError):
                db.session.commit()
    
    def test_transaction_constraints(self, app, test_user_with_portfolio, test_asset):
        """Test transaction constraints are enforced."""
        with app.app_context():
            from sqlalchemy.exc import IntegrityError
            
            # Try to create transaction with negative quantity
            transaction = Transaction(
                user_id=test_user_with_portfolio.id,
                asset_id=test_asset.id,
                legacy_symbol=test_asset.symbol,
                timestamp=current_utc().timestamp() * 1000,
                type='buy',
                quantity=-10.0,  # Invalid!
                price=100.0,
                total_cost=1000.0
            )
            db.session.add(transaction)
            
            with pytest.raises(IntegrityError):
                db.session.commit()


class TestConcurrency:
    """Test concurrent operations."""
    
    def test_concurrent_user_creation(self, app):
        """Test multiple users can be created simultaneously."""
        with app.app_context():
            users = []
            for i in range(10):
                user = User(username=f'concurrent{i}')
                user.set_password('TestPass123!')
                db.session.add(user)
                users.append(user)
            
            db.session.commit()
            
            # All users should be created
            assert User.query.count() >= 10
    
    def test_concurrent_transactions(self, app, test_user_with_portfolio, multiple_assets):
        """Test multiple transactions can be created simultaneously."""
        with app.app_context():
            transactions = []
            for i, asset in enumerate(multiple_assets):
                transaction = Transaction(
                    user_id=test_user_with_portfolio.id,
                    asset_id=asset.id,
                    legacy_symbol=asset.symbol,
                    timestamp=current_utc().timestamp() * 1000 + i,
                    type='buy',
                    quantity=10.0,
                    price=100.0,
                    total_cost=1000.0
                )
                db.session.add(transaction)
                transactions.append(transaction)
            
            db.session.commit()
            
            # All transactions should be created
            assert Transaction.query.filter_by(user_id=test_user_with_portfolio.id).count() >= 5
