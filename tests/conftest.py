"""
Pytest configuration and fixtures for testing the Marketplace API.
"""

import os
import sys
import pytest
from faker import Faker

# Add the parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.user import User
from app.models.listing import Listing
from app.models.task_request import TaskRequest
from app.models.offering import Offering
from app.models.review import Review

fake = Faker()


@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    # Set test configuration
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['JWT_SECRET_KEY'] = 'test-secret-key-for-testing'
    
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'JWT_SECRET_KEY': 'test-secret-key-for-testing',
        'WTF_CSRF_ENABLED': False,
    })
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    yield app
    
    # Cleanup
    with app.app_context():
        db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """Create test client for each test function."""
    return app.test_client()


@pytest.fixture(scope='function')
def db_session(app):
    """Create a fresh database session for each test."""
    with app.app_context():
        # Clear all tables before each test
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        yield db.session
        db.session.rollback()


@pytest.fixture
def test_user(app, db_session):
    """Create a test user."""
    with app.app_context():
        user = User(
            username=fake.user_name(),
            email=fake.email(),
            password_hash='test_hash'
        )
        user.set_password('testpassword123')
        db.session.add(user)
        db.session.commit()
        
        # Return user data as dict since we're outside context later
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'password': 'testpassword123'
        }


@pytest.fixture
def second_user(app, db_session):
    """Create a second test user for interaction tests."""
    with app.app_context():
        user = User(
            username=fake.user_name(),
            email=fake.email(),
            password_hash='test_hash'
        )
        user.set_password('testpassword456')
        db.session.add(user)
        db.session.commit()
        
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'password': 'testpassword456'
        }


@pytest.fixture
def auth_headers(client, test_user):
    """Get authentication headers for test user."""
    response = client.post('/api/auth/login', json={
        'email': test_user['email'],
        'password': test_user['password']
    })
    token = response.json.get('access_token') or response.json.get('token')
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def second_auth_headers(client, second_user):
    """Get authentication headers for second user."""
    response = client.post('/api/auth/login', json={
        'email': second_user['email'],
        'password': second_user['password']
    })
    token = response.json.get('access_token') or response.json.get('token')
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def test_listing(app, db_session, test_user):
    """Create a test listing."""
    with app.app_context():
        listing = Listing(
            title=fake.sentence(nb_words=4),
            description=fake.paragraph(),
            price=fake.pyfloat(min_value=10, max_value=1000, right_digits=2),
            category='electronics',
            status='active',
            user_id=test_user['id']
        )
        db.session.add(listing)
        db.session.commit()
        
        return {
            'id': listing.id,
            'title': listing.title,
            'user_id': listing.user_id
        }


@pytest.fixture
def test_task(app, db_session, test_user):
    """Create a test task."""
    with app.app_context():
        task = TaskRequest(
            title=fake.sentence(nb_words=4),
            description=fake.paragraph(),
            budget=fake.pyfloat(min_value=20, max_value=500, right_digits=2),
            category='cleaning',
            status='open',
            location_lat=56.9496,
            location_lng=24.1052,
            location_address='Riga, Latvia',
            user_id=test_user['id']
        )
        db.session.add(task)
        db.session.commit()
        
        return {
            'id': task.id,
            'title': task.title,
            'user_id': task.user_id
        }


@pytest.fixture
def test_offering(app, db_session, test_user):
    """Create a test offering."""
    with app.app_context():
        offering = Offering(
            title=fake.sentence(nb_words=4),
            description=fake.paragraph(),
            price=fake.pyfloat(min_value=15, max_value=100, right_digits=2),
            price_type='hourly',
            category='handyman',
            status='active',
            location_lat=56.9496,
            location_lng=24.1052,
            location_address='Riga, Latvia',
            user_id=test_user['id']
        )
        db.session.add(offering)
        db.session.commit()
        
        return {
            'id': offering.id,
            'title': offering.title,
            'user_id': offering.user_id
        }
