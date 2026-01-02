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
    import jwt
    import os
    from datetime import datetime, timedelta
    
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
    
    # Generate real JWT token
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
    payload = {
        'user_id': test_user.id,
        'username': test_user.username,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    
    return {
        'user_id': test_user.id,
        'access_token': token,
        'refresh_token': token  # Using same token for simplicity in tests
    }

@pytest.fixture(scope='function')
def test_listing(client, auth_tokens, db_session):
    """Create a test listing/product."""
    from app.models import Listing
    
    listing = Listing(
        title='Test Product',
        description='Test description',
        price=100.00,
        category='Electronics',
        seller_id=auth_tokens['user_id'],
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
    """Create a test review directly in database."""
    from app.models import Review
    
    review = Review(
        reviewer_id=auth_tokens['user_id'],
        reviewed_user_id=auth_tokens['user_id'],
        listing_id=test_listing['id'],
        rating=5,
        content='Great product!'
    )
    db_session.add(review)
    db_session.commit()
    
    return {
        'id': review.id,
        'rating': review.rating,
        'content': review.content
    }
    return {}


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
    
    # Return mock token
    return {
        'user_id': second_user.id,
        'token': 'mock_second_user_token'
    }
