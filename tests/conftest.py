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
