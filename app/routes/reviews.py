"""Review routes for ratings and feedback."""

from flask import Blueprint, request, jsonify
from app import db
from app.models import Review, User, Listing, TaskRequest
from functools import wraps
import jwt
import os
from datetime import datetime

reviews_bp = Blueprint('reviews', __name__, url_prefix='/api/reviews')
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')

# JWT token verification
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            token = token.split(' ')[1]
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            current_user_id = data['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except Exception as e:
            return jsonify({'error': 'Token is invalid'}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorated

@reviews_bp.route('', methods=['GET'])
def get_reviews():
    """Get all reviews with optional filtering."""
    try:
        # Optional filters
        reviewer_id = request.args.get('reviewer_id')
        reviewed_user_id = request.args.get('reviewed_user_id')
        listing_id = request.args.get('listing_id')
        task_id = request.args.get('task_id')
        rating_min = request.args.get('rating_min', type=int)
        
        query = Review.query
        
        if reviewer_id:
            query = query.filter_by(reviewer_id=reviewer_id)
        if reviewed_user_id:
            query = query.filter_by(reviewed_user_id=reviewed_user_id)
        if listing_id:
            query = query.filter_by(listing_id=listing_id)
        if task_id:
            query = query.filter_by(task_id=task_id)
        if rating_min:
            query = query.filter(Review.rating >= rating_min)
        
        reviews = query.all()
        return jsonify([review.to_dict() for review in reviews]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reviews_bp.route('', methods=['POST'])
@token_required
def create_review(current_user_id):
    """Create a new review."""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['rating', 'reviewed_user_id']):
            return jsonify({'error': 'Missing required fields'}), 400
        
        if not (1 <= data['rating'] <= 5):
            return jsonify({'error': 'Rating must be between 1 and 5'}), 400
        
        review = Review(
            reviewer_id=current_user_id,
            reviewed_user_id=data['reviewed_user_id'],
            rating=data['rating'],
            comment=data.get('comment'),
            listing_id=data.get('listing_id'),
            task_id=data.get('task_id')
        )
        
        db.session.add(review)
        db.session.commit()
        
        return jsonify({'message': 'Review created successfully', 'review': review.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@reviews_bp.route('/<int:review_id>', methods=['GET'])
def get_review(review_id):
    """Get a specific review by ID."""
    try:
        review = Review.query.get(review_id)
        if not review:
            return jsonify({'error': 'Review not found'}), 404
        
        return jsonify(review.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reviews_bp.route('/<int:review_id>', methods=['PUT'])
@token_required
def update_review(current_user_id, review_id):
    """Update a review."""
    try:
        review = Review.query.get(review_id)
        if not review:
            return jsonify({'error': 'Review not found'}), 404
        
        if review.reviewer_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        if 'rating' in data:
            if not (1 <= data['rating'] <= 5):
                return jsonify({'error': 'Rating must be between 1 and 5'}), 400
            review.rating = data['rating']
        
        if 'comment' in data:
            review.comment = data['comment']
        
        review.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Review updated', 'review': review.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@reviews_bp.route('/<int:review_id>', methods=['DELETE'])
@token_required
def delete_review(current_user_id, review_id):
    """Delete a review."""
    try:
        review = Review.query.get(review_id)
        if not review:
            return jsonify({'error': 'Review not found'}), 404
        
        if review.reviewer_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        db.session.delete(review)
        db.session.commit()
        
        return jsonify({'message': 'Review deleted'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
