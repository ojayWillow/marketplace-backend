"""Test suite for reviews functionality."""
import pytest
from datetime import datetime, timedelta


class TestReviewsEndpoints:
    """Test cases for review-related API endpoints."""

    def test_create_review_success(self, client, auth_tokens, test_listing, db_session):
        """Test successful review creation."""
        # Get product_id from test_listing
        product_id = test_listing['id']
        
        review_data = {
            'product_id': product_id,
            'rating': 5,
            'comment': 'Excellent product!'
        }
        
        response = client.post(
            '/api/reviews',
            json=review_data,
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['message'] == 'Review created successfully'
        assert 'review' in data
        assert data['review']['rating'] == 5
        assert data['review']['comment'] == 'Excellent product!'

    def test_create_review_missing_fields(self, client, auth_tokens):
        """Test review creation with missing required fields."""
        review_data = {
            'rating': 5
            # Missing product_id and comment
        }
        
        response = client.post(
            '/api/reviews',
            json=review_data,
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )
        
        assert response.status_code == 404

    def test_create_review_invalid_rating(self, client, auth_tokens, test_listing):
        """Test review creation with invalid rating value."""
        product_id = test_listing['id']
        
        review_data = {
            'product_id': product_id,
            'rating': 6,  # Invalid: should be 1-5
            'comment': 'Test comment'
        }
        
        response = client.post(
            '/api/reviews',
            json=review_data,
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )
        
        assert response.status_code == 400

    def test_get_reviews_by_product(self, client, test_listing, create_test_review):
        """Test retrieving reviews for a specific product."""
        product_id = test_listing['id']
        
        response = client.get(f'/api/reviews/{product_id}')
        
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_reviews_nonexistent_product(self, client):
        """Test retrieving reviews for non-existent product."""
        response = client.get('/api/reviews/99999')
        
        assert response.status_code == 404

    def test_update_review_success(self, client, auth_tokens, create_test_review):
        """Test successful review update."""
        review_id = create_test_review['id']
        
        update_data = {
            'rating': 4,
            'comment': 'Updated review comment'
        }
        
        response = client.put(
            f'/api/reviews/{review_id}',
            json=update_data,
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Review updated'

    def test_update_nonexistent_review(self, client, auth_tokens):
        """Test updating a non-existent review."""
        update_data = {
            'rating': 4,
            'comment': 'Updated comment'
        }
        
        response = client.put(
            '/api/reviews/99999',
            json=update_data,
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )
        
        assert response.status_code == 404

    def test_update_review_unauthorized(self, client, create_test_review, create_second_user):
        """Test updating review by unauthorized user."""
        review_id = create_test_review['id']
        second_user_token = create_second_user['token']
        
        update_data = {
            'rating': 1,
            'comment': 'Trying to modify someone elses review'
        }
        
        response = client.put(
            f'/api/reviews/{review_id}',
            json=update_data,
            headers={'Authorization': f"Bearer {second_user_token}"}
        )
        
        assert response.status_code == 401

    def test_delete_review_success(self, client, auth_tokens, create_test_review):
        """Test successful review deletion."""
        review_id = create_test_review['id']
        
        response = client.delete(
            f'/api/reviews/{review_id}',
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Review deleted'

    def test_delete_nonexistent_review(self, client, auth_tokens):
        """Test deleting a non-existent review."""
        response = client.delete(
            '/api/reviews/99999',
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )
        
        assert response.status_code == 404

    def test_review_requires_authentication(self, client, test_listing):
        """Test that creating a review requires authentication."""
        product_id = test_listing['id']
        
        review_data = {
            'product_id': product_id,
            'rating': 5,
            'comment': 'Test review'
        }
        
        response = client.post('/api/reviews', json=review_data)
        
        assert response.status_code == 401
