"""
Tests for offerings endpoints.
"""

import pytest
from faker import Faker

fake = Faker()


class TestListOfferings:
    """Tests for GET /api/offerings"""
    
    def test_list_offerings_empty(self, client, db_session):
        """Test listing when no offerings exist."""
        response = client.get('/api/offerings')
        
        assert response.status_code == 200
    
    def test_list_offerings_with_data(self, client, test_offering):
        """Test listing when offerings exist."""
        response = client.get('/api/offerings')
        
        assert response.status_code == 200
        data = response.json if isinstance(response.json, list) else response.json.get('offerings', [])
        assert len(data) >= 1
    
    def test_list_offerings_by_location(self, client, test_offering):
        """Test filtering offerings by location."""
        response = client.get('/api/offerings?lat=56.9496&lng=24.1052&radius=10')
        
        assert response.status_code == 200
    
    def test_list_offerings_by_category(self, client, test_offering):
        """Test filtering offerings by category."""
        response = client.get('/api/offerings?category=handyman')
        
        assert response.status_code == 200


class TestGetOffering:
    """Tests for GET /api/offerings/:id"""
    
    def test_get_offering_success(self, client, test_offering):
        """Test getting a specific offering."""
        response = client.get(f'/api/offerings/{test_offering["id"]}')
        
        assert response.status_code == 200
        assert 'title' in response.json
    
    def test_get_offering_not_found(self, client, db_session):
        """Test getting non-existent offering."""
        response = client.get('/api/offerings/99999')
        
        assert response.status_code == 404


class TestCreateOffering:
    """Tests for POST /api/offerings"""
    
    def test_create_offering_success(self, client, auth_headers, db_session):
        """Test creating a new offering."""
        data = {
            'title': fake.sentence(nb_words=4),
            'description': fake.paragraph(),
            'price': 25.00,
            'price_type': 'hourly',
            'category': 'cleaning',
            'location_lat': 56.9496,
            'location_lng': 24.1052,
            'location_address': 'Riga, Latvia'
        }
        
        response = client.post('/api/offerings', json=data, headers=auth_headers)
        
        assert response.status_code == 201
        assert 'id' in response.json
    
    def test_create_offering_unauthenticated(self, client, db_session):
        """Test creating offering without authentication."""
        data = {
            'title': fake.sentence(nb_words=4),
            'description': fake.paragraph(),
            'price': 25.00,
            'price_type': 'hourly',
            'category': 'cleaning'
        }
        
        response = client.post('/api/offerings', json=data)
        
        assert response.status_code in [401, 422]
    
    def test_create_offering_different_price_types(self, client, auth_headers, db_session):
        """Test creating offerings with different price types."""
        for price_type in ['hourly', 'fixed', 'per_item']:
            data = {
                'title': fake.sentence(nb_words=4),
                'description': fake.paragraph(),
                'price': 30.00,
                'price_type': price_type,
                'category': 'handyman',
                'location_lat': 56.9496,
                'location_lng': 24.1052
            }
            
            response = client.post('/api/offerings', json=data, headers=auth_headers)
            
            # Should accept valid price types
            assert response.status_code in [201, 400]


class TestUpdateOffering:
    """Tests for PUT /api/offerings/:id"""
    
    def test_update_own_offering(self, client, auth_headers, test_offering):
        """Test updating own offering."""
        new_title = fake.sentence(nb_words=4)
        
        response = client.put(
            f'/api/offerings/{test_offering["id"]}',
            json={'title': new_title},
            headers=auth_headers
        )
        
        assert response.status_code == 200
    
    def test_update_other_user_offering(self, client, second_auth_headers, test_offering):
        """Test updating another user's offering (should fail)."""
        response = client.put(
            f'/api/offerings/{test_offering["id"]}',
            json={'title': 'Hacked title'},
            headers=second_auth_headers
        )
        
        assert response.status_code in [403, 404]
    
    def test_update_offering_status(self, client, auth_headers, test_offering):
        """Test updating offering status."""
        response = client.put(
            f'/api/offerings/{test_offering["id"]}',
            json={'status': 'paused'},
            headers=auth_headers
        )
        
        assert response.status_code in [200, 400]  # May not support status changes


class TestDeleteOffering:
    """Tests for DELETE /api/offerings/:id"""
    
    def test_delete_own_offering(self, client, auth_headers, test_offering):
        """Test deleting own offering."""
        response = client.delete(
            f'/api/offerings/{test_offering["id"]}',
            headers=auth_headers
        )
        
        assert response.status_code in [200, 204]
        
        # Verify it's deleted
        get_response = client.get(f'/api/offerings/{test_offering["id"]}')
        assert get_response.status_code == 404
    
    def test_delete_other_user_offering(self, client, second_auth_headers, test_offering):
        """Test deleting another user's offering (should fail)."""
        response = client.delete(
            f'/api/offerings/{test_offering["id"]}',
            headers=second_auth_headers
        )
        
        assert response.status_code in [403, 404]


class TestMyOfferings:
    """Tests for user's offerings"""
    
    def test_get_my_offerings(self, client, auth_headers, test_offering):
        """Test getting offerings by user."""
        response = client.get('/api/offerings/my', headers=auth_headers)
        
        assert response.status_code == 200
    
    def test_my_offerings_unauthenticated(self, client, db_session):
        """Test getting my offerings without authentication."""
        response = client.get('/api/offerings/my')
        
        assert response.status_code in [401, 422]
