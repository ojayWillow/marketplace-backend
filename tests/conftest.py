import pytest
import os
from app import create_app, db

@pytest.fixture(scope='function')
def app():
    """Create application for testing."""
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture(scope='function')
def client(app):
    """Test client for making requests."""
    return app.test_client()

@pytest.fixture(scope='function')
def runner(app):
    """Test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture(scope='function')
def db_session(app):
    """Database session for tests."""
    return db.session


@pytest.fixture(scope='function')
def auth_tokens(client, db_session):
    """Create a test user and return auth tokens."""
    from app.models import User
    
    # Create test user
    test_user = User(
        username='testuser',
        email='test@example.com',
        first_name='Test',
        last_name='User'
    )
    test_user.set_password('TestPass123!')
    db_session.add(test_user)
    db_session.commit()
    
    # Login to get tokens
    response = client.post('/api/auth/login', json={
        'email': 'test@example.com',
        'password': 'TestPass123!'
    })
    
    tokens = response.get_json()
    tokens['user_id'] = test_user.id
    return tokens


@pytest.fixture(scope='function')
def test_listing(client, auth_tokens, db_session):
    """Create a test listing/product."""
    from app.models import Listing
    
    listing = Listing(
        title='Test Product',
        description='Test description',
        price=100.00,
        category='Electronics',
        user_id=auth_tokens['user_id'],
        location='Test City'
    )
    db_session.add(listing)
    db_session.commit()
    
    return {
        'id': listing.id,
        'title': listing.title,
        'price': listing.price
    }


@pytest.fixture(scope='function')
def create_test_review(client, auth_tokens, test_listing, db_session):
    """Create a test review."""
    from app.models import Review
    
    review_data = {
        'product_id': test_listing['id'],
        'rating': 5,
        'comment': 'Great product!'
    }
    
    response = client.post(
        '/api/reviews',
        json=review_data,
        headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
    )
    
    data = response.get_json()
    return data.get('review', {})


@pytest.fixture(scope='function')
def create_second_user(client, db_session):
    """Create a second test user for authorization testing."""
    from app.models import User
    
    second_user = User(
        username='seconduser',
        email='second@example.com',
        first_name='Second',
        last_name='User'
    )
    second_user.set_password('SecondPass123!')
    db_session.add(second_user)
    db_session.commit()
    
    # Login to get token
    response = client.post('/api/auth/login', json={
        'email': 'second@example.com',
        'password': 'SecondPass123!'
    })
    
    tokens = response.get_json()
    return {
        'user_id': second_user.id,
        'token': tokens.get('access_token')
    }
