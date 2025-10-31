"""
Asset Manager - Manages lifecycle of expiring assets.
Handles creation, expiration, settlement, and automatic replacement.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from models import db, Asset, Settlement, Portfolio, Transaction, User
import time

logger = logging.getLogger(__name__)


class AssetManager:
    """Manages the lifecycle of assets with expiration dates."""
    
    def __init__(self, app_config, price_service=None, socketio=None):
        """Initialize the asset manager.
        
        Args:
            app_config: Flask app configuration
            price_service: Price service instance (optional)
            socketio: SocketIO instance for emitting events (optional)
        """
        self.config = app_config
        self.price_service = price_service
        self.socketio = socketio
        self.min_active_assets = app_config.get('MIN_ACTIVE_ASSETS', 16)
        self.initial_asset_price = app_config.get('INITIAL_ASSET_PRICE', 100.0)
    
    def get_active_assets(self) -> List[Asset]:
        """Get all currently active (non-expired) assets.
        
        Returns:
            List of active Asset objects
        """
        return Asset.query.filter_by(is_active=True).all()
    
    def get_expired_assets(self, unsettled_only=True) -> List[Asset]:
        """Get expired assets.
        
        Args:
            unsettled_only: If True, only return assets that haven't been settled
        
        Returns:
            List of expired Asset objects
        """
        query = Asset.query.filter(Asset.expires_at <= datetime.utcnow())
        
        if unsettled_only:
            query = query.filter_by(is_active=True)
        else:
            query = query.filter_by(is_active=False)
        
        return query.all()
    
    def check_and_expire_assets(self) -> List[Asset]:
        """Check for expired assets and mark them as expired.
        
        Returns:
            List of newly expired assets
        """
        expired_assets = self.get_expired_assets(unsettled_only=True)
        
        for asset in expired_assets:
            logger.info(f"Expiring asset {asset.symbol} at price {asset.current_price}")
            asset.expire(final_price=asset.current_price)
        
        if expired_assets:
            db.session.commit()
        
        return expired_assets
    
    def settle_expired_positions(self, expired_assets: List[Asset]) -> Dict[str, int]:
        """Settle all user positions in expired assets.
        
        Args:
            expired_assets: List of expired assets to settle
        
        Returns:
            Dictionary with settlement statistics
        """
        stats = {
            'assets_settled': 0,
            'positions_settled': 0,
            'total_value_settled': 0.0,
            'transactions': []  # Store transaction data for later emission
        }
        
        for asset in expired_assets:
            if not asset.final_price:
                logger.warning(f"Asset {asset.symbol} has no final price, skipping settlement")
                continue
            
            # Find all portfolios with holdings in this asset
            portfolios = Portfolio.query.all()
            
            for portfolio in portfolios:
                holdings = portfolio.get_holdings()
                
                if asset.symbol in holdings and holdings[asset.symbol] > 0:
                    quantity = holdings[asset.symbol]
                    settlement_value = quantity * asset.final_price
                    
                    # Create settlement record
                    settlement = Settlement(
                        user_id=portfolio.user_id,
                        asset_id=asset.id,
                        symbol=asset.symbol,
                        quantity=quantity,
                        settlement_price=asset.final_price,
                        settlement_value=settlement_value
                    )
                    db.session.add(settlement)
                    
                    # Return cash to user
                    portfolio.cash += settlement_value
                    
                    # Remove holding - DELETE the key entirely
                    holdings = portfolio.get_holdings()
                    if asset.symbol in holdings:
                        del holdings[asset.symbol]
                    portfolio.set_holdings(holdings)
                    
                    # Clear position info
                    position_info = portfolio.get_position_info()
                    if asset.symbol in position_info:
                        del position_info[asset.symbol]
                        portfolio.set_position_info(position_info)
                    
                    # Create settlement transaction for history
                    transaction = Transaction(
                        user_id=portfolio.user_id,
                        timestamp=time.time() * 1000,
                        symbol=asset.symbol,
                        type='settlement',
                        quantity=quantity,
                        price=asset.final_price,
                        total_cost=settlement_value
                    )
                    db.session.add(transaction)
                    
                    # Store transaction data for emission after commit
                    transaction_data = {
                        'timestamp': transaction.timestamp,
                        'symbol': transaction.symbol,
                        'type': transaction.type,
                        'quantity': transaction.quantity,
                        'price': transaction.price,
                        'total_cost': transaction.total_cost,  # Use total_cost not total!
                        'user_id': portfolio.user_id
                    }
                    stats['transactions'].append(transaction_data)
                    
                    logger.info(f"Settled {quantity} units of {asset.symbol} for user {portfolio.user_id} at ${asset.final_price:.2f} = ${settlement_value:.2f}")
                    
                    stats['positions_settled'] += 1
                    stats['total_value_settled'] += settlement_value
            
            stats['assets_settled'] += 1
        
        db.session.commit()
        return stats
    
    def create_new_assets(self, count: int = 1) -> List[Asset]:
        """Create new assets with random expiration dates.
        
        Args:
            count: Number of assets to create
        
        Returns:
            List of newly created Asset objects
        """
        new_assets = []
        
        for _ in range(count):
            asset = Asset.create_new_asset(
                initial_price=self.initial_asset_price,
                volatility=None,  # Random
                minutes_to_expiry=None  # Random 5-480 minutes (5 min to 8 hours)
            )
            db.session.add(asset)
            new_assets.append(asset)
            
            time_to_expiry = (asset.expires_at - datetime.utcnow()).total_seconds() / 60
            logger.info(f"Created new asset {asset.symbol} with volatility {asset.volatility:.4f}, expires in {time_to_expiry:.1f} minutes")
        
        db.session.commit()
        
        # Register new assets with price service if available
        if self.price_service:
            for asset in new_assets:
                try:
                    # Add to price service's fallback (always available)
                    if hasattr(self.price_service, 'fallback'):
                        self.price_service.fallback.assets[asset.symbol] = {
                            'price': asset.current_price,
                            'volatility': asset.volatility,
                            'history': [],
                            'last_update': None
                        }
                        logger.info(f"Registered {asset.symbol} with price service")
                except Exception as e:
                    logger.error(f"Error registering asset {asset.symbol} with price service: {e}")
        
        return new_assets
    
    def maintain_asset_pool(self) -> Dict[str, any]:
        """Ensure minimum number of active assets by creating replacements.
        
        Returns:
            Dictionary with maintenance statistics
        """
        active_assets = self.get_active_assets()
        active_count = len(active_assets)
        
        stats = {
            'active_assets': active_count,
            'created_assets': 0
        }
        
        if active_count < self.min_active_assets:
            needed = self.min_active_assets - active_count
            logger.info(f"Creating {needed} new assets to maintain pool of {self.min_active_assets}")
            new_assets = self.create_new_assets(count=needed)
            stats['created_assets'] = len(new_assets)
        
        return stats
    
    def initialize_asset_pool(self, count: Optional[int] = None) -> List[Asset]:
        """Initialize the asset pool with active assets.
        
        Args:
            count: Number of assets to create (uses MIN_ACTIVE_ASSETS if None)
        
        Returns:
            List of created assets
        """
        if count is None:
            count = self.min_active_assets
        
        existing_active = self.get_active_assets()
        if existing_active:
            logger.info(f"Asset pool already has {len(existing_active)} active assets")
            return existing_active
        
        logger.info(f"Initializing asset pool with {count} assets")
        return self.create_new_assets(count=count)
    
    def cleanup_old_assets(self, days_old: int = 30) -> int:
        """Remove old expired assets from database to prevent bloat.
        
        Args:
            days_old: Remove assets expired this many days ago
        
        Returns:
            Number of assets removed
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        old_assets = Asset.query.filter(
            Asset.is_active == False,
            Asset.settled_at < cutoff_date
        ).all()
        
        count = len(old_assets)
        
        for asset in old_assets:
            # Settlements will be cascade deleted
            db.session.delete(asset)
        
        db.session.commit()
        
        if count > 0:
            logger.info(f"Cleaned up {count} old assets")
        
        return count
    
    def process_expirations(self) -> Dict[str, any]:
        """Main processing loop - check expirations, settle, create replacements.
        
        Returns:
            Dictionary with processing statistics
        """
        logger.info("Processing asset expirations...")
        
        # Step 1: Check and expire assets
        expired_assets = self.check_and_expire_assets()
        
        stats = {
            'expired_assets': len(expired_assets),
            'settlement_stats': {},
            'maintenance_stats': {}
        }
        
        # Step 2: Settle positions
        if expired_assets:
            logger.info(f"Found {len(expired_assets)} expired assets")
            settlement_stats = self.settle_expired_positions(expired_assets)
            stats['settlement_stats'] = settlement_stats
            
            # Emit settlement transactions AFTER database commit
            logger.info(f"Settlement stats: {settlement_stats}")
            logger.info(f"Transactions to emit: {len(settlement_stats.get('transactions', []))}")
            logger.info(f"SocketIO available: {self.socketio is not None}")
            
            if self.socketio and settlement_stats.get('transactions'):
                for transaction_data in settlement_stats['transactions']:
                    logger.info(f"Emitting transaction_added: {transaction_data}")
                    # Broadcast to all clients - frontend will filter by user
                    self.socketio.emit('transaction_added', transaction_data, broadcast=True)
                    logger.info(f"Emitting global_transaction_update: {transaction_data}")
                    # Also broadcast to all clients for Time & Sales
                    self.socketio.emit('global_transaction_update', transaction_data)
                    logger.info(f"Broadcasted settlement transaction for {transaction_data['symbol']} user {transaction_data['user_id']}")
            else:
                if not self.socketio:
                    logger.error("SocketIO is None - cannot emit settlement transactions!")
                if not settlement_stats.get('transactions'):
                    logger.warning("No transactions to emit in settlement_stats")
            
            # Remove expired assets from price service
            if self.price_service and hasattr(self.price_service, 'fallback'):
                for asset in expired_assets:
                    if asset.symbol in self.price_service.fallback.assets:
                        del self.price_service.fallback.assets[asset.symbol]
                        logger.info(f"Removed {asset.symbol} from price service")
        
        # Step 3: Maintain asset pool
        maintenance_stats = self.maintain_asset_pool()
        stats['maintenance_stats'] = maintenance_stats
        
        logger.info(f"Expiration processing complete: {stats}")
        return stats
    
    def get_asset_summary(self) -> Dict[str, any]:
        """Get summary of current asset state.
        
        Returns:
            Dictionary with asset statistics
        """
        active_assets = self.get_active_assets()
        expired_unsettled = self.get_expired_assets(unsettled_only=True)
        expired_settled = self.get_expired_assets(unsettled_only=False)
        
        # Calculate average time to expiry for active assets
        if active_assets:
            avg_ttl = sum(a.time_to_expiry().total_seconds() for a in active_assets) / len(active_assets)
        else:
            avg_ttl = 0
        
        return {
            'active_count': len(active_assets),
            'expired_unsettled_count': len(expired_unsettled),
            'expired_settled_count': len(expired_settled),
            'average_ttl_hours': avg_ttl / 3600,
            'active_symbols': [a.symbol for a in active_assets],
            'expiring_soon': [
                {
                    'symbol': a.symbol,
                    'expires_at': a.expires_at.isoformat(),
                    'hours_remaining': a.time_to_expiry().total_seconds() / 3600
                }
                for a in sorted(active_assets, key=lambda x: x.expires_at)[:5]
            ]
        }
