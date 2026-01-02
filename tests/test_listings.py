import pytest
from app.models import Listing


def test_create_listing(client, auth_tokens, test_listing):
    """Test creating a new listing."""
    access_token = auth_tokens['access_token']
    response = client.post('/api/listings',
                          json=test_listing,
                          headers={'Authorization': f'Bearer {access_token}'})
    assert response.status_code == 201
    data = response.get_json()
    assert 'id' in data
    assert data['title'] == test_listing['title']


def test_get_all_listings(client):
    """Test retrieving all listings."""
    response = client.get('/api/listings')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)


def test_get_listing_by_id(client, test_listing, auth_tokens):
    """Test retrieving a specific listing."""
    # Create a listing first
    access_token = auth_tokens['access_token']
    create_response = client.post('/api/listings',
                                  json=test_listing,
                                  headers={'Authorization': f'Bearer {access_token}'})
    listing_id = create_response.get_json()['id']
    
    # Retrieve the listing
    response = client.get(f'/api/listings/{listing_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data['id'] == listing_id


def test_update_listing(client, auth_tokens, test_listing):
    """Test updating a listing."""
    access_token = auth_tokens['access_token']
    
    # Create a listing
    create_response = client.post('/api/listings',
                                  json=test_listing,
                                  headers={'Authorization': f'Bearer {access_token}'})
    listing_id = create_response.get_json()['id']
    
    # Update the listing
    updated_data = {'title': 'Updated Product', 'price': 149.99}
    response = client.put(f'/api/listings/{listing_id}',
                         json=updated_data,
                         headers={'Authorization': f'Bearer {access_token}'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['title'] == 'Updated Product'


def test_delete_listing(client, auth_tokens, test_listing):
    """Test deleting a listing."""
    access_token = auth_tokens['access_token']
    
    # Create a listing
    create_response = client.post('/api/listings',
                                  json=test_listing,
                                  headers={'Authorization': f'Bearer {access_token}'})
    listing_id = create_response.get_json()['id']
    
    # Delete the listing
    response = client.delete(f'/api/listings/{listing_id}',
                            headers={'Authorization': f'Bearer {access_token}'})
    assert response.status_code == 204


def test_search_listings(client):
    """Test searching listings."""
    response = client.get('/api/listings/search?q=product')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
