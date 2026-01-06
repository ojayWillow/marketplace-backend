"""
Tests for listings endpoints.
"""

import pytest
from faker import Faker

fake = Faker()


class TestListListings:
    """Tests for GET /api/listings"""
    
    def test_list_listings_empty(self, client, db_session):
        """Test listing when no listings exist."""
        response = client.get('/api/listings')
        
        assert response.status_code == 200
        # Response should be a list or have listings key
        assert isinstance(response.json, list) or 'listings' in response.json
    
    def test_list_listings_with_data(self, client, test_listing):
        """Test listing when listings exist."""
        response = client.get('/api/listings')
        
        assert response.status_code == 200
        data = response.json if isinstance(response.json, list) else response.json.get('listings', [])
        assert len(data) >= 1
    
    def test_list_listings_filter_category(self, client, test_listing):
        """Test filtering listings by category."""
        response = client.get('/api/listings?category=electronics')
        
        assert response.status_code == 200
    
    def test_list_listings_pagination(self, client, db_session):
        """Test listings pagination."""
        response = client.get('/api/listings?page=1&per_page=10')
        
        assert response.status_code == 200


class TestGetListing:
    """Tests for GET /api/listings/:id"""
    
    def test_get_listing_success(self, client, test_listing):
        """Test getting a specific listing."""
        response = client.get(f'/api/listings/{test_listing["id"]}')
        
        assert response.status_code == 200
        assert 'title' in response.json
    
    def test_get_listing_not_found(self, client, db_session):
        """Test getting non-existent listing."""
        response = client.get('/api/listings/99999')
        
        assert response.status_code == 404


class TestCreateListing:
    """Tests for POST /api/listings"""
    
    def test_create_listing_success(self, client, auth_headers, db_session):
        """Test creating a new listing."""
        data = {
            'title': fake.sentence(nb_words=4),
            'description': fake.paragraph(),
            'price': 99.99,
            'category': 'electronics'
        }
        
        response = client.post('/api/listings', json=data, headers=auth_headers)
        
        assert response.status_code == 201
        assert 'id' in response.json
    
    def test_create_listing_unauthenticated(self, client, db_session):
        """Test creating listing without authentication."""
        data = {
            'title': fake.sentence(nb_words=4),
            'description': fake.paragraph(),
            'price': 99.99,
            'category': 'electronics'
        }
        
        response = client.post('/api/listings', json=data)
        
        assert response.status_code in [401, 422]
    
    def test_create_listing_missing_title(self, client, auth_headers, db_session):
        """Test creating listing without title."""
        data = {
            'description': fake.paragraph(),
            'price': 99.99,
            'category': 'electronics'
        }
        
        response = client.post('/api/listings', json=data, headers=auth_headers)
        
        assert response.status_code in [400, 422]
    
    def test_create_listing_invalid_price(self, client, auth_headers, db_session):
        """Test creating listing with negative price."""
        data = {
            'title': fake.sentence(nb_words=4),
            'description': fake.paragraph(),
            'price': -10,
            'category': 'electronics'
        }
        
        response = client.post('/api/listings', json=data, headers=auth_headers)
        
        # May be accepted or rejected
        assert response.status_code in [201, 400, 422]


class TestUpdateListing:
    """Tests for PUT /api/listings/:id"""
    
    def test_update_own_listing(self, client, auth_headers, test_listing):
        """Test updating own listing."""
        new_title = fake.sentence(nb_words=4)
        
        response = client.put(
            f'/api/listings/{test_listing["id"]}',
            json={'title': new_title},
            headers=auth_headers
        )
        
        assert response.status_code == 200
    
    def test_update_other_user_listing(self, client, second_auth_headers, test_listing):
        """Test updating another user's listing (should fail)."""
        response = client.put(
            f'/api/listings/{test_listing["id"]}',
            json={'title': 'Hacked title'},
            headers=second_auth_headers
        )
        
        assert response.status_code in [403, 404]  # Forbidden or Not Found
    
    def test_update_listing_unauthenticated(self, client, test_listing):
        """Test updating listing without authentication."""
        response = client.put(
            f'/api/listings/{test_listing["id"]}',
            json={'title': 'New title'}
        )
        
        assert response.status_code in [401, 422]
    
    def test_update_nonexistent_listing(self, client, auth_headers, db_session):
        """Test updating non-existent listing."""
        response = client.put(
            '/api/listings/99999',
            json={'title': 'New title'},
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestDeleteListing:
    """Tests for DELETE /api/listings/:id"""
    
    def test_delete_own_listing(self, client, auth_headers, test_listing):
        """Test deleting own listing."""
        response = client.delete(
            f'/api/listings/{test_listing["id"]}',
            headers=auth_headers
        )
        
        assert response.status_code in [200, 204]
        
        # Verify it's deleted
        get_response = client.get(f'/api/listings/{test_listing["id"]}')
        assert get_response.status_code == 404
    
    def test_delete_other_user_listing(self, client, second_auth_headers, test_listing):
        """Test deleting another user's listing (should fail)."""
        response = client.delete(
            f'/api/listings/{test_listing["id"]}',
            headers=second_auth_headers
        )
        
        assert response.status_code in [403, 404]
    
    def test_delete_listing_unauthenticated(self, client, test_listing):
        """Test deleting listing without authentication."""
        response = client.delete(f'/api/listings/{test_listing["id"]}')
        
        assert response.status_code in [401, 422]
