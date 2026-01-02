import pytest
from app.models import User


def test_get_user_profile(client, auth_tokens):
    """Test getting user profile."""
    access_token = auth_tokens['access_token']
    response = client.get('/api/auth/profile',
                         headers={'Authorization': f'Bearer {access_token}'})
    assert response.status_code == 200
    data = response.get_json()
    assert 'id' in data or 'user_id' in data
    assert 'username' in data
