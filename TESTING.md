# Testing Guide for Martingale Trading Platform

## Overview

This guide provides comprehensive information about testing the Martingale trading platform. The test suite includes over 200 tests covering models, business logic, API endpoints, and integration scenarios.

## Test Structure

```
martingale/
├── conftest.py                 # Pytest configuration and shared fixtures
├── test_models.py              # Database model tests (~50 tests)
├── test_asset_manager.py       # Asset lifecycle tests (~40 tests)
├── test_app.py                 # Flask application tests (~60 tests)
├── test_validators.py          # Input validation tests (57 tests)
├── test_integration.py         # End-to-end workflow tests (~30 tests)
├── test_expiring_assets.py     # Legacy: Asset expiration tests
├── test_drift_implementation.py # Legacy: GBM drift tests
├── test_martingale_property.py # Legacy: Martingale property tests
└── services_startup_test.py    # Service health checks
```

## Quick Start

### Install Test Dependencies

```bash
pip install pytest pytest-cov pytest-flask
```

### Run All Tests

```bash
pytest
```

### Run With Coverage

```bash
pytest --cov=. --cov-report=html --cov-report=term
open htmlcov/index.html
```

## Test Categories

### 1. Model Tests (`test_models.py`)

Tests database models, constraints, and relationships.

**Coverage Areas:**
- User authentication and password hashing
- Portfolio holdings management and serialization
- Transaction CRUD operations and constraints
- Asset lifecycle methods and expiration
- Settlement record creation
- Database integrity constraints
- Cascade delete behavior

**Example Commands:**
```bash
# All model tests
pytest test_models.py -v

# Specific model
pytest test_models.py::TestUserModel -v
pytest test_models.py::TestPortfolioModel -v
pytest test_models.py::TestAssetModel -v
```

### 2. Asset Manager Tests (`test_asset_manager.py`)

Tests asset lifecycle management and settlement.

**Coverage Areas:**
- Asset creation and initialization
- Active/expired/worthless asset queries
- Time-based expiration processing
- Price-based early settlement
- Position settlement with cash return
- Asset pool maintenance
- Settlement transaction creation
- Old asset cleanup

**Example Commands:**
```bash
# All asset manager tests
pytest test_asset_manager.py -v

# Specific functionality
pytest test_asset_manager.py::TestAssetExpiration -v
pytest test_asset_manager.py::TestPositionSettlement -v
pytest test_asset_manager.py::TestAssetPoolMaintenance -v
```

### 3. Application Tests (`test_app.py`)

Tests Flask routes, authentication, and API endpoints.

**Coverage Areas:**
- User registration and validation
- Login with rate limiting
- Logout and session management
- Portfolio API endpoints
- Performance calculation endpoints
- Transaction history endpoints
- Asset market data endpoints
- Settlement history endpoints
- Leaderboard endpoint
- Input validation and error handling
- SQL injection protection
- Authentication requirements

**Example Commands:**
```bash
# All application tests
pytest test_app.py -v

# Authentication flows
pytest test_app.py::TestAuthentication -v

# API endpoints
pytest test_app.py::TestPortfolioEndpoints -v
pytest test_app.py::TestAssetEndpoints -v
pytest test_app.py::TestPerformanceEndpoints -v
```

### 4. Validator Tests (`test_validators.py`)

Tests comprehensive input validation system (57 tests).

**Coverage Areas:**
- Trade quantity validation (boundaries, precision)
- Price validation (min/max, NaN/infinity)
- Trade value calculation and limits
- Symbol validation and SQL injection protection
- Portfolio cash balance validation
- Sufficient funds/holdings checks
- Query parameter validation
- Edge cases (negative, zero, extreme values)
- Decimal precision and rounding

**Example Commands:**
```bash
# All validation tests
pytest test_validators.py -v

# Specific validators
pytest test_validators.py::TestTradeValidator -v
pytest test_validators.py::TestSymbolValidator -v
pytest test_validators.py::TestPortfolioValidator -v
```

### 5. Integration Tests (`test_integration.py`)

Tests end-to-end workflows and multi-component interactions.

**Coverage Areas:**
- Complete user registration → trading workflow
- Buy → sell transaction flow
- Asset creation → expiration → settlement
- Worthless asset early settlement
- Multi-user trading scenarios
- Performance calculation with real data
- Asset pool replacement workflow
- Concurrent operations
- Data integrity across transactions

**Example Commands:**
```bash
# All integration tests
pytest test_integration.py -v

# Specific workflows
pytest test_integration.py::TestCompleteUserWorkflow -v
pytest test_integration.py::TestAssetLifecycleWorkflow -v
pytest test_integration.py::TestMultiUserTradingScenario -v
```

## Test Fixtures

### Available Fixtures (from `conftest.py`)

#### Application Fixtures
- `app` - Flask application with test config
- `client` - Test client for making requests
- `db_session` - Database session for queries
- `authenticated_client` - Pre-authenticated test client

#### User Fixtures
- `test_user` - Basic user without portfolio
- `test_user_with_portfolio` - User with empty portfolio
- `multiple_users` - 3 users with portfolios
- `user_with_holdings` - User with 100 shares of test asset

#### Asset Fixtures
- `test_asset` - Single active asset
- `multiple_assets` - 5 active assets with varying properties
- `expired_asset` - Already expired and settled asset
- `worthless_asset` - Asset with price below threshold

#### Transaction Fixtures
- `buy_transaction` - Sample buy transaction
- `sell_transaction` - Sample sell transaction
- `settlement_record` - Sample settlement record

#### Service Fixtures
- `mock_price_service` - Mock price service for testing
- `mock_socketio` - Mock SocketIO for testing events
- `data_generator` - Helper for creating test data

### Using Fixtures

```python
def test_example(test_user_with_portfolio, test_asset):
    """Example test using fixtures."""
    with app.app_context():
        user = test_user_with_portfolio
        assert user.portfolio is not None
        assert user.portfolio.cash == 100000.0
```

## Common Test Patterns

### Testing Database Models

```python
def test_create_and_query(app):
    """Test creating and querying database records."""
    with app.app_context():
        # Create
        user = User(username='testuser')
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        
        # Query
        retrieved = User.query.filter_by(username='testuser').first()
        assert retrieved is not None
        assert retrieved.check_password('password123')
```

### Testing API Endpoints

```python
def test_api_endpoint(authenticated_client, app):
    """Test API endpoint returns correct data."""
    with app.app_context():
        response = authenticated_client.get('/api/portfolio')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'cash' in data
        assert 'holdings' in data
```

### Testing Business Logic

```python
def test_settlement_logic(app, user_with_holdings, test_asset, mock_price_service):
    """Test settlement returns cash to user."""
    with app.app_context():
        # Setup
        asset = Asset.query.filter_by(symbol='TEST').first()
        portfolio = user_with_holdings.portfolio
        cash_before = portfolio.cash
        
        # Expire and settle
        asset.expire(final_price=110.0)
        manager = AssetManager(app.config, mock_price_service)
        manager.settle_expired_positions([asset])
        
        # Verify
        assert portfolio.cash > cash_before
```

### Testing Validation

```python
def test_validation_rejects_invalid(app):
    """Test validation rejects invalid input."""
    with app.app_context():
        from validators import ValidationError, TradeValidator
        
        # Should raise ValidationError
        with pytest.raises(ValidationError):
            TradeValidator.validate_quantity(-10)
```

## Coverage Goals

### Target Coverage by Module

- **models.py**: >90% (critical for data integrity)
- **validators.py**: >95% (critical for security)
- **asset_manager.py**: >85% (complex business logic)
- **app.py**: >80% (many branches, some unreachable)

### Checking Coverage

```bash
# Generate HTML coverage report
pytest --cov=. --cov-report=html
open htmlcov/index.html

# Terminal coverage report
pytest --cov=. --cov-report=term-missing

# Coverage for specific modules
pytest --cov=models --cov=validators --cov-report=term
```

### Coverage Report Interpretation

```
Name                    Stmts   Miss  Cover   Missing
-----------------------------------------------------
models.py                 450     45    90%   123-145, 234
validators.py             280     14    95%   156-169
asset_manager.py          320     48    85%   78-92, 234-245
app.py                    680    136    80%   Many branches
-----------------------------------------------------
TOTAL                    1730    243    86%
```

## Running Tests in Different Modes

### Verbose Mode
```bash
pytest -v
```

### Stop on First Failure
```bash
pytest -x
```

### Show Print Statements
```bash
pytest -s
```

### Run Only Failed Tests
```bash
pytest --lf  # Last failed
pytest --ff  # Failed first, then all
```

### Run Tests by Pattern
```bash
pytest -k "user"        # All tests with "user" in name
pytest -k "not slow"    # Skip slow tests
pytest -k "validation"  # All validation tests
```

### Parallel Execution
```bash
pip install pytest-xdist
pytest -n auto  # Auto-detect CPU count
pytest -n 4     # Use 4 workers
```

## Debugging Tests

### Using Debugger
```bash
pytest --pdb  # Drop into debugger on failure
```

### Verbose Tracebacks
```bash
pytest --tb=long   # Full traceback
pytest --tb=short  # Minimal traceback
pytest --tb=line   # Single line per failure
```

### Show Local Variables
```bash
pytest -l  # Show local variables on failure
```

### Custom Markers
```python
@pytest.mark.slow
def test_slow_operation():
    """Mark slow tests for conditional execution."""
    pass

# Run marked tests
pytest -m "slow"        # Only slow tests
pytest -m "not slow"    # Skip slow tests
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12']
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run tests with coverage
        run: |
          pytest --cov=. --cov-report=xml --cov-report=term
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

## Best Practices

### Writing Tests

1. **Isolation**: Each test should be independent
2. **Clear Names**: Use descriptive names (test_what_when_then pattern)
3. **Single Purpose**: Each test should test one thing
4. **Fixtures**: Use fixtures for setup/teardown
5. **Assertions**: Be specific about expected values
6. **Edge Cases**: Test boundary conditions
7. **Documentation**: Add docstrings explaining purpose
8. **Speed**: Keep tests fast (use in-memory database)

### Test Naming Convention

```python
# Good
def test_user_can_register_with_valid_credentials():
    pass

def test_trade_rejected_when_insufficient_funds():
    pass

# Bad
def test_1():
    pass

def test_user():
    pass
```

### Fixture Best Practices

```python
# Use scope appropriately
@pytest.fixture(scope='function')  # New instance per test
def user():
    return create_user()

@pytest.fixture(scope='module')  # Shared across module
def expensive_resource():
    return create_expensive_resource()

# Clean up after tests
@pytest.fixture
def temp_file(tmp_path):
    file = tmp_path / "test.txt"
    file.write_text("data")
    yield file
    # Cleanup happens automatically with tmp_path
```

## Troubleshooting

### Test Database Issues

```bash
# If tests fail due to database issues:
rm -f instance/test.db
pytest test_models.py -v
```

### Import Errors

```bash
# Ensure project root in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest
```

### Fixture Not Found

```bash
# Ensure conftest.py is in the same directory
ls conftest.py
pytest --fixtures  # List all available fixtures
```

### Tests Hanging

```bash
# Add timeout
pip install pytest-timeout
pytest --timeout=30  # 30 second timeout per test
```

## Performance Testing

### Measure Test Duration

```bash
# Show slowest 10 tests
pytest --durations=10

# Show all test durations
pytest --durations=0
```

### Profile Tests

```bash
pip install pytest-profiling
pytest --profile
```

## Maintenance

### Updating Tests

When modifying code:
1. Run relevant tests first
2. Update tests to match new behavior
3. Add tests for new features
4. Ensure all tests pass
5. Check coverage hasn't decreased

### Refactoring Tests

```bash
# Find duplicate test code
grep -r "def test_" . | cut -d: -f2 | sort | uniq -c | sort -rn

# Find slow tests
pytest --durations=20

# Find flaky tests
pytest --count=10  # Run each test 10 times
```

## Resources

- **Pytest Documentation**: https://docs.pytest.org/
- **Pytest Fixtures**: https://docs.pytest.org/en/stable/fixture.html
- **Testing Flask Applications**: https://flask.palletsprojects.com/en/latest/testing/
- **Coverage.py**: https://coverage.readthedocs.io/

## Getting Help

If tests fail:
1. Read the error message carefully
2. Check relevant test file for documentation
3. Review fixture definitions in `conftest.py`
4. Run with `-v` for verbose output
5. Use `--pdb` to debug interactively
6. Check if database needs reset
7. Verify all dependencies installed

For questions or issues, open an issue on GitHub.
