"""Test suite for reviews functionality."""
import pytest
from datetime import datetime


class TestReviewsEndpoints:
    """Test cases for review-related API endpoints."""

    def test_create_review_success(self, client, auth_tokens, test_listing, db_session):
        """Test successful review creation."""
        # Get product_id from test listing
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

        assert response.status_code == 400

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

    def test_get_reviews_by_product(self, client, test_listing):
        """Test getting reviews for a specific product."""
        product_id = test_listing['id']

        response = client.get(f'/api/reviews/product/{product_id}')

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_get_reviews_nonexistent_product(self, client):
        """Test getting reviews for non-existent product."""
        response = client.get('/api/reviews/product/99999')

        # Should return 200 with empty list
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_update_review_success(self, client, auth_tokens, test_listing, db_session):
        """Test successful review update."""
        # Create a review first
        product_id = test_listing['id']
        review_data = {
            'product_id': product_id,
            'rating': 4,
            'comment': 'Good product'
        }
        
        create_response = client.post(
            '/api/reviews',
            json=review_data,
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )
        review_id = create_response.get_json()['review']['id']

        # Update the review
        update_data = {
            'rating': 5,
            'comment': 'Updated: Excellent product!'
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
        # Create a review first
        product_id = test_listing['id']
        review_data = {
            'product_id': product_id,
            'rating': 3,
            'comment': 'Average product'
        }
        
        create_response = client.post(
            '/api/reviews',
            json=review_data,
            headers={'Authorization': f"Bearer {auth_tokens['access_token']}"}
        )
        review_id = create_response.get_json()['review']['id']

        # Delete the review
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
