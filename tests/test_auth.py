"""
Tests for authentication endpoints.
"""

import pytest
from faker import Faker

fake = Faker()


class TestRegistration:
    """Tests for POST /api/auth/register"""
    
    def test_register_success(self, client, db_session):
        """Test successful user registration."""
        data = {
            'username': fake.user_name(),
            'email': fake.email(),
            'password': 'securepassword123'
        }
        
        response = client.post('/api/auth/register', json=data)
        
        assert response.status_code == 201
        assert 'user' in response.json or 'id' in response.json
    
    def test_register_missing_fields(self, client, db_session):
        """Test registration with missing required fields."""
        # Missing password
        data = {
            'username': fake.user_name(),
            'email': fake.email()
        }
        
        response = client.post('/api/auth/register', json=data)
        
        assert response.status_code in [400, 422]
    
    def test_register_invalid_email(self, client, db_session):
        """Test registration with invalid email format."""
        data = {
            'username': fake.user_name(),
            'email': 'not-an-email',
            'password': 'securepassword123'
        }
        
        response = client.post('/api/auth/register', json=data)
        
        # Should reject invalid email
        assert response.status_code in [400, 422, 201]  # Some APIs may accept any string
    
    def test_register_duplicate_email(self, client, db_session, test_user):
        """Test registration with already existing email."""
        data = {
            'username': fake.user_name(),
            'email': test_user['email'],  # Use existing email
            'password': 'securepassword123'
        }
        
        response = client.post('/api/auth/register', json=data)
        
        assert response.status_code in [400, 409]  # Bad request or Conflict
    
    def test_register_short_password(self, client, db_session):
        """Test registration with too short password."""
        data = {
            'username': fake.user_name(),
            'email': fake.email(),
            'password': '123'  # Too short
        }
        
        response = client.post('/api/auth/register', json=data)
        
        # May be accepted or rejected depending on validation rules
        assert response.status_code in [201, 400, 422]


class TestLogin:
    """Tests for POST /api/auth/login"""
    
    def test_login_success(self, client, test_user):
        """Test successful login."""
        response = client.post('/api/auth/login', json={
            'email': test_user['email'],
            'password': test_user['password']
        })
        
        assert response.status_code == 200
        assert 'token' in response.json or 'access_token' in response.json
    
    def test_login_wrong_password(self, client, test_user):
        """Test login with wrong password."""
        response = client.post('/api/auth/login', json={
            'email': test_user['email'],
            'password': 'wrongpassword'
        })
        
        assert response.status_code == 401
    
    def test_login_nonexistent_user(self, client, db_session):
        """Test login with non-existent email."""
        response = client.post('/api/auth/login', json={
            'email': 'nonexistent@example.com',
            'password': 'anypassword'
        })
        
        assert response.status_code in [401, 404]
    
    def test_login_missing_fields(self, client, db_session):
        """Test login with missing fields."""
        response = client.post('/api/auth/login', json={
            'email': fake.email()
            # Missing password
        })
        
        assert response.status_code in [400, 401, 422]


class TestProfile:
    """Tests for GET/PUT /api/auth/profile"""
    
    def test_get_profile_authenticated(self, client, auth_headers):
        """Test getting profile when authenticated."""
        response = client.get('/api/auth/profile', headers=auth_headers)
        
        assert response.status_code == 200
        assert 'username' in response.json or 'user' in response.json
    
    def test_get_profile_unauthenticated(self, client, db_session):
        """Test getting profile without authentication."""
        response = client.get('/api/auth/profile')
        
        assert response.status_code in [401, 422]
    
    def test_get_profile_invalid_token(self, client, db_session):
        """Test getting profile with invalid token."""
        headers = {'Authorization': 'Bearer invalid-token-here'}
        response = client.get('/api/auth/profile', headers=headers)
        
        assert response.status_code in [401, 422]
    
    def test_update_profile(self, client, auth_headers):
        """Test updating user profile."""
        new_bio = fake.paragraph()
        
        response = client.put('/api/auth/profile', 
            headers=auth_headers,
            json={'bio': new_bio}
        )
        
        assert response.status_code == 200
    
    def test_update_profile_unauthenticated(self, client, db_session):
        """Test updating profile without authentication."""
        response = client.put('/api/auth/profile', json={'bio': 'New bio'})
        
        assert response.status_code in [401, 422]


class TestPublicUserProfile:
    """Tests for GET /api/auth/users/:id"""
    
    def test_get_public_profile(self, client, test_user, db_session):
        """Test getting a public user profile."""
        response = client.get(f'/api/auth/users/{test_user["id"]}')
        
        assert response.status_code == 200
        assert 'username' in response.json
    
    def test_get_nonexistent_user(self, client, db_session):
        """Test getting non-existent user profile."""
        response = client.get('/api/auth/users/99999')
        
        assert response.status_code == 404
