"""
Input validation utilities for Martingale trading platform.

This module provides comprehensive validation for all user inputs to prevent:
- Financial exploits (negative values, precision attacks)
- SQL injection and XSS attacks
- Business logic bypasses
- Data integrity issues (NaN, infinity, extreme values)
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from typing import Optional, Tuple
import re
import math


class ValidationError(Exception):
    """Custom exception for validation failures."""
    pass


class TradeValidator:
    """Validates trading operations."""
    
    # Configuration constants
    MAX_QUANTITY = Decimal('1000000000')  # 1 billion max
    MIN_QUANTITY = Decimal('0.00000001')  # 8 decimal places minimum
    MAX_PRICE = Decimal('1000000000')  # 1 billion max
    MIN_PRICE = Decimal('0.01')  # 1 cent minimum
    MAX_TRADE_VALUE = Decimal('10000000000')  # 10 billion max
    DECIMAL_PLACES = 8  # Maximum precision
    
    @staticmethod
    def validate_quantity(quantity: any, allow_zero: bool = False) -> Decimal:
        """Validate and sanitize trade quantity.
        
        Args:
            quantity: Raw quantity input (can be int, float, str, Decimal)
            allow_zero: Whether to allow zero quantity (for position checks)
        
        Returns:
            Validated Decimal quantity
            
        Raises:
            ValidationError: If quantity is invalid
        """
        # Type conversion and validation
        try:
            if isinstance(quantity, str):
                quantity = quantity.strip()
            qty = Decimal(str(quantity))
        except (InvalidOperation, ValueError, TypeError) as e:
            raise ValidationError(f"Invalid quantity format: {quantity}")
        
        # Check for special float values
        if not qty.is_finite():
            raise ValidationError("Quantity cannot be infinity or NaN")
        
        # Check sign
        if qty < 0:
            raise ValidationError("Quantity cannot be negative")
        
        # Check zero
        if qty == 0 and not allow_zero:
            raise ValidationError("Quantity must be greater than zero")
        
        # Check minimum (if not zero)
        if qty > 0 and qty < TradeValidator.MIN_QUANTITY:
            raise ValidationError(
                f"Quantity must be at least {TradeValidator.MIN_QUANTITY}"
            )
        
        # Check maximum
        if qty > TradeValidator.MAX_QUANTITY:
            raise ValidationError(
                f"Quantity cannot exceed {TradeValidator.MAX_QUANTITY}"
            )
        
        # Round to maximum decimal places
        qty = qty.quantize(
            Decimal('0.00000001'),
            rounding=ROUND_HALF_EVEN
        )
        
        return qty
    
    @staticmethod
    def validate_price(price: any) -> Decimal:
        """Validate and sanitize asset price.
        
        Args:
            price: Raw price input
            
        Returns:
            Validated Decimal price
            
        Raises:
            ValidationError: If price is invalid
        """
        try:
            if isinstance(price, str):
                price = price.strip()
            prc = Decimal(str(price))
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError(f"Invalid price format: {price}")
        
        # Check for special values
        if not prc.is_finite():
            raise ValidationError("Price cannot be infinity or NaN")
        
        # Check minimum (prices must be positive)
        if prc < TradeValidator.MIN_PRICE:
            raise ValidationError(
                f"Price must be at least {TradeValidator.MIN_PRICE}"
            )
        
        # Check maximum
        if prc > TradeValidator.MAX_PRICE:
            raise ValidationError(
                f"Price cannot exceed {TradeValidator.MAX_PRICE}"
            )
        
        # Round to maximum decimal places
        prc = prc.quantize(
            Decimal('0.00000001'),
            rounding=ROUND_HALF_EVEN
        )
        
        return prc
    
    @staticmethod
    def validate_trade_value(quantity: Decimal, price: Decimal) -> Decimal:
        """Validate total trade value.
        
        Args:
            quantity: Already validated quantity
            price: Already validated price
            
        Returns:
            Total trade value
            
        Raises:
            ValidationError: If trade value exceeds limits
        """
        total = (quantity * price).quantize(
            Decimal('0.00000001'),
            rounding=ROUND_HALF_EVEN
        )
        
        if total > TradeValidator.MAX_TRADE_VALUE:
            raise ValidationError(
                f"Trade value ${total} exceeds maximum of ${TradeValidator.MAX_TRADE_VALUE}"
            )
        
        return total
    
    @staticmethod
    def validate_trade_type(trade_type: str) -> str:
        """Validate trade type.
        
        Args:
            trade_type: Trade type string
            
        Returns:
            Normalized trade type ('buy' or 'sell')
            
        Raises:
            ValidationError: If trade type is invalid
        """
        if not isinstance(trade_type, str):
            raise ValidationError("Trade type must be a string")
        
        trade_type = trade_type.lower().strip()
        
        if trade_type not in ['buy', 'sell']:
            raise ValidationError(
                f"Trade type must be 'buy' or 'sell', got '{trade_type}'"
            )
        
        return trade_type


class SymbolValidator:
    """Validates asset symbols."""
    
    # Symbol must be 1-10 uppercase letters
    SYMBOL_PATTERN = re.compile(r'^[A-Z]{1,10}$')
    
    # Reserved symbols that cannot be traded
    RESERVED_SYMBOLS = {'NULL', 'NONE', 'CASH', 'USD', 'SYSTEM', 'ADMIN', 'TEST'}
    
    @staticmethod
    def validate_symbol(symbol: str) -> str:
        """Validate and sanitize asset symbol.
        
        Args:
            symbol: Raw symbol input
            
        Returns:
            Validated uppercase symbol
            
        Raises:
            ValidationError: If symbol is invalid
        """
        if not isinstance(symbol, str):
            raise ValidationError("Symbol must be a string")
        
        # Strip whitespace and convert to uppercase
        symbol = symbol.strip().upper()
        
        # Check length
        if len(symbol) == 0:
            raise ValidationError("Symbol cannot be empty")
        
        if len(symbol) > 10:
            raise ValidationError("Symbol cannot exceed 10 characters")
        
        # Check pattern (only uppercase letters)
        if not SymbolValidator.SYMBOL_PATTERN.match(symbol):
            raise ValidationError(
                "Symbol can only contain uppercase letters (A-Z)"
            )
        
        # Check reserved
        if symbol in SymbolValidator.RESERVED_SYMBOLS:
            raise ValidationError(f"Symbol '{symbol}' is reserved and cannot be traded")
        
        return symbol


class PortfolioValidator:
    """Validates portfolio operations."""
    
    MAX_CASH = Decimal('100000000000')  # 100 billion max
    MIN_CASH = Decimal('0')  # Cannot go negative
    
    @staticmethod
    def validate_cash_balance(balance: any) -> Decimal:
        """Validate cash balance.
        
        Args:
            balance: Raw balance input
            
        Returns:
            Validated Decimal balance
            
        Raises:
            ValidationError: If balance is invalid
        """
        try:
            if isinstance(balance, str):
                balance = balance.strip()
            bal = Decimal(str(balance))
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError(f"Invalid balance format: {balance}")
        
        if not bal.is_finite():
            raise ValidationError("Balance cannot be infinity or NaN")
        
        if bal < PortfolioValidator.MIN_CASH:
            raise ValidationError("Cash balance cannot be negative")
        
        if bal > PortfolioValidator.MAX_CASH:
            raise ValidationError(
                f"Cash balance cannot exceed {PortfolioValidator.MAX_CASH}"
            )
        
        # Round to 2 decimal places for currency
        bal = bal.quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_EVEN
        )
        
        return bal
    
    @staticmethod
    def validate_sufficient_funds(balance: Decimal, required: Decimal) -> bool:
        """Check if portfolio has sufficient funds.
        
        Args:
            balance: Current cash balance
            required: Required amount
            
        Returns:
            True if sufficient funds
            
        Raises:
            ValidationError: If insufficient funds
        """
        if balance < required:
            raise ValidationError(
                f"Insufficient funds: have ${balance}, need ${required}"
            )
        return True
    
    @staticmethod
    def validate_sufficient_holdings(quantity_held: Decimal, quantity_required: Decimal) -> bool:
        """Check if portfolio has sufficient holdings to sell.
        
        Args:
            quantity_held: Current quantity held
            quantity_required: Required quantity
            
        Returns:
            True if sufficient holdings
            
        Raises:
            ValidationError: If insufficient holdings
        """
        if quantity_held < quantity_required:
            raise ValidationError(
                f"Insufficient holdings: have {quantity_held}, need {quantity_required}"
            )
        return True


class QueryValidator:
    """Validates API query parameters."""
    
    @staticmethod
    def validate_limit(limit: any, max_limit: int = 1000, default: int = 100) -> int:
        """Validate pagination limit parameter.
        
        Args:
            limit: Raw limit input
            max_limit: Maximum allowed limit
            default: Default value if limit is None
            
        Returns:
            Validated integer limit
        """
        if limit is None:
            return default
        
        try:
            limit = int(limit)
        except (ValueError, TypeError):
            return default
        
        # Clamp to valid range
        if limit < 1:
            return 1
        if limit > max_limit:
            return max_limit
        
        return limit
    
    @staticmethod
    def validate_offset(offset: any, default: int = 0) -> int:
        """Validate pagination offset parameter.
        
        Args:
            offset: Raw offset input
            default: Default value if offset is None
            
        Returns:
            Validated integer offset
        """
        if offset is None:
            return default
        
        try:
            offset = int(offset)
        except (ValueError, TypeError):
            return default
        
        # Offset must be non-negative
        if offset < 0:
            return 0
        
        return offset
    
    @staticmethod
    def validate_user_id(user_id: any) -> int:
        """Validate user ID parameter.
        
        Args:
            user_id: Raw user ID input
            
        Returns:
            Validated integer user ID
            
        Raises:
            ValidationError: If user ID is invalid
        """
        try:
            uid = int(user_id)
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid user ID: {user_id}")
        
        if uid < 1:
            raise ValidationError("User ID must be positive")
        
        return uid


# Convenience function for validating complete trades
def validate_trade(symbol: str, quantity: any, price: any, trade_type: str) -> Tuple[str, Decimal, Decimal, str]:
    """Validate all components of a trade operation.
    
    Args:
        symbol: Asset symbol
        quantity: Trade quantity
        price: Asset price
        trade_type: 'buy' or 'sell'
        
    Returns:
        Tuple of (validated_symbol, validated_quantity, validated_price, validated_type)
        
    Raises:
        ValidationError: If any component is invalid
    """
    validated_symbol = SymbolValidator.validate_symbol(symbol)
    validated_quantity = TradeValidator.validate_quantity(quantity)
    validated_price = TradeValidator.validate_price(price)
    validated_type = TradeValidator.validate_trade_type(trade_type)
    
    # Validate total trade value
    TradeValidator.validate_trade_value(validated_quantity, validated_price)
    
    return validated_symbol, validated_quantity, validated_price, validated_type


# Utility functions for safe float-to-decimal conversion
def safe_decimal(value: any, default: Decimal = Decimal('0')) -> Decimal:
    """Safely convert any value to Decimal, returning default on error.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Decimal value or default
    """
    try:
        if isinstance(value, str):
            value = value.strip()
        dec = Decimal(str(value))
        if dec.is_finite():
            return dec
    except (InvalidOperation, ValueError, TypeError):
        pass
    return default


def safe_float_to_decimal(value: float, places: int = 8) -> Decimal:
    """Convert float to Decimal with specific precision.
    
    Args:
        value: Float value to convert
        places: Number of decimal places
        
    Returns:
        Decimal value rounded to specified places
    """
    if not math.isfinite(value):
        return Decimal('0')
    
    dec = Decimal(str(value))
    quantizer = Decimal('0.1') ** places
    return dec.quantize(quantizer, rounding=ROUND_HALF_EVEN)
