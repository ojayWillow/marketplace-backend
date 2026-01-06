# Backend Tests

Unit and integration tests for the Marketplace API.

## Setup

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Or install everything
pip install -r requirements.txt -r requirements-test.txt
```

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_auth.py

# Run specific test class
pytest tests/test_auth.py::TestLogin

# Run specific test
pytest tests/test_auth.py::TestLogin::test_login_success

# Run tests matching a keyword
pytest -k "login"

# Run tests by marker
pytest -m auth
pytest -m "not slow"
```

## Coverage Reports

```bash
# Run tests with coverage
pytest --cov=app

# Generate HTML coverage report
pytest --cov=app --cov-report=html

# View report
open htmlcov/index.html  # Mac
start htmlcov/index.html  # Windows
```

## Test Structure

```
tests/
├── __init__.py          # Package init
├── conftest.py          # Shared fixtures
├── test_auth.py         # Authentication tests
├── test_listings.py     # Listings CRUD tests
├── test_tasks.py        # Tasks CRUD + workflow tests
├── test_offerings.py    # Offerings tests (TODO)
├── test_reviews.py      # Reviews tests (TODO)
└── README.md            # This file
```

## Fixtures

Shared fixtures are defined in `conftest.py`:

| Fixture | Description |
|---------|-------------|
| `app` | Flask test application |
| `client` | Test client for making requests |
| `db_session` | Fresh database session (cleared each test) |
| `test_user` | A registered test user |
| `second_user` | Second user for interaction tests |
| `auth_headers` | Authorization headers for test_user |
| `second_auth_headers` | Authorization headers for second_user |
| `test_listing` | A sample listing |
| `test_task` | A sample task |
| `test_offering` | A sample offering |

## Writing Tests

### Basic Test Structure

```python
import pytest
from faker import Faker

fake = Faker()


class TestFeatureName:
    """Tests for feature X"""
    
    def test_something_works(self, client, auth_headers):
        """Test that something works correctly."""
        response = client.get('/api/endpoint', headers=auth_headers)
        
        assert response.status_code == 200
        assert 'expected_key' in response.json
```

### Test Naming Conventions

- Test files: `test_<feature>.py`
- Test classes: `Test<Feature>`
- Test methods: `test_<what_is_being_tested>`

### Using Fixtures

```python
def test_with_authenticated_user(self, client, auth_headers, test_user):
    """auth_headers automatically logs in test_user"""
    response = client.get('/api/auth/profile', headers=auth_headers)
    assert response.json['email'] == test_user['email']
```

### Testing Error Cases

```python
def test_unauthenticated_access(self, client):
    """Test that unauthenticated requests are rejected."""
    response = client.get('/api/protected-endpoint')
    assert response.status_code in [401, 422]
```

## Test Categories

Tests are organized by feature:

### Authentication (`test_auth.py`)
- User registration
- Login/logout
- Profile management
- Token validation

### Listings (`test_listings.py`)
- CRUD operations
- Category filtering
- Pagination
- Authorization (own listings only)

### Tasks (`test_tasks.py`)
- CRUD operations
- Location-based search
- Task workflow (apply → accept → done → confirm)
- Authorization

### Offerings (`test_offerings.py`) - TODO
- CRUD operations
- Location search
- Price types

### Reviews (`test_reviews.py`) - TODO
- Create/update/delete reviews
- Rating calculations
- Self-review prevention

## CI/CD Integration

Add to your CI pipeline:

```yaml
# GitHub Actions example
- name: Run tests
  run: |
    pip install -r requirements.txt -r requirements-test.txt
    pytest --cov=app --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Troubleshooting

### Database Issues

Tests use SQLite in-memory database. If you see database errors:

1. Check that models are imported in `conftest.py`
2. Ensure `db.create_all()` is called in the app fixture

### Import Errors

Make sure the parent directory is in the Python path:

```python
import sys
sys.path.insert(0, '..')
```

### Fixture Not Found

Ensure the fixture is defined in `conftest.py` or the same test file.
