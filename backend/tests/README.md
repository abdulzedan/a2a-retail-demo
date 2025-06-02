# A2A Retail Demo - Test Suite

This directory contains the comprehensive test suite for the A2A Retail Demo project.

## Test Structure

```
backend/tests/
├── conftest.py              # Shared fixtures and configuration
├── test_inventory_agent.py  # Unit tests for inventory agent
├── test_host_agent.py       # Unit tests for host agent
├── test_customer_service_agent.py  # Unit tests for customer service agent
├── test_integration.py      # Integration tests for agent communication
└── run_tests.py            # Test runner script
```

## Running Tests

### Using Make commands:

```bash
# Run all tests
make test

# Run only unit tests
make test-unit

# Run only integration tests
make test-integration

# Run tests with coverage report
make test-coverage

# Run linting
make lint
```

### Using pytest directly:

```bash
# Run all tests
.venv/bin/python -m pytest backend/tests -v

# Run specific test file
.venv/bin/python -m pytest backend/tests/test_inventory_agent.py -v

# Run specific test
.venv/bin/python -m pytest backend/tests/test_inventory_agent.py::TestInventoryAgent::test_search_products_by_query -v

# Run with coverage
.venv/bin/python -m pytest backend/tests --cov=backend --cov-report=html
```

## Test Categories

### Unit Tests
- Test individual agent components in isolation
- Mock external dependencies (API calls, database)
- Fast execution
- No network calls

### Integration Tests
- Test agent-to-agent communication
- Test A2A protocol implementation
- Test error handling across agents
- May require longer execution time

## Writing New Tests

### Test Structure Example:

```python
import pytest
from unittest.mock import Mock, AsyncMock

class TestNewFeature:
    @pytest.fixture
    def setup_fixture(self):
        # Setup code
        return mock_object
    
    @pytest.mark.asyncio
    async def test_async_feature(self, setup_fixture):
        # Test async functionality
        result = await async_function()
        assert result == expected
    
    def test_sync_feature(self):
        # Test synchronous functionality
        assert True
```

### Best Practices:

1. **Use descriptive test names**: `test_search_products_returns_filtered_results`
2. **One assertion per test** when possible
3. **Use fixtures** for common setup
4. **Mock external dependencies** to avoid network calls
5. **Mark tests appropriately**: `@pytest.mark.integration`, `@pytest.mark.slow`
6. **Test both success and failure cases**
7. **Test edge cases** (empty inputs, invalid data, etc.)

## Coverage Goals

- Aim for >80% code coverage
- Focus on critical business logic
- Don't test framework code or simple getters/setters
- Integration tests complement unit tests

## Debugging Tests

```bash
# Run with debugging output
.venv/bin/python -m pytest backend/tests -v -s

# Run with full traceback
.venv/bin/python -m pytest backend/tests -v --tb=long

# Stop on first failure
.venv/bin/python -m pytest backend/tests -x
```

## Continuous Integration

Tests should be run:
- Before committing code
- In pull request checks
- As part of deployment pipeline

## Common Issues

1. **Import errors**: Ensure PYTHONPATH includes the backend directory
2. **Async test failures**: Use `@pytest.mark.asyncio` decorator
3. **Mock not working**: Check patch path matches actual import path
4. **Slow tests**: Use mocks instead of real API calls