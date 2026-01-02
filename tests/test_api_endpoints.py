"""Test suite for API endpoint integration."""
import pytest


class TestAPIEndpoints:
    """Integration tests for all API endpoints."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get('/health')
        assert response.status_code == 200
        data = response.get_json()
        assert data.get('status') == 'ok'

    def test_auth_register_and_login_flow(self, client):
        """Test complete registration and login flow."""
        # Register user
        register_data = {
            'username': 'flowtest',
            'email': 'flowtest@example.com',
            'password': 'TestPass123!',
            'first_name': 'Flow',
            'last_name': 'Test'
        }
        
        response = client.post(
            '/api/auth/register',
            json=register_data
        )
        
        if response.status_code not in (200, 201):
            print(f"Registration failed: {response.status_code} {response.get_json()}")
        assert response.status_code in (200, 201)

        # Login user
        login_data = {
            'email': 'flowtest@example.com',
            'password': 'TestPass123!'
        }
        
        response = client.post(
            '/api/auth/login',
            json=login_data
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'token' in data

    def test_listings_crud_flow(self, client, auth_tokens):
        """Test complete listings CRUD flow."""
        # Create listing
        listing_data = {
            'title': 'CRUD Test Product',
            'description': 'Test description',
            'price': 99.99,
            'category': 'electronics'
        }
        
        response = client.post(
            '/api/listings',
            json=listing_data,
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )
        
        assert response.status_code == 201
        data = response.get_json()
        listing_id = data['listing']['id']

        # Get single listing
        response = client.get(f'/api/listings/{listing_id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == listing_id

        # Update listing
        update_data = {'price': 79.99}
        response = client.put(
            f'/api/listings/{listing_id}',
            json=update_data,
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200

        # Delete listing
        response = client.delete(
            f'/api/listings/{listing_id}',
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200

    def test_reviews_flow(self, client, auth_tokens, test_listing):
        """Test reviews creation and retrieval flow."""
        product_id = test_listing['id']
        
        # Create review
        review_data = {
            'reviewed_user_id': auth_tokens['user_id'],
            'content': 'Flow test review',
            'listing_id': product_id,
            'rating': 5,
            'comment': 'Flow test review'        
        response = client.post(
            '/api/reviews',
            json=review_data,
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )
        
        assert response.status_code == 201
        
        # Get reviews for product
        response = client.get(f'/api/reviews/product/{product_id}')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_unauthorized_access(self, client):
        """Test that protected endpoints require authentication."""
        # Try to create listing without auth
        listing_data = {
            'title': 'Unauthorized Test',
            'description': 'Should fail',
            'price': 50.00,
            'category': 'test'
        }
        
        response = client.post(
            '/api/listings',
            json=listing_data
        )
        
        assert response.status_code == 401

    def test_invalid_endpoints(self, client):
        """Test that invalid endpoints return 404."""
        response = client.get('/api/nonexistent')
        assert response.status_code == 404
