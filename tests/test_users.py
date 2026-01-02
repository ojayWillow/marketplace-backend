import pytest
from app.models import User


def test_get_user_profile(client, auth_tokens):
    """Test getting user profile."""
    access_token = auth_tokens['access_token']
    response = client.get('/api/users/profile',
                         headers={'Authorization': f'Bearer {access_token}'})
    assert response.status_code == 200
    data = response.get_json()
    assert 'user_id' in data
    assert 'username' in data


def test_update_user_profile(client, auth_tokens):
    """Test updating user profile."""
    access_token = auth_tokens['access_token']
    updated_data = {
        'first_name': 'Updated',
        'last_name': 'Name',
        'bio': 'This is my updated bio'
    }
    response = client.put('/api/users/profile',
                         json=updated_data,
                         headers={'Authorization': f'Bearer {access_token}'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['first_name'] == 'Updated'


def test_get_user_by_id(client, auth_tokens):
    """Test getting user by ID."""
    access_token = auth_tokens['access_token']
    # Get current user's ID
    profile_response = client.get('/api/users/profile',
                                 headers={'Authorization': f'Bearer {access_token}'})
    user_id = profile_response.get_json()['user_id']
    
    # Get user by ID
    response = client.get(f'/api/users/{user_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data['user_id'] == user_id


def test_get_user_listings(client, auth_tokens):
    """Test getting user's listings."""
    access_token = auth_tokens['access_token']
    profile_response = client.get('/api/users/profile',
                                 headers={'Authorization': f'Bearer {access_token}'})
    user_id = profile_response.get_json()['user_id']
    
    response = client.get(f'/api/users/{user_id}/listings')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)


def test_change_password(client, auth_tokens):
    """Test changing user password."""
    access_token = auth_tokens['access_token']
    password_data = {
        'current_password': 'TestPass123!',
        'new_password': 'NewPass123!'
    }
    response = client.post('/api/users/change-password',
                          json=password_data,
                          headers={'Authorization': f'Bearer {access_token}'})
    assert response.status_code == 200
