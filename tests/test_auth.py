import pytest
from app.models import User


def test_user_registration(client):
    """Test user registration."""
    response = client.post('/register', json={
        'username': 'newuser',
        'email': 'newuser@example.com',
        'password': 'SecurePass123!',
        'first_name': 'New',
        'last_name': 'User'
    })
    assert response.status_code == 201
    data = response.get_json()
    assert 'user' in data
    assert data['user']['username'] == 'newuser'


def test_user_login(client, auth_tokens):
    """Test user login."""
    # Use email instead of username for login
    response = client.post('/login', json={
        'email': 'test@example.com',
        'password': 'TestPass123!'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert 'token' in data


def test_protected_route(client, auth_tokens):
    """Test accessing protected route with valid token."""
    token = auth_tokens['access_token']
    response = client.get('/profile',
                         headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 200


def test_invalid_token(client):
    """Test accessing protected route with invalid token."""
    response = client.get('/profile',
                         headers={'Authorization': 'Bearer invalid_token'})
    assert response.status_code in (400, 401)
