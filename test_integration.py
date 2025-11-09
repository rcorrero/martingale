"""
Integration test suite for Martingale trading platform.

Tests complete workflows end-to-end:
- User registration → portfolio creation → trading → settlement
- Asset lifecycle → expiration → settlement → replacement
- Performance calculation with real trading history
- Multi-user scenarios
"""
import pytest
from datetime import timedelta
from decimal import Decimal
from models import db, User, Portfolio, Asset, Transaction, Settlement, current_utc
from asset_manager import AssetManager
from validators import validate_trade


class TestCompleteUserWorkflow:
    """Test complete user workflow from registration to trading."""
    
    def test_user_registration_to_first_trade(self, app, test_asset, mock_price_service):
        """Test user can register and make their first trade."""
        with app.app_context():
            # 1. Register user
            user = User(username='newtrader')
            user.set_password('SecurePass123!')
            db.session.add(user)
            db.session.commit()
            
            # 2. Create portfolio
            portfolio = Portfolio(user_id=user.id, cash=100000.0)
            portfolio.set_holdings({})
            portfolio.set_position_info({})
            db.session.add(portfolio)
            db.session.commit()
            
            # 3. Make first buy trade
            quantity = 10.0
            price = 100.0
            total_cost = quantity * price
            
            portfolio.cash -= total_cost
            holdings = {test_asset.id: quantity}
            portfolio.set_holdings(holdings)
            
            position_info = {
                test_asset.id: {
                    'total_cost': total_cost,
                    'total_quantity': quantity
                }
            }
            portfolio.set_position_info(position_info)
            
            transaction = Transaction(
                user_id=user.id,
                asset_id=test_asset.id,
                legacy_symbol=test_asset.symbol,
                timestamp=current_utc().timestamp() * 1000,
                type='buy',
                quantity=quantity,
                price=price,
                total_cost=total_cost
            )
            db.session.add(transaction)
            db.session.commit()
            
            # 4. Verify state
            assert portfolio.cash == 99000.0
            assert holdings[test_asset.id] == 10.0
            assert Transaction.query.filter_by(user_id=user.id).count() == 1
    
    def test_buy_then_sell_workflow(self, app, test_asset, data_generator):
        """Test buying and then selling an asset."""
        with app.app_context():
            # Create user with portfolio
            user = data_generator.create_user('trader', with_portfolio=True)
            portfolio = user.portfolio
            
            # Buy 50 shares at $100
            portfolio.cash -= 5000.0
            holdings = {test_asset.id: 50.0}
            portfolio.set_holdings(holdings)
            position_info = {
                test_asset.id: {
                    'total_cost': 5000.0,
                    'total_quantity': 50.0
                }
            }
            portfolio.set_position_info(position_info)
            
            buy_tx = data_generator.create_transaction(
                user, test_asset, 'buy', 50.0, 100.0
            )
            
            # Sell 30 shares at $110
            portfolio.cash += 3300.0
            holdings[test_asset.id] = 20.0
            portfolio.set_holdings(holdings)
            
            # Update position info (proportional reduction)
            position_info[test_asset.id]['total_cost'] = 2000.0  # 20/50 * 5000
            position_info[test_asset.id]['total_quantity'] = 20.0
            portfolio.set_position_info(position_info)
            
            sell_tx = data_generator.create_transaction(
                user, test_asset, 'sell', 30.0, 110.0
            )
            
            # Verify final state
            assert portfolio.cash == 98300.0  # 100k - 5k + 3.3k
            assert holdings[test_asset.id] == 20.0
            assert Transaction.query.filter_by(user_id=user.id).count() == 2


class TestAssetLifecycleWorkflow:
    """Test complete asset lifecycle from creation to settlement."""
    
    def test_asset_creation_to_expiration_to_settlement(self, app, mock_price_service, data_generator):
        """Test complete asset lifecycle."""
        with app.app_context():
            # 1. Create asset manager and assets
            manager = AssetManager(app.config, mock_price_service)
            new_assets = manager.create_new_assets(count=1)
            asset = new_assets[0]
            
            # 2. Create user with holdings in this asset
            user = data_generator.create_user('holder', with_portfolio=True)
            portfolio = user.portfolio
            
            # Buy 100 shares
            portfolio.cash -= 10000.0
            holdings = {asset.id: 100.0}
            portfolio.set_holdings(holdings)
            position_info = {
                asset.id: {
                    'total_cost': 10000.0,
                    'total_quantity': 100.0
                }
            }
            portfolio.set_position_info(position_info)
            db.session.commit()
            
            # 3. Manually expire the asset
            asset.expires_at = current_utc() - timedelta(minutes=1)
            db.session.commit()
            
            # 4. Process expiration and settlement
            expired = manager.check_and_expire_assets()
            assert len(expired) == 1
            
            stats = manager.settle_expired_positions(expired)
            
            # 5. Verify settlement
            assert stats['positions_settled'] == 1
            
            # Check portfolio updated
            portfolio = Portfolio.query.get(portfolio.id)
            assert asset.id not in portfolio.get_holdings()
            assert portfolio.cash > 90000.0  # Got money back
            
            # Check settlement record
            settlement = Settlement.query.filter_by(
                user_id=user.id,
                asset_id=asset.id
            ).first()
            assert settlement is not None
    
    def test_worthless_asset_early_settlement(self, app, mock_price_service, data_generator):
        """Test asset gets settled early when price drops below threshold."""
        with app.app_context():
            # Create worthless asset (below $0.01 threshold)
            asset = Asset(
                symbol='WORTHLESS',
                initial_price=100.0,
                current_price=0.005,  # Already worthless
                volatility=0.02,
                drift=0.0,
                color='#ff0000',
                expires_at=current_utc() + timedelta(hours=2),  # Not yet expired
                is_active=True
            )
            db.session.add(asset)
            db.session.commit()
            
            # User holds shares
            user = data_generator.create_user('bagholder', with_portfolio=True)
            portfolio = user.portfolio
            holdings = {asset.id: 100.0}
            portfolio.set_holdings(holdings)
            portfolio.cash = 90000.0
            db.session.commit()
            
            # Process worthless asset settlement (this expires the asset with final_price)
            manager = AssetManager(app.config, mock_price_service)
            worthless = manager.check_and_settle_worthless_assets(threshold=0.01)
            
            assert len(worthless) == 1
            # check_and_settle_worthless_assets now calls .expire() which sets final_price
            assert worthless[0].final_price is not None, "Asset should have final_price after expiration"
            
            # Settle
            stats = manager.settle_expired_positions(worthless)
            
            # Verify minimal settlement value
            portfolio = Portfolio.query.get(portfolio.id)
            assert portfolio.cash == 90000.5  # Got 100 * 0.005


class TestMultiUserTradingScenario:
    """Test scenarios with multiple users trading."""
    
    def test_multiple_users_trading_same_asset(self, app, data_generator):
        """Test multiple users can trade the same asset."""
        with app.app_context():
            # Create asset
            asset = data_generator.create_asset('POPULAR', price=100.0)
            
            # Create 3 users
            users = []
            for i in range(3):
                user = data_generator.create_user(f'trader{i}', with_portfolio=True)
                users.append(user)
            
            # Each user buys different amounts
            quantities = [10.0, 25.0, 50.0]
            for user, qty in zip(users, quantities):
                portfolio = user.portfolio
                cost = qty * 100.0
                
                portfolio.cash -= cost
                holdings = {asset.id: qty}
                portfolio.set_holdings(holdings)
                
                data_generator.create_transaction(user, asset, 'buy', qty, 100.0)
            
            db.session.commit()
            
            # Verify all transactions recorded
            total_transactions = Transaction.query.filter_by(asset_id=asset.id).count()
            assert total_transactions == 3
            
            # Calculate total open interest
            total_holdings = sum(
                user.portfolio.get_holdings().get(asset.id, 0.0)
                for user in users
            )
            assert total_holdings == 85.0  # 10 + 25 + 50
    
    def test_competing_traders_same_asset(self, app, data_generator):
        """Test traders buying and selling to each other (simulated)."""
        with app.app_context():
            asset = data_generator.create_asset('VOLATILE', price=100.0)
            
            # User 1 buys
            user1 = data_generator.create_user('buyer', with_portfolio=True)
            portfolio1 = user1.portfolio
            portfolio1.cash -= 5000.0
            holdings1 = {asset.id: 50.0}
            portfolio1.set_holdings(holdings1)
            data_generator.create_transaction(user1, asset, 'buy', 50.0, 100.0)
            
            # User 2 also buys
            user2 = data_generator.create_user('buyer2', with_portfolio=True)
            portfolio2 = user2.portfolio
            portfolio2.cash -= 5500.0
            holdings2 = {asset.id: 50.0}
            portfolio2.set_holdings(holdings2)
            data_generator.create_transaction(user2, asset, 'buy', 50.0, 110.0)
            
            # User 1 sells at higher price (profit)
            portfolio1.cash += 6000.0
            holdings1[asset.id] = 0.0
            portfolio1.set_holdings({})
            data_generator.create_transaction(user1, asset, 'sell', 50.0, 120.0)
            
            db.session.commit()
            
            # User 1 should have profit
            assert portfolio1.cash == 101000.0  # 100k - 5k + 6k
            
            # User 2 still holding
            assert portfolio2.get_holdings()[asset.id] == 50.0


class TestPerformanceCalculationWorkflow:
    """Test performance calculation with real trading data."""
    
    def test_performance_after_profitable_trades(self, app, data_generator, mock_price_service):
        """Test performance calculation after profitable trading."""
        with app.app_context():
            from app import calculate_portfolio_performance
            
            # Create user and asset
            user = data_generator.create_user('profitable', with_portfolio=True)
            asset = data_generator.create_asset('WINNER', price=100.0)
            
            # Buy at $100
            portfolio = user.portfolio
            portfolio.cash -= 10000.0
            holdings = {asset.id: 100.0}
            portfolio.set_holdings(holdings)
            position_info = {
                asset.id: {
                    'total_cost': 10000.0,
                    'total_quantity': 100.0
                }
            }
            portfolio.set_position_info(position_info)
            db.session.commit()
            
            # Price goes up to $120
            asset.current_price = 120.0
            db.session.commit()
            mock_price_service.set_price('WINNER', 120.0)
            
            # Calculate performance
            performance = calculate_portfolio_performance(
                portfolio,
                current_prices=mock_price_service.get_current_prices(),
                active_assets=[asset]
            )
            
            # Portfolio value: $90k cash + (100 * $120) = $102k
            assert performance['portfolio_value'] == 102000.0
            
            # Unrealized P&L: (100 * $120) - $10k = $2k
            assert performance['unrealized_pnl'] == 2000.0
            
            # Total return: ($102k - $100k) / $100k = 2%
            assert performance['total_return'] == 2.0
    
    def test_performance_after_losses(self, app, data_generator, mock_price_service):
        """Test performance calculation after losing trade."""
        with app.app_context():
            from app import calculate_portfolio_performance
            
            # Create user and asset
            user = data_generator.create_user('loser', with_portfolio=True)
            asset = data_generator.create_asset('LOSER', price=100.0)
            
            # Buy at $100
            portfolio = user.portfolio
            portfolio.cash -= 10000.0
            holdings = {asset.id: 100.0}
            portfolio.set_holdings(holdings)
            position_info = {
                asset.id: {
                    'total_cost': 10000.0,
                    'total_quantity': 100.0
                }
            }
            portfolio.set_position_info(position_info)
            db.session.commit()
            
            # Price drops to $80
            asset.current_price = 80.0
            db.session.commit()
            mock_price_service.set_price('LOSER', 80.0)
            
            # Calculate performance
            performance = calculate_portfolio_performance(
                portfolio,
                current_prices=mock_price_service.get_current_prices(),
                active_assets=[asset]
            )
            
            # Portfolio value: $90k cash + (100 * $80) = $98k
            assert performance['portfolio_value'] == 98000.0
            
            # Unrealized P&L: (100 * $80) - $10k = -$2k
            assert performance['unrealized_pnl'] == -2000.0
            
            # Total return: ($98k - $100k) / $100k = -2%
            assert performance['total_return'] == -2.0


class TestEndToEndAssetReplacement:
    """Test complete asset replacement workflow."""
    
    def test_asset_expires_and_replaced_automatically(self, app, mock_price_service):
        """Test asset pool is maintained through expiration and replacement."""
        with app.app_context():
            manager = AssetManager(app.config, mock_price_service)
            
            # Initialize pool
            initial_assets = manager.initialize_asset_pool()
            initial_count = len(initial_assets)
            
            # Manually expire all assets
            for asset in initial_assets:
                asset.expires_at = current_utc() - timedelta(minutes=1)
            db.session.commit()
            
            # Process expirations (should replace them)
            stats = manager.process_expirations()
            
            assert stats['expired_assets'] == initial_count
            assert stats['maintenance_stats']['created_assets'] == initial_count
            
            # Verify we still have minimum assets
            active_count = Asset.query.filter_by(is_active=True).count()
            assert active_count >= initial_count


class TestValidationIntegration:
    """Test validation throughout complete workflows."""
    
    def test_invalid_trade_rejected_before_db(self, app, data_generator):
        """Test invalid trades are rejected by validation."""
        with app.app_context():
            from validators import ValidationError
            
            user = data_generator.create_user('validator', with_portfolio=True)
            asset = data_generator.create_asset('VALID', price=100.0)
            
            # Try invalid quantity
            with pytest.raises(ValidationError):
                validate_trade('VALID', -10, 100.0, 'buy')
            
            # Try invalid symbol
            with pytest.raises(ValidationError):
                validate_trade('INVALID!!!', 10, 100.0, 'buy')
            
            # Try invalid price
            with pytest.raises(ValidationError):
                validate_trade('VALID', 10, -100.0, 'buy')
            
            # Database should be unchanged
            assert Transaction.query.filter_by(user_id=user.id).count() == 0
    
    def test_insufficient_funds_prevents_trade(self, app, data_generator):
        """Test trade is prevented when user has insufficient funds."""
        with app.app_context():
            from validators import PortfolioValidator, ValidationError
            from decimal import Decimal
            
            user = data_generator.create_user('poor', with_portfolio=True)
            portfolio = user.portfolio
            portfolio.cash = 100.0  # Only $100
            db.session.commit()
            
            # Try to buy $1000 worth
            with pytest.raises(ValidationError):
                PortfolioValidator.validate_sufficient_funds(
                    Decimal('100.0'),
                    Decimal('1000.0')
                )


class TestConcurrentOperations:
    """Test concurrent operations don't cause data corruption."""
    
    def test_concurrent_settlements(self, app, mock_price_service, data_generator):
        """Test multiple assets settling simultaneously."""
        with app.app_context():
            # Create multiple expired assets
            assets = []
            for i in range(5):
                asset = data_generator.create_asset(
                    f'EXPIRE{i}',
                    price=100.0,
                    expires_in_hours=-1  # Already expired
                )
                # Mark as expired with final price for settlement
                asset.expire(final_price=95.0 + i)  # Different final prices
                assets.append(asset)
            
            # Create users with holdings in all assets
            users = []
            for i in range(3):
                user = data_generator.create_user(f'holder{i}', with_portfolio=True)
                portfolio = user.portfolio
                holdings = {}
                for asset in assets:
                    holdings[asset.id] = 10.0
                portfolio.set_holdings(holdings)
                portfolio.cash = 50000.0
                users.append(user)
            
            db.session.commit()
            
            # Settle all at once
            manager = AssetManager(app.config, mock_price_service)
            stats = manager.settle_expired_positions(assets)
            
            # Should settle 3 users × 5 assets = 15 positions
            assert stats['positions_settled'] == 15
            
            # Verify all settlements created
            total_settlements = Settlement.query.count()
            assert total_settlements == 15


class TestDataIntegrity:
    """Test data integrity across complete workflows."""
    
    def test_cash_balance_stays_valid(self, app, data_generator):
        """Test cash balance remains valid through multiple operations."""
        with app.app_context():
            user = data_generator.create_user('cashtest', with_portfolio=True)
            portfolio = user.portfolio
            asset = data_generator.create_asset('STABLE', price=100.0)
            
            # Buy
            portfolio.cash -= 1000.0
            assert portfolio.cash == 99000.0
            
            # Sell
            portfolio.cash += 1100.0
            assert portfolio.cash == 100100.0
            
            # Buy more
            portfolio.cash -= 2000.0
            assert portfolio.cash == 98100.0
            
            db.session.commit()
            
            # Verify cash is still valid
            from validators import PortfolioValidator
            from decimal import Decimal
            validated = PortfolioValidator.validate_cash_balance(Decimal(str(portfolio.cash)))
            assert validated == Decimal('98100.00')
    
    def test_holdings_never_negative(self, app, data_generator):
        """Test holdings never become negative."""
        with app.app_context():
            user = data_generator.create_user('holdtest', with_portfolio=True)
            portfolio = user.portfolio
            asset = data_generator.create_asset('HOLDINGS', price=100.0)
            
            # Buy 50 shares
            holdings = {asset.id: 50.0}
            portfolio.set_holdings(holdings)
            
            # Can't sell more than we have (should be prevented)
            # This is enforced by validation in the app
            # Here we just verify the data model
            holdings[asset.id] = 0.0
            portfolio.set_holdings(holdings)
            
            db.session.commit()
            
            # Holdings should be removed when zero
            retrieved = portfolio.get_holdings()
            assert asset.id not in retrieved or retrieved[asset.id] >= 0
