import pytest
from app.models import User


def test_user_registration(client):
    """Test user registration."""
    response = client.post('/api/auth/register', json={
        'username': 'newuser',
        'email': 'newuser@example.com',
        'password': 'SecurePass123!',
        'first_name': 'New',
        'last_name': 'User'
    })
    assert response.status_code == 201
    data = response.get_json()
    assert 'user_id' in data
    assert data['username'] == 'newuser'


def test_user_login(client, auth_tokens):
    """Test user login."""
    response = client.post('/api/auth/login', json={
        'username': 'testuser',
        'password': 'TestPass123!'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert 'access_token' in data
    assert 'refresh_token' in data


def test_token_refresh(client, auth_tokens):
    """Test token refresh."""
    refresh_token = auth_tokens['refresh_token']
    response = client.post('/api/auth/refresh', 
                          headers={'Authorization': f'Bearer {refresh_token}'})
    assert response.status_code == 200
    data = response.get_json()
    assert 'access_token' in data


def test_protected_route(client, auth_tokens):
    """Test accessing protected route with valid token."""
    access_token = auth_tokens['access_token']
    response = client.get('/api/users/profile',
                         headers={'Authorization': f'Bearer {access_token}'})
    assert response.status_code == 200


def test_invalid_token(client):
    """Test accessing protected route with invalid token."""
    response = client.get('/api/users/profile',
                         headers={'Authorization': 'Bearer invalid_token'})
    assert response.status_code == 401
