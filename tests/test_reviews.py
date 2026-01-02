"""Test suite for reviews functionality."""
import pytest
from datetime import datetime


class TestReviewsEndpoints:
    """Test cases for review-related API endpoints."""

    def test_create_review_success(self, client, auth_tokens, test_listing, db_session):
        """Test successful review creation."""
        listing_id = test_listing['id']

        review_data = {
            'reviewed_user_id': auth_tokens['user_id'],
            'listing_id': listing_id,
            'rating': 5,
            'content': 'Excellent product!'
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
        assert data['review']['content'] == 'Excellent product!'

    def test_create_review_missing_fields(self, client, auth_tokens):
        """Test review creation with missing required fields."""
        review_data = {
            'rating': 5
        }

        response = client.post(
            '/api/reviews',
            json=review_data,
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )

        assert response.status_code == 400

    def test_create_review_invalid_rating(self, client, auth_tokens, test_listing):
        """Test review creation with invalid rating value."""
        listing_id = test_listing['id']

        review_data = {
            'reviewed_user_id': auth_tokens['user_id'],
            'listing_id': listing_id,
            'rating': 6,
            'content': 'Test comment'
        }

        response = client.post(
            '/api/reviews',
            json=review_data,
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )

        assert response.status_code == 400

    def test_get_reviews_by_reviewer(self, client, auth_tokens, test_listing, db_session):
        """Test getting reviews by reviewer ID."""
        # Create a review first
        listing_id = test_listing['id']
        review_data = {
            'reviewed_user_id': auth_tokens['user_id'],
            'listing_id': listing_id,
            'rating': 5,
            'content': 'Test review'
        }
        
        client.post(
            '/api/reviews',
            json=review_data,
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )

        reviewer_id = auth_tokens['user_id']
        response = client.get(f'/api/reviews/{reviewer_id}')

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_get_reviews_nonexistent_reviewer(self, client):
        """Test getting reviews for non-existent reviewer."""
        response = client.get('/api/reviews/99999')

        assert response.status_code in (200, 404)
        if response.status_code == 200:
            data = response.get_json()
            assert isinstance(data, list)

    def test_update_review_success(self, client, auth_tokens, test_listing, db_session):
        """Test successful review update."""
        listing_id = test_listing['id']
        review_data = {
            'reviewed_user_id': auth_tokens['user_id'],
            'listing_id': listing_id,
            'rating': 4,
            'content': 'Good product'
        }
        
        create_response = client.post(
            '/api/reviews',
            json=review_data,
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )
        
        review_id = create_response.get_json()['review']['id']

        update_data = {
            'rating': 5,
            'content': 'Updated: Excellent product!'
        }

        response = client.put(
            f'/api/reviews/{review_id}',
            json=update_data,
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Review updated successfully'

    def test_delete_review_success(self, client, auth_tokens, test_listing, db_session):
        """Test successful review deletion."""
        listing_id = test_listing['id']
        review_data = {
            'reviewed_user_id': auth_tokens['user_id'],
            'listing_id': listing_id,
            'rating': 3,
            'content': 'Average product'
        }
        
        create_response = client.post(
            '/api/reviews',
            json=review_data,
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )
        
        review_id = create_response.get_json()['review']['id']

        response = client.delete(
            f'/api/reviews/{review_id}',
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Review deleted successfully'

    def test_delete_nonexistent_review(self, client, auth_tokens):
        """Test deleting non-existent review."""
        response = client.delete(
            '/api/reviews/99999',
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )

        assert response.status_code == 404
