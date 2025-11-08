"""
Comprehensive test suite for validators.py module.

Tests edge cases, boundary conditions, malicious inputs, and Decimal precision.
"""

import unittest
import math
from decimal import Decimal, InvalidOperation
from validators import (
    ValidationError,
    TradeValidator,
    SymbolValidator,
    PortfolioValidator,
    QueryValidator,
    validate_trade,
    safe_decimal,
    safe_float_to_decimal
)


class TestTradeValidator(unittest.TestCase):
    """Test TradeValidator class methods."""
    
    def test_validate_quantity_valid(self):
        """Test valid quantity inputs."""
        self.assertEqual(TradeValidator.validate_quantity(1), Decimal('1'))
        self.assertEqual(TradeValidator.validate_quantity(0.5), Decimal('0.5'))
        self.assertEqual(TradeValidator.validate_quantity('100.12345678'), Decimal('100.12345678'))
        self.assertEqual(TradeValidator.validate_quantity(Decimal('50')), Decimal('50'))
    
    def test_validate_quantity_minimum(self):
        """Test minimum quantity boundary."""
        # Exactly at minimum
        min_qty = TradeValidator.validate_quantity(0.00000001)
        self.assertEqual(min_qty, Decimal('0.00000001'))
        
        # Below minimum should fail
        with self.assertRaises(ValidationError) as ctx:
            TradeValidator.validate_quantity(0.000000001)
        self.assertIn('at least', str(ctx.exception).lower())
    
    def test_validate_quantity_maximum(self):
        """Test maximum quantity boundary."""
        # Just under maximum
        max_qty = TradeValidator.validate_quantity(999999999)
        self.assertEqual(max_qty, Decimal('999999999'))
        
        # Over maximum should fail
        with self.assertRaises(ValidationError) as ctx:
            TradeValidator.validate_quantity(1000000001)
        self.assertIn('cannot exceed', str(ctx.exception).lower())
    
    def test_validate_quantity_zero(self):
        """Test zero quantity is rejected."""
        with self.assertRaises(ValidationError) as ctx:
            TradeValidator.validate_quantity(0)
        self.assertIn('greater than zero', str(ctx.exception).lower())
    
    def test_validate_quantity_negative(self):
        """Test negative quantity is rejected."""
        with self.assertRaises(ValidationError) as ctx:
            TradeValidator.validate_quantity(-1)
        self.assertIn('cannot be negative', str(ctx.exception).lower())
        
        with self.assertRaises(ValidationError):
            TradeValidator.validate_quantity(-0.5)
    
    def test_validate_quantity_infinity(self):
        """Test infinity is rejected."""
        with self.assertRaises(ValidationError) as ctx:
            TradeValidator.validate_quantity(float('inf'))
        self.assertIn('infinity', str(ctx.exception).lower())
        
        with self.assertRaises(ValidationError):
            TradeValidator.validate_quantity(float('-inf'))
    
    def test_validate_quantity_nan(self):
        """Test NaN is rejected."""
        with self.assertRaises(ValidationError) as ctx:
            TradeValidator.validate_quantity(float('nan'))
        self.assertIn('nan', str(ctx.exception).lower())
    
    def test_validate_quantity_precision(self):
        """Test decimal precision is enforced (8 decimal places)."""
        # Exactly 8 decimal places - should work
        qty = TradeValidator.validate_quantity(1.12345678)
        self.assertEqual(qty, Decimal('1.12345678'))
        
        # More than 8 decimal places - should be rounded
        qty = TradeValidator.validate_quantity(1.123456789)
        self.assertEqual(qty, Decimal('1.12345679'))  # Rounded
    
    def test_validate_quantity_invalid_types(self):
        """Test invalid types are rejected."""
        with self.assertRaises(ValidationError):
            TradeValidator.validate_quantity(None)
        
        with self.assertRaises(ValidationError):
            TradeValidator.validate_quantity('invalid')
        
        with self.assertRaises(ValidationError):
            TradeValidator.validate_quantity([1, 2, 3])
    
    def test_validate_price_valid(self):
        """Test valid price inputs."""
        self.assertEqual(TradeValidator.validate_price(1.5), Decimal('1.5'))
        self.assertEqual(TradeValidator.validate_price('100.50'), Decimal('100.50'))
        self.assertEqual(TradeValidator.validate_price(Decimal('99.99')), Decimal('99.99'))
    
    def test_validate_price_minimum(self):
        """Test minimum price boundary."""
        # At minimum
        price = TradeValidator.validate_price(0.01)
        self.assertEqual(price, Decimal('0.01'))
        
        # Below minimum should fail
        with self.assertRaises(ValidationError) as ctx:
            TradeValidator.validate_price(0.001)
        self.assertIn('at least', str(ctx.exception).lower())
    
    def test_validate_price_maximum(self):
        """Test maximum price boundary."""
        # Under maximum
        price = TradeValidator.validate_price(999999999)
        self.assertEqual(price, Decimal('999999999'))
        
        # Over maximum should fail
        with self.assertRaises(ValidationError) as ctx:
            TradeValidator.validate_price(1000000001)
        self.assertIn('cannot exceed', str(ctx.exception).lower())
    
    def test_validate_price_zero_negative(self):
        """Test zero and negative prices are rejected."""
        with self.assertRaises(ValidationError):
            TradeValidator.validate_price(0)
        
        with self.assertRaises(ValidationError):
            TradeValidator.validate_price(-5)
    
    def test_validate_price_special_values(self):
        """Test infinity and NaN are rejected."""
        with self.assertRaises(ValidationError):
            TradeValidator.validate_price(float('inf'))
        
        with self.assertRaises(ValidationError):
            TradeValidator.validate_price(float('nan'))
    
    def test_validate_trade_value_valid(self):
        """Test valid trade value validation."""
        quantity = Decimal('10')
        price = Decimal('100.50')
        # trade_value = 10 * 100.50 = 1005
        TradeValidator.validate_trade_value(quantity, price)  # Should not raise
    
    def test_validate_trade_value_maximum(self):
        """Test maximum trade value boundary."""
        # Just under max
        quantity = Decimal('10000')
        price = Decimal('999999')
        TradeValidator.validate_trade_value(quantity, price)  # Should work
        
        # Over max
        quantity = Decimal('100000')
        price = Decimal('100001')
        with self.assertRaises(ValidationError) as ctx:
            TradeValidator.validate_trade_value(quantity, price)
        self.assertIn('exceeds maximum', str(ctx.exception).lower())
    
    def test_validate_trade_type_valid(self):
        """Test valid trade types."""
        self.assertEqual(TradeValidator.validate_trade_type('buy'), 'buy')
        self.assertEqual(TradeValidator.validate_trade_type('sell'), 'sell')
        self.assertEqual(TradeValidator.validate_trade_type('BUY'), 'buy')
        self.assertEqual(TradeValidator.validate_trade_type('SELL'), 'sell')
    
    def test_validate_trade_type_invalid(self):
        """Test invalid trade types are rejected."""
        with self.assertRaises(ValidationError) as ctx:
            TradeValidator.validate_trade_type('invalid')
        self.assertIn('must be', str(ctx.exception).lower())
        
        with self.assertRaises(ValidationError):
            TradeValidator.validate_trade_type('')
        
        with self.assertRaises(ValidationError):
            TradeValidator.validate_trade_type(None)


class TestSymbolValidator(unittest.TestCase):
    """Test SymbolValidator class methods."""
    
    def test_validate_symbol_valid(self):
        """Test valid symbol inputs."""
        self.assertEqual(SymbolValidator.validate_symbol('AAPL'), 'AAPL')
        self.assertEqual(SymbolValidator.validate_symbol('TSLA'), 'TSLA')
        self.assertEqual(SymbolValidator.validate_symbol('BTC'), 'BTC')
        self.assertEqual(SymbolValidator.validate_symbol('a'), 'A')  # Single char
    
    def test_validate_symbol_case_normalization(self):
        """Test lowercase is converted to uppercase."""
        self.assertEqual(SymbolValidator.validate_symbol('aapl'), 'AAPL')
        self.assertEqual(SymbolValidator.validate_symbol('TsLa'), 'TSLA')
        self.assertEqual(SymbolValidator.validate_symbol('btc'), 'BTC')
    
    def test_validate_symbol_length_boundaries(self):
        """Test symbol length validation."""
        # 1 character - valid
        self.assertEqual(SymbolValidator.validate_symbol('A'), 'A')
        
        # 10 characters - valid
        self.assertEqual(SymbolValidator.validate_symbol('ABCDEFGHIJ'), 'ABCDEFGHIJ')
        
        # Empty - invalid
        with self.assertRaises(ValidationError) as ctx:
            SymbolValidator.validate_symbol('')
        self.assertIn('empty', str(ctx.exception).lower())
        
        # 11 characters - invalid
        with self.assertRaises(ValidationError) as ctx:
            SymbolValidator.validate_symbol('ABCDEFGHIJK')
        self.assertIn('cannot exceed', str(ctx.exception).lower())
    
    def test_validate_symbol_pattern_validation(self):
        """Test symbol pattern (only letters A-Z)."""
        # Invalid characters
        with self.assertRaises(ValidationError) as ctx:
            SymbolValidator.validate_symbol('AAPL123')
        self.assertIn('letters', str(ctx.exception).lower())
        
        with self.assertRaises(ValidationError):
            SymbolValidator.validate_symbol('AAPL-USD')
        
        with self.assertRaises(ValidationError):
            SymbolValidator.validate_symbol('AAPL.US')
        
        with self.assertRaises(ValidationError):
            SymbolValidator.validate_symbol('AAP L')  # Space
    
    def test_validate_symbol_sql_injection_attempts(self):
        """Test SQL injection attempts are blocked."""
        with self.assertRaises(ValidationError):
            SymbolValidator.validate_symbol("'; DROP TABLE assets;--")
        
        with self.assertRaises(ValidationError):
            SymbolValidator.validate_symbol("' OR '1'='1")
        
        with self.assertRaises(ValidationError):
            SymbolValidator.validate_symbol("1=1")
    
    def test_validate_symbol_reserved_words(self):
        """Test reserved words are rejected."""
        # Testing actual reserved symbols from validators.py
        reserved_words = ['NULL', 'NONE', 'CASH', 'USD', 'SYSTEM', 'ADMIN', 'TEST']
        for word in reserved_words:
            with self.assertRaises(ValidationError) as ctx:
                SymbolValidator.validate_symbol(word)
            self.assertIn('reserved', str(ctx.exception).lower())
    
    def test_validate_symbol_null_none(self):
        """Test None and null-like inputs are rejected."""
        with self.assertRaises(ValidationError):
            SymbolValidator.validate_symbol(None)
        
        with self.assertRaises(ValidationError):
            SymbolValidator.validate_symbol('NULL')
        
        with self.assertRaises(ValidationError):
            SymbolValidator.validate_symbol('null')


class TestPortfolioValidator(unittest.TestCase):
    """Test PortfolioValidator class methods."""
    
    def test_validate_cash_balance_valid(self):
        """Test valid cash balance inputs."""
        PortfolioValidator.validate_cash_balance(Decimal('100000'))
        PortfolioValidator.validate_cash_balance(Decimal('0'))
        PortfolioValidator.validate_cash_balance(Decimal('50000.50'))
    
    def test_validate_cash_balance_negative(self):
        """Test negative cash balance is rejected."""
        with self.assertRaises(ValidationError) as ctx:
            PortfolioValidator.validate_cash_balance(Decimal('-100'))
        self.assertIn('cannot be negative', str(ctx.exception).lower())
    
    def test_validate_cash_balance_maximum(self):
        """Test maximum cash balance boundary."""
        # Just under max
        PortfolioValidator.validate_cash_balance(Decimal('99999999999'))
        
        # Over max
        with self.assertRaises(ValidationError) as ctx:
            PortfolioValidator.validate_cash_balance(Decimal('100000000001'))
        self.assertIn('cannot exceed', str(ctx.exception).lower())
    
    def test_validate_cash_balance_special_values(self):
        """Test infinity and NaN are rejected."""
        with self.assertRaises(ValidationError):
            PortfolioValidator.validate_cash_balance(Decimal('Infinity'))
        
        with self.assertRaises(ValidationError):
            PortfolioValidator.validate_cash_balance(Decimal('NaN'))
    
    def test_validate_sufficient_funds_valid(self):
        """Test sufficient funds validation."""
        # Exact amount
        PortfolioValidator.validate_sufficient_funds(Decimal('1000'), Decimal('1000'))
        
        # More than enough
        PortfolioValidator.validate_sufficient_funds(Decimal('2000'), Decimal('1000'))
    
    def test_validate_sufficient_funds_insufficient(self):
        """Test insufficient funds is detected."""
        with self.assertRaises(ValidationError) as ctx:
            PortfolioValidator.validate_sufficient_funds(Decimal('500'), Decimal('1000'))
        self.assertIn('insufficient', str(ctx.exception).lower())
    
    def test_validate_sufficient_holdings_valid(self):
        """Test sufficient holdings validation."""
        # Exact amount
        PortfolioValidator.validate_sufficient_holdings(Decimal('10'), Decimal('10'))
        
        # More than enough
        PortfolioValidator.validate_sufficient_holdings(Decimal('20'), Decimal('10'))
    
    def test_validate_sufficient_holdings_insufficient(self):
        """Test insufficient holdings is detected."""
        with self.assertRaises(ValidationError) as ctx:
            PortfolioValidator.validate_sufficient_holdings(Decimal('5'), Decimal('10'))
        self.assertIn('insufficient', str(ctx.exception).lower())


class TestQueryValidator(unittest.TestCase):
    """Test QueryValidator class methods."""
    
    def test_validate_limit_valid(self):
        """Test valid limit inputs."""
        self.assertEqual(QueryValidator.validate_limit(50), 50)
        self.assertEqual(QueryValidator.validate_limit(100), 100)
        self.assertEqual(QueryValidator.validate_limit('200'), 200)
    
    def test_validate_limit_none_returns_default(self):
        """Test None returns default value."""
        self.assertEqual(QueryValidator.validate_limit(None), 100)
        self.assertEqual(QueryValidator.validate_limit(None, default=50), 50)
    
    def test_validate_limit_maximum(self):
        """Test maximum limit is enforced."""
        # Over max should be clamped
        self.assertEqual(QueryValidator.validate_limit(5000, max_limit=1000), 1000)
        self.assertEqual(QueryValidator.validate_limit(9999, max_limit=500), 500)
    
    def test_validate_limit_minimum(self):
        """Test minimum limit is enforced."""
        # Below 1 should be clamped to 1
        self.assertEqual(QueryValidator.validate_limit(0), 1)
        self.assertEqual(QueryValidator.validate_limit(-10), 1)
    
    def test_validate_limit_invalid_types(self):
        """Test invalid types return default."""
        self.assertEqual(QueryValidator.validate_limit('invalid'), 100)
        self.assertEqual(QueryValidator.validate_limit([1, 2, 3]), 100)
    
    def test_validate_offset_valid(self):
        """Test valid offset inputs."""
        self.assertEqual(QueryValidator.validate_offset(0), 0)
        self.assertEqual(QueryValidator.validate_offset(50), 50)
        self.assertEqual(QueryValidator.validate_offset('100'), 100)
    
    def test_validate_offset_none_returns_default(self):
        """Test None returns default value."""
        self.assertEqual(QueryValidator.validate_offset(None), 0)
        self.assertEqual(QueryValidator.validate_offset(None, default=10), 10)
    
    def test_validate_offset_negative(self):
        """Test negative offsets are clamped to 0."""
        self.assertEqual(QueryValidator.validate_offset(-10), 0)
        self.assertEqual(QueryValidator.validate_offset(-1), 0)
    
    def test_validate_offset_invalid_types(self):
        """Test invalid types return default."""
        self.assertEqual(QueryValidator.validate_offset('invalid'), 0)
        self.assertEqual(QueryValidator.validate_offset([1, 2, 3]), 0)
    
    def test_validate_user_id_valid(self):
        """Test valid user ID inputs."""
        self.assertEqual(QueryValidator.validate_user_id(1), 1)
        self.assertEqual(QueryValidator.validate_user_id('123'), 123)
        self.assertEqual(QueryValidator.validate_user_id(999999), 999999)
    
    def test_validate_user_id_invalid(self):
        """Test invalid user IDs are rejected."""
        with self.assertRaises(ValidationError):
            QueryValidator.validate_user_id(0)
        
        with self.assertRaises(ValidationError):
            QueryValidator.validate_user_id(-1)
        
        with self.assertRaises(ValidationError):
            QueryValidator.validate_user_id(None)
        
        with self.assertRaises(ValidationError):
            QueryValidator.validate_user_id('invalid')


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions."""
    
    def test_safe_decimal_valid(self):
        """Test safe_decimal with valid inputs."""
        self.assertEqual(safe_decimal(10), Decimal('10'))
        self.assertEqual(safe_decimal('50.5'), Decimal('50.5'))
        self.assertEqual(safe_decimal(Decimal('100')), Decimal('100'))
    
    def test_safe_decimal_infinity(self):
        """Test safe_decimal with infinity returns default."""
        self.assertEqual(safe_decimal(float('inf')), Decimal('0'))
        self.assertEqual(safe_decimal(float('-inf')), Decimal('0'))
        self.assertEqual(safe_decimal(float('inf'), default=Decimal('100')), Decimal('100'))
    
    def test_safe_decimal_nan(self):
        """Test safe_decimal with NaN returns default."""
        self.assertEqual(safe_decimal(float('nan')), Decimal('0'))
        self.assertEqual(safe_decimal(float('nan'), default=Decimal('50')), Decimal('50'))
    
    def test_safe_decimal_invalid(self):
        """Test safe_decimal with invalid inputs returns default."""
        self.assertEqual(safe_decimal('invalid'), Decimal('0'))
        self.assertEqual(safe_decimal(None), Decimal('0'))
        self.assertEqual(safe_decimal([1, 2, 3]), Decimal('0'))
    
    def test_safe_float_to_decimal(self):
        """Test float to Decimal conversion."""
        result = safe_float_to_decimal(1.5)
        self.assertEqual(result, Decimal('1.5'))
        
        result = safe_float_to_decimal(99.12345678)
        self.assertEqual(result, Decimal('99.12345678'))
    
    def test_safe_float_to_decimal_precision(self):
        """Test float to Decimal with custom precision."""
        result = safe_float_to_decimal(1.123456789, places=2)
        self.assertEqual(result, Decimal('1.12'))
        
        result = safe_float_to_decimal(1.125, places=2)
        self.assertEqual(result, Decimal('1.12'))  # Banker's rounding
    
    def test_safe_float_to_decimal_special_values(self):
        """Test float to Decimal with special values returns zero."""
        self.assertEqual(safe_float_to_decimal(float('inf')), Decimal('0'))
        self.assertEqual(safe_float_to_decimal(float('-inf')), Decimal('0'))
        self.assertEqual(safe_float_to_decimal(float('nan')), Decimal('0'))
    
    def test_validate_trade_function(self):
        """Test the validate_trade helper function."""
        # Valid trade
        symbol, quantity, price, trade_type = validate_trade('AAPL', 10, 150.50, 'buy')
        self.assertEqual(symbol, 'AAPL')
        self.assertEqual(quantity, Decimal('10'))
        self.assertEqual(price, Decimal('150.50'))
        self.assertEqual(trade_type, 'buy')
        
        # Invalid symbol
        with self.assertRaises(ValidationError):
            validate_trade('', 10, 150.50, 'buy')
        
        # Invalid quantity
        with self.assertRaises(ValidationError):
            validate_trade('AAPL', -1, 150.50, 'buy')
        
        # Invalid trade type
        with self.assertRaises(ValidationError):
            validate_trade('AAPL', 10, 150.50, 'invalid')


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and extreme values."""
    
    def test_very_small_quantity(self):
        """Test very small but valid quantities."""
        qty = TradeValidator.validate_quantity(0.00000001)
        self.assertEqual(qty, Decimal('0.00000001'))
    
    def test_very_large_quantity(self):
        """Test large but valid quantities."""
        qty = TradeValidator.validate_quantity(999999999)
        self.assertEqual(qty, Decimal('999999999'))
    
    def test_scientific_notation(self):
        """Test scientific notation inputs."""
        qty = TradeValidator.validate_quantity('1e6')
        self.assertEqual(qty, Decimal('1000000'))
        
        qty = TradeValidator.validate_quantity('1.5e-5')
        self.assertEqual(qty, Decimal('0.000015'))
    
    def test_decimal_rounding_consistency(self):
        """Test that rounding is consistent (banker's rounding)."""
        # 0.5 rounds to nearest even
        qty = safe_float_to_decimal(1.125, places=2)
        self.assertEqual(qty, Decimal('1.12'))  # Rounds down to even
        
        qty = safe_float_to_decimal(1.135, places=2)
        self.assertEqual(qty, Decimal('1.14'))  # Rounds up to even
    
    def test_whitespace_handling(self):
        """Test that whitespace is handled correctly."""
        # Symbol with whitespace
        symbol = SymbolValidator.validate_symbol('  AAPL  ')
        self.assertEqual(symbol, 'AAPL')
        
        # Quantity with whitespace
        qty = TradeValidator.validate_quantity('  100  ')
        self.assertEqual(qty, Decimal('100'))


if __name__ == '__main__':
    unittest.main()
