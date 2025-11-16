"""
Asset Manager - Manages lifecycle of expiring assets.
Handles creation, expiration, settlement, and automatic replacement.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from models import db, Asset, Settlement, Portfolio, Transaction, User, current_utc
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
        if bool(app_config.get('RANDOM_INITIAL_ASSET_PRICE', True)):
            self.initial_asset_price = None  # Randomized per asset
        else:
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
        query = Asset.query.filter(Asset.expires_at <= current_utc())
        
        if unsettled_only:
            query = query.filter_by(is_active=True)
        else:
            query = query.filter_by(is_active=False)
        
        return query.all()
    
    def get_worthless_assets(self, threshold: float = 0.01) -> List[Asset]:
        """Get active assets whose price has fallen below threshold.
        
        Args:
            threshold: Price threshold below which assets are considered worthless
        
        Returns:
            List of active Asset objects with price below threshold
        """
        return Asset.query.filter(
            Asset.is_active == True,
            Asset.current_price < threshold
        ).all()
    
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
    
    def check_and_settle_worthless_assets(self, threshold: float = 0.01) -> List[Asset]:
        """Check for assets that have fallen below price threshold and settle them early.
        
        Args:
            threshold: Price threshold below which assets are settled
        
        Returns:
            List of assets that were settled due to price dropping below threshold
        """
        worthless_assets = self.get_worthless_assets(threshold=threshold)
        
        if not worthless_assets:
            return []
        
        logger.info(f"Found {len(worthless_assets)} asset(s) below ${threshold:.2f} threshold")
        
        for asset in worthless_assets:
            logger.warning(f"Auto-settling {asset.symbol} - price ${asset.current_price:.4f} below ${threshold:.2f} threshold")
            # Expire with current (worthless) price as final price
            asset.expire(final_price=asset.current_price)
        
        if worthless_assets:
            db.session.commit()
        
        return worthless_assets
    
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
                
                if asset.id in holdings and holdings[asset.id] > 0:
                    quantity = holdings[asset.id]
                    settlement_value = quantity * asset.final_price
                    
                    # Create settlement record
                    settlement = Settlement(
                        user_id=portfolio.user_id,
                        asset_id=asset.id,
                        legacy_symbol=asset.symbol,
                        quantity=quantity,
                        settlement_price=asset.final_price,
                        settlement_value=settlement_value
                    )
                    db.session.add(settlement)
                    
                    # Return cash to user
                    portfolio.cash += settlement_value
                    
                    # Remove holding - DELETE the key entirely
                    holdings = portfolio.get_holdings()
                    if asset.id in holdings:
                        del holdings[asset.id]
                    portfolio.set_holdings(holdings)
                    
                    # Clear position info
                    position_info = portfolio.get_position_info()
                    if asset.id in position_info:
                        del position_info[asset.id]
                        portfolio.set_position_info(position_info)
                    
                    # Create settlement transaction for history
                    transaction = Transaction(
                        user_id=portfolio.user_id,
                        asset_id=asset.id,
                        legacy_symbol=asset.symbol,
                        timestamp=time.time() * 1000,
                        type='settlement',
                        quantity=quantity,
                        price=asset.final_price,
                        total_cost=settlement_value
                    )
                    db.session.add(transaction)
                    
                    # Store transaction data for emission after commit
                    transaction_data = {
                        'timestamp': transaction.timestamp,
                        'symbol': asset.symbol,
                        'type': transaction.type,
                        'quantity': transaction.quantity,
                        'price': transaction.price,
                        'total_cost': transaction.total_cost,  # Use total_cost not total!
                        'asset_id': transaction.asset_id,
                        'user_id': portfolio.user_id,
                        'color': asset.color
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
                minutes_to_expiry=None,  # Random
                exclude_symbols=self.config.get('EXCLUDED_SYMBOLS', None) 
            )
            db.session.add(asset)
            new_assets.append(asset)
            
            time_to_expiry = (asset.expires_at - current_utc()).total_seconds() / 60
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
                            'drift': asset.drift,
                            'history': [],
                            'last_update': None
                        }
                        logger.info(f"Registered {asset.symbol} with price service (volatility={asset.volatility:.4f}, drift={asset.drift:.6f})")
                except Exception as e:
                    logger.error(f"Error registering asset {asset.symbol} with price service: {e}")
        
        return new_assets
    
    def maintain_asset_pool(self) -> Dict[str, Any]:
        """Ensure minimum number of active assets by creating replacements.
        
        Returns:
            Dictionary with maintenance statistics
        """
        active_assets = self.get_active_assets()
        active_count = len(active_assets)
        
        stats = {
            'active_assets': active_count,
            'created_assets': 0,
            'active_symbols': [a.symbol for a in active_assets],
            'created_symbols': []
        }
        
        if active_count < self.min_active_assets:
            needed = self.min_active_assets - active_count
            logger.info(f"Creating {needed} new assets to maintain pool of {self.min_active_assets}")
            new_assets = self.create_new_assets(count=needed)
            stats['created_assets'] = len(new_assets)
            stats['created_symbols'] = [a.symbol for a in new_assets]
        
        return stats
    
    def initialize_asset_pool(self, count: Optional[int] = None) -> List[Asset]:
        """Initialize the asset pool with active assets.
        
        Args:
            count: Number of assets to create (uses MIN_ACTIVE_ASSETS if None)
        
        Returns:
            List of created assets
        """
        create_count = self.min_active_assets if count is None else count
        
        existing_active = self.get_active_assets()
        if existing_active:
            logger.info(f"Asset pool already has {len(existing_active)} active assets")
            return existing_active
        
        logger.info(f"Initializing asset pool with {create_count} assets")
        return self.create_new_assets(count=create_count)
    
    def cleanup_old_assets(self, days_old: int = 7) -> int:
        """Remove old expired assets from database to prevent bloat.
        
        Args:
            days_old: Remove assets expired this many days ago
        
        Returns:
            Number of assets removed
        """
        cutoff_date = current_utc() - timedelta(days=days_old)
        
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
    
    def process_expirations(self) -> Dict[str, Any]:
        """Main processing loop - check expirations, settle, create replacements.
        
        Returns:
            Dictionary with processing statistics
        """
        logger.info("Processing asset expirations...")
        
        # Step 1: Check and expire assets that have passed their expiration time
        expired_assets = self.check_and_expire_assets()
        
        # Step 1.5: Check and settle assets that have fallen below worthless threshold
        worthless_assets = self.check_and_settle_worthless_assets(threshold=0.01)
        
        # Combine both types of expired assets
        all_expired = list(expired_assets)
        if worthless_assets:
            all_expired.extend(worthless_assets)
            logger.info(f"Found {len(worthless_assets)} worthless asset(s) to settle early")
        
        # Build lists of symbols for each category
        expired_symbols = [asset.symbol for asset in expired_assets]
        worthless_symbols = [asset.symbol for asset in worthless_assets] if worthless_assets else []
        
        stats: Dict[str, Any] = {
            'expired_assets': len(expired_assets),
            'expired_symbols': expired_symbols,
            'worthless_assets': len(worthless_assets),
            'worthless_symbols': worthless_symbols,
            'total_settled': len(all_expired),
            'settlement_stats': {},
            'maintenance_stats': {}
        }
        
        # Step 2: Settle positions
        if all_expired:
            logger.info(f"Found {len(all_expired)} expired/worthless assets (time expired: {len(expired_assets)}, worthless: {len(worthless_assets)})")
            settlement_stats = self.settle_expired_positions(all_expired)
            stats['settlement_stats'] = settlement_stats
            
            # Emit settlement transactions AFTER database commit
            logger.info(f"Settlement stats: {settlement_stats}")
            transactions_value = settlement_stats.get('transactions')
            transactions: List[Dict[str, Any]] = transactions_value if isinstance(transactions_value, list) else []
            logger.info(f"Transactions to emit: {len(transactions)}")
            logger.info(f"SocketIO available: {self.socketio is not None}")
            
            if self.socketio and transactions:
                for transaction_data in transactions:
                    logger.info(f"Emitting transaction_added: {transaction_data}")
                    # Broadcast to all clients - frontend will filter by user
                    self.socketio.emit('transaction_added', transaction_data)
                    logger.info(f"Emitting global_transaction_update: {transaction_data}")
                    # Also broadcast to all clients for Time & Sales
                    public_transaction = {
                        'timestamp': int(transaction_data.get('timestamp', time.time() * 1000)),
                        'symbol': transaction_data.get('symbol'),
                        'type': transaction_data.get('type'),
                        'quantity': transaction_data.get('quantity'),
                        'price': transaction_data.get('price'),
                        'total_cost': transaction_data.get('total_cost'),
                        'user_id': transaction_data.get('user_id'),
                        'color': transaction_data.get('color')
                    }
                    self.socketio.emit('global_transaction_update', public_transaction)
                    logger.info(f"Broadcasted settlement transaction for {transaction_data['symbol']} user {transaction_data['user_id']}")
            else:
                if not self.socketio:
                    logger.error("SocketIO is None - cannot emit settlement transactions!")
                if not transactions:
                    logger.warning("No transactions to emit in settlement_stats")
            
            # Remove expired assets from price service
            if self.price_service and hasattr(self.price_service, 'fallback'):
                for asset in all_expired:
                    if asset.symbol in self.price_service.fallback.assets:
                        del self.price_service.fallback.assets[asset.symbol]
                        logger.info(f"Removed {asset.symbol} from price service")
        
        # Step 3: Maintain asset pool
        maintenance_stats = self.maintain_asset_pool()
        stats['maintenance_stats'] = maintenance_stats
        
        logger.info(f"Expiration processing complete: {stats}")
        return stats
    
    def get_asset_summary(self) -> Dict[str, Any]:
        """Get summary of current asset state.
        
        Returns:
            Dictionary with asset statistics
        """
        active_assets = self.get_active_assets()
        expired_unsettled = self.get_expired_assets(unsettled_only=True)
        expired_settled = self.get_expired_assets(unsettled_only=False)
        
        # Calculate average time to expiry for active assets
        ttl_seconds = [ttl.total_seconds() for ttl in (a.time_to_expiry() for a in active_assets) if ttl]
        avg_ttl = (sum(ttl_seconds) / len(ttl_seconds)) if ttl_seconds else 0
        
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
                    'hours_remaining': (ttl.total_seconds() / 3600) if (ttl := a.time_to_expiry()) else 0
                }
                for a in sorted(active_assets, key=lambda x: x.expires_at)[:5]
            ]
        }
