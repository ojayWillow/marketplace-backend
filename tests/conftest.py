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
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['JWT_SECRET_KEY'] = 'test-secret-key-for-testing'

    app = create_app('testing')
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'JWT_SECRET_KEY': 'test-secret-key-for-testing',
        'WTF_CSRF_ENABLED': False,
    })

    with app.app_context():
        db.create_all()

    yield app

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
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        yield db.session
        db.session.rollback()


def _create_user(password='testpassword123', **overrides):
    """Helper to create a user with sensible defaults."""
    data = {
        'username': fake.user_name() + fake.pystr(min_chars=4, max_chars=6),
        'email': fake.unique.email(),
        'first_name': fake.first_name(),
        'last_name': fake.last_name(),
    }
    data.update(overrides)
    user = User(**{k: v for k, v in data.items() if k != 'password'})
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'password': password,
    }


@pytest.fixture
def test_user(app, db_session):
    """Create a test user."""
    with app.app_context():
        return _create_user()


@pytest.fixture
def second_user(app, db_session):
    """Create a second test user for interaction tests."""
    with app.app_context():
        return _create_user(password='testpassword456')


def _get_token(client, email, password):
    """Login and return JWT token."""
    resp = client.post('/api/auth/login', json={
        'email': email,
        'password': password,
    })
    data = resp.get_json()
    return data.get('access_token') or data.get('token')


@pytest.fixture
def auth_headers(client, test_user):
    """Get authentication headers for test user."""
    token = _get_token(client, test_user['email'], test_user['password'])
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def second_auth_headers(client, second_user):
    """Get authentication headers for second user."""
    token = _get_token(client, second_user['email'], second_user['password'])
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def test_listing(app, db_session, test_user):
    """Create a test listing matching actual Listing model."""
    with app.app_context():
        listing = Listing(
            title=fake.sentence(nb_words=4),
            description=fake.paragraph(),
            price=round(fake.pyfloat(min_value=10, max_value=500, right_digits=2), 2),
            category='electronics',
            status='active',
            seller_id=test_user['id'],
        )
        db.session.add(listing)
        db.session.commit()
        return {
            'id': listing.id,
            'title': listing.title,
            'seller_id': listing.seller_id,
        }


@pytest.fixture
def test_task(app, db_session, test_user):
    """Create a test task matching actual TaskRequest model."""
    with app.app_context():
        task = TaskRequest(
            title=fake.sentence(nb_words=4),
            description=fake.paragraph(),
            budget=round(fake.pyfloat(min_value=20, max_value=500, right_digits=2), 2),
            category='cleaning',
            status='open',
            location='Riga, Latvia',
            latitude=56.9496,
            longitude=24.1052,
            creator_id=test_user['id'],
        )
        db.session.add(task)
        db.session.commit()
        return {
            'id': task.id,
            'title': task.title,
            'creator_id': task.creator_id,
        }
