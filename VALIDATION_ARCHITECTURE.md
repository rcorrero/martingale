# Input Validation Architecture (Phase 1.1)

## Overview

The Martingale platform implements a comprehensive input validation system to prevent financial exploits, SQL injection attacks, and data integrity issues. This document describes the validation architecture implemented in Phase 1.1 of the production readiness plan.

## Core Principles

### Defense in Depth
The validation system uses multiple layers:
1. **Application-level validation** - Validates inputs before any business logic
2. **Database constraints** - Enforces rules at the database level as a fallback
3. **Type safety** - Uses Python's Decimal type for all financial calculations

### Fail-Fast Approach
Invalid inputs are rejected immediately at the entry point, before any state changes or database operations occur.

### Decimal Precision
All financial calculations use Python's `Decimal` type with 8 decimal places precision to prevent:
- Float precision errors
- Rounding vulnerabilities
- Precision-based exploits

## Validation Modules

### 1. TradeValidator

Validates trade-related inputs with strict bounds checking.

**Key Features:**
- Quantity validation: MIN=1e-8, MAX=1 billion, 8 decimal places
- Price validation: MIN=0.01, MAX=1 billion, 8 decimal places
- Trade value validation: MAX=10 billion to prevent overflow
- Trade type validation: Only 'buy' or 'sell' allowed
- Rejects: negative values, zero, infinity, NaN

**Example Usage:**
```python
from validators import TradeValidator, ValidationError

try:
    quantity = TradeValidator.validate_quantity(10.5)
    price = TradeValidator.validate_price(150.75)
    trade_type = TradeValidator.validate_trade_type('buy')
    TradeValidator.validate_trade_value(quantity, price)
except ValidationError as e:
    print(f"Validation failed: {e}")
```

**Security Protection:**
- Prevents negative/infinite quantities that could exploit account balances
- Enforces realistic bounds on trade sizes
- Prevents precision attacks via extreme decimal values

### 2. SymbolValidator

Validates asset symbols with SQL injection protection.

**Key Features:**
- Pattern validation: Only A-Z letters, 1-10 characters
- Reserved word blocking: Prevents use of SQL keywords and system symbols
- Case normalization: Converts to uppercase automatically
- Whitespace handling: Strips leading/trailing whitespace

**Reserved Symbols:**
- NULL, NONE, CASH, USD, SYSTEM, ADMIN, TEST

**Example Usage:**
```python
from validators import SymbolValidator, ValidationError

try:
    symbol = SymbolValidator.validate_symbol('AAPL')  # Returns 'AAPL'
    symbol = SymbolValidator.validate_symbol('aapl')  # Returns 'AAPL' (normalized)
    symbol = SymbolValidator.validate_symbol("'; DROP TABLE--")  # Raises ValidationError
except ValidationError as e:
    print(f"Invalid symbol: {e}")
```

**Security Protection:**
- Blocks SQL injection attempts via symbol inputs
- Prevents use of reserved system keywords
- Ensures symbols follow expected format for downstream processing

### 3. PortfolioValidator

Validates portfolio-related operations and balances.

**Key Features:**
- Cash balance validation: MIN=0, MAX=100 billion
- Sufficient funds checking for buy operations
- Sufficient holdings checking for sell operations
- Prevents negative balances

**Example Usage:**
```python
from validators import PortfolioValidator, ValidationError
from decimal import Decimal

try:
    # Validate cash balance
    PortfolioValidator.validate_cash_balance(Decimal('100000'))
    
    # Check sufficient funds for purchase
    PortfolioValidator.validate_sufficient_funds(
        available=Decimal('10000'),
        required=Decimal('5000')
    )
    
    # Check sufficient holdings for sale
    PortfolioValidator.validate_sufficient_holdings(
        current_holdings=Decimal('100'),
        required=Decimal('50')
    )
except ValidationError as e:
    print(f"Portfolio validation failed: {e}")
```

**Security Protection:**
- Prevents overdraft attacks (selling more than owned)
- Prevents negative balance exploits
- Enforces realistic portfolio size limits

### 4. QueryValidator

Validates API query parameters like pagination limits and offsets.

**Key Features:**
- Limit validation with configurable min/max bounds
- Offset validation (non-negative only)
- User ID validation (positive integers only)
- Returns safe defaults for invalid inputs

**Example Usage:**
```python
from validators import QueryValidator

# Validates and clamps limit to safe range
limit = QueryValidator.validate_limit(1000, max_limit=500)  # Returns 500

# Validates offset
offset = QueryValidator.validate_offset(50)  # Returns 50

# Negative offset returns 0
offset = QueryValidator.validate_offset(-10)  # Returns 0
```

**Security Protection:**
- Prevents DOS attacks via extremely large pagination requests
- Ensures predictable API behavior
- Clamps values to safe ranges instead of rejecting

## Database Constraints

In addition to application-level validation, the database enforces constraints as a second layer of defense:

### Portfolio Table
```sql
CHECK (cash >= 0)
CHECK (cash <= 100000000000)
```

### Transaction Table
```sql
CHECK (quantity > 0)
CHECK (price >= 0)
CHECK (cost >= 0)
CHECK (type IN ('buy', 'sell', 'settlement'))
```

### Asset Table
```sql
CHECK (initial_price > 0)
CHECK (current_price > 0)
CHECK (final_price >= 0 OR final_price IS NULL)
CHECK (volatility >= 0 AND volatility <= 1)
```

### Settlement Table
```sql
CHECK (quantity > 0)
CHECK (settlement_price >= 0)
CHECK (settlement_value >= 0)
```

These constraints:
- Act as a safety net if application validation is bypassed
- Protect against direct database manipulation
- Ensure data integrity at the lowest level

## Validation Flow

### Trade Execution (handle_trade)

The `handle_trade()` WebSocket endpoint follows a strict 5-step validation process:

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: INPUT VALIDATION                                    │
│ - Validate trade type (buy/sell)                           │
│ - Validate symbol (pattern, reserved words)                │
│ - Validate quantity (bounds, precision)                    │
│ └─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: ASSET VALIDATION                                    │
│ - Verify asset exists in database                          │
│ - Check asset is active (not expired)                      │
│ - Get asset details                                        │
│ └─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: PRICE VALIDATION                                    │
│ - Fetch current price from price service                   │
│ - Validate price is within bounds                          │
│ - Ensure price is realistic/reasonable                     │
│ └─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: TRADE VALUE VALIDATION                              │
│ - Calculate trade value (quantity × price)                 │
│ - Verify trade value within max limit (10B)               │
│ - Prevent overflow attacks                                 │
│ └─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 5: PORTFOLIO VALIDATION                                │
│ - For BUY: Check sufficient funds                          │
│ - For SELL: Check sufficient holdings                      │
│ - Retrieve portfolio for processing                        │
│ └─────────────────────────────────────────────────────────┘
                           │
                           ▼
                  Execute Trade ✓
```

**Key Points:**
- All validation happens BEFORE any database operations
- Each step can independently reject the trade
- Failures emit clear error messages to the user
- All values use Decimal precision throughout

### API Endpoints

All API endpoints that accept user input now validate parameters:

**Portfolio Endpoint** (`/api/portfolio`):
- Validates `limit` parameter for transaction history
- Validates portfolio cash balance
- Logs integrity issues without failing the request

**Transactions Endpoints** (`/api/transactions`, `/api/transactions/all`):
- Validates `limit` parameter with appropriate max bounds
- Returns 400 Bad Request for invalid limits

**Leaderboard Endpoint** (`/api/leaderboard`):
- Validates `limit` parameter (max 100)
- Returns 400 Bad Request for invalid limits

**Settlements Endpoint** (`/api/settlements`):
- Validates `limit` parameter (max 200)
- Returns 400 Bad Request for invalid limits

**Performance History** (`/api/performance/history`):
- Validates `limit` parameter with custom range (50-1000)
- Returns 400 Bad Request for invalid limits

## Helper Functions

### safe_decimal()
Safely converts any value to Decimal, returning a default value on failure.

```python
from validators import safe_decimal
from decimal import Decimal

safe_decimal(10.5)              # Returns Decimal('10.5')
safe_decimal(float('inf'))      # Returns Decimal('0')
safe_decimal('invalid')         # Returns Decimal('0')
safe_decimal(None, Decimal('100'))  # Returns Decimal('100')
```

### safe_float_to_decimal()
Converts float to Decimal with specific precision using banker's rounding.

```python
from validators import safe_float_to_decimal

safe_float_to_decimal(1.123456789, places=8)  # Returns Decimal('1.12345679')
safe_float_to_decimal(1.125, places=2)        # Returns Decimal('1.12') (banker's rounding)
safe_float_to_decimal(float('inf'))           # Returns Decimal('0')
```

### validate_trade()
Convenience function that validates all components of a trade in one call.

```python
from validators import validate_trade, ValidationError

try:
    symbol, quantity, price, trade_type = validate_trade(
        symbol='AAPL',
        quantity=10,
        price=150.50,
        trade_type='buy'
    )
    # All values validated and returned as proper types
except ValidationError as e:
    print(f"Trade validation failed: {e}")
```

## Testing

The validation system includes a comprehensive test suite (`test_validators.py`) with 57 tests covering:

### Edge Cases
- Zero values
- Negative values
- Infinity and NaN
- Extremely small values (1e-8)
- Extremely large values (999,999,999)
- Scientific notation inputs

### Boundary Conditions
- Minimum/maximum quantity boundaries
- Minimum/maximum price boundaries
- Maximum trade value boundaries
- Symbol length boundaries (1-10 characters)

### Attack Vectors
- SQL injection attempts
- Reserved keyword usage
- Invalid type conversions
- Malicious string inputs
- Overflow/underflow attempts

### Precision Testing
- Decimal rounding consistency (banker's rounding)
- Float to Decimal conversion accuracy
- Multiple decimal place handling
- Scientific notation parsing

**Running Tests:**
```bash
python -m unittest test_validators -v
```

**Test Results:**
```
Ran 57 tests in 0.015s

OK
```

## Error Handling

All validators raise `ValidationError` with descriptive messages:

```python
class ValidationError(Exception):
    """Raised when input validation fails."""
    pass
```

**Error Message Examples:**
- "Quantity must be greater than zero"
- "Quantity cannot be negative"
- "Quantity must be at least 1e-8"
- "Quantity cannot exceed 1000000000"
- "Price must be at least 0.01"
- "Symbol cannot be empty"
- "Symbol must be 1-10 uppercase letters only"
- "Symbol 'NULL' is reserved and cannot be used"
- "Insufficient funds: have 5000, need 10000"
- "Trade value exceeds maximum allowed: 10000000000"

## Migration Guide: Float to Decimal

Currently, the application stores financial data as float in the database but uses Decimal for all validation and calculations. A future phase will migrate database columns to NUMERIC/DECIMAL types.

### Current Approach
```python
# Validate with Decimal precision
validated_quantity = TradeValidator.validate_quantity(10.5)  # Decimal('10.5')

# Convert to float for database (temporary)
quantity = float(validated_quantity)

# Store in database
transaction = Transaction(quantity=quantity, ...)
```

### Future Migration
```python
# After database migration to NUMERIC types
validated_quantity = TradeValidator.validate_quantity(10.5)  # Decimal('10.5')

# Store directly as Decimal
transaction = Transaction(quantity=validated_quantity, ...)
```

**Migration Steps:**
1. Add new NUMERIC columns alongside existing float columns
2. Dual-write to both columns during transition
3. Verify data consistency
4. Update all read operations to use NUMERIC columns
5. Remove old float columns
6. Update SQLAlchemy models to use Decimal type

## Performance Considerations

### Validation Overhead
- Validation adds minimal overhead (~1-5ms per request)
- Decimal operations are slightly slower than float but negligible for trading frequency
- Early rejection of invalid inputs actually improves performance by preventing unnecessary database queries

### Optimization Tips
- Validation results are not cached (security > performance for financial data)
- Database constraints are enforced at INSERT time, not on every read
- QueryValidator clamps values instead of raising errors for better UX

## Best Practices

### When Adding New Endpoints

1. **Always validate user inputs:**
   ```python
   from validators import QueryValidator, ValidationError
   
   try:
       limit = QueryValidator.validate_limit(request.args.get('limit', 100), max_limit=500)
   except ValidationError as ve:
       return jsonify({'error': str(ve)}), 400
   ```

2. **Log validation failures:**
   ```python
   logger.warning(f"Validation failed for user {user_id}: {ve}")
   ```

3. **Return descriptive error messages:**
   ```python
   return jsonify({'error': f'Invalid limit: {str(ve)}'}), 400
   ```

### When Adding New Financial Operations

1. **Use Decimal for all calculations:**
   ```python
   from decimal import Decimal
   from validators import safe_float_to_decimal
   
   value = safe_float_to_decimal(user_input)
   ```

2. **Validate before any state changes:**
   ```python
   # Validate FIRST
   TradeValidator.validate_trade_value(quantity, price)
   PortfolioValidator.validate_sufficient_funds(cash, cost)
   
   # Then execute
   portfolio.cash -= cost
   db.session.commit()
   ```

3. **Add database constraints for new tables:**
   ```sql
   CREATE TABLE new_table (
       amount NUMERIC(20, 8) CHECK (amount >= 0)
   );
   ```

## Future Enhancements

### Phase 1.2: Transaction Atomicity
- Wrap financial operations in database transactions
- Add row-level locking with `with_for_update()`
- Implement idempotency keys for duplicate request prevention

### Phase 1.3: Audit Logging
- Log all financial operations with full context
- Include IP address and user agent in audit logs
- Create immutable audit trail

### Phase 1.4: Rate Limiting
- Implement per-user trade rate limiting
- Add sliding window rate limiter
- Protect against API abuse

## Conclusion

The Phase 1.1 input validation system provides comprehensive protection against:
- **Financial exploits** - Negative values, infinity, precision attacks
- **SQL injection** - Malicious symbols and query parameters
- **Data integrity issues** - NaN, extreme values, invalid types
- **Overflow attacks** - Trade value limits and bounds checking

Combined with database constraints, this defense-in-depth approach ensures the platform is production-ready for mobile deployment and future real-money functionality.

## References

- validators.py - Main validation module
- test_validators.py - Comprehensive test suite (57 tests)
- models.py - Database models with CHECK constraints
- app.py - Validated endpoints and trade handlers
- SECURITY.md - Overall security documentation

---

**Last Updated:** November 8, 2025  
**Phase:** 1.1 - Input Validation (Production Ready)  
**Status:** ✅ Complete
