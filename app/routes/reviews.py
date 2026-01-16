"""Review routes for ratings and feedback.

REVIEWS ARE RESTRICTED TO COMPLETED TRANSACTIONS ONLY.
Users can only review each other after:
- Completing a task (client reviews worker, worker reviews client)
- Completing a listing sale (buyer reviews seller, seller reviews buyer)
"""

from flask import Blueprint, request, jsonify
from sqlalchemy.orm import joinedload
from app import db
from app.models import Review, User, Listing, TaskRequest
from app.utils import token_required, token_optional
from datetime import datetime

reviews_bp = Blueprint('reviews', __name__, url_prefix='/api/reviews')

# Minimum characters required for review content
MIN_REVIEW_CONTENT_LENGTH = 10


def build_review_response(review):
    """Build review dict with reviewer and reviewed user info.
    
    Assumes reviewer and reviewed relationships are already loaded (via joinedload).
    """
    review_dict = review.to_dict()
    if review.reviewer:
        review_dict['reviewer'] = {
            'id': review.reviewer.id,
            'username': review.reviewer.username,
            'profile_picture_url': review.reviewer.profile_picture_url
        }
    if review.reviewed:
        review_dict['reviewed_user'] = {
            'id': review.reviewed.id,
            'username': review.reviewed.username,
            'profile_picture_url': review.reviewed.profile_picture_url
        }
    return review_dict


@reviews_bp.route('', methods=['GET'])
def get_reviews():
    """Get all reviews with optional filtering and pagination."""
    try:
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = min(per_page, 100)  # Cap at 100
        
        # Optional filters
        reviewer_id = request.args.get('reviewer_id')
        reviewed_user_id = request.args.get('reviewed_user_id')
        listing_id = request.args.get('listing_id')
        task_id = request.args.get('task_id')
        rating_min = request.args.get('rating_min', type=int)
        
        # Build query with eager loading to avoid N+1
        query = Review.query.options(
            joinedload(Review.reviewer),
            joinedload(Review.reviewed)
        )
        
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
        
        # Paginate
        paginated = query.order_by(Review.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        result = [build_review_response(review) for review in paginated.items]
        
        return jsonify({
            'reviews': result,
            'total': paginated.total,
            'page': page,
            'per_page': per_page,
            'has_more': paginated.has_next
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@reviews_bp.route('/task/<int:task_id>', methods=['GET'])
def get_task_reviews(task_id):
    """Get all reviews for a specific task."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Eager load reviewer and reviewed to avoid N+1 queries
        reviews = Review.query.options(
            joinedload(Review.reviewer),
            joinedload(Review.reviewed)
        ).filter_by(task_id=task_id).order_by(Review.created_at.desc()).all()
        
        result = [build_review_response(review) for review in reviews]
        
        return jsonify({
            'reviews': result,
            'total': len(result)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@reviews_bp.route('/task/<int:task_id>/can-review', methods=['GET'])
@token_required
def can_review_task(current_user_id, task_id):
    """Check if current user can review this task and who they can review."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Task must be completed
        if task.status != 'completed':
            return jsonify({
                'can_review': False,
                'reason': 'Task must be completed before leaving reviews'
            }), 200
        
        is_creator = task.creator_id == current_user_id
        is_worker = task.assigned_to_id == current_user_id
        
        if not is_creator and not is_worker:
            return jsonify({
                'can_review': False,
                'reason': 'You are not involved in this task'
            }), 200
        
        # Check if user already left a review
        existing_review = Review.query.filter_by(
            task_id=task_id,
            reviewer_id=current_user_id
        ).first()
        
        if existing_review:
            return jsonify({
                'can_review': False,
                'reason': 'You have already reviewed this task',
                'existing_review': existing_review.to_dict()
            }), 200
        
        # Determine who the user can review
        if is_creator:
            # Task creator can review the worker
            reviewee = User.query.get(task.assigned_to_id)
            review_type = 'client_review'  # Client reviewing worker
        else:
            # Worker can review the task creator
            reviewee = User.query.get(task.creator_id)
            review_type = 'worker_review'  # Worker reviewing client
        
        return jsonify({
            'can_review': True,
            'review_type': review_type,
            'reviewee': {
                'id': reviewee.id,
                'username': reviewee.username,
                'profile_picture_url': reviewee.profile_picture_url
            } if reviewee else None,
            'task': task.to_dict(),
            'min_content_length': MIN_REVIEW_CONTENT_LENGTH
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@reviews_bp.route('/task/<int:task_id>', methods=['POST'])
@token_required
def create_task_review(current_user_id, task_id):
    """Create a review for a completed task."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Task must be completed
        if task.status != 'completed':
            return jsonify({'error': 'Task must be completed before leaving reviews'}), 400
        
        is_creator = task.creator_id == current_user_id
        is_worker = task.assigned_to_id == current_user_id
        
        if not is_creator and not is_worker:
            return jsonify({'error': 'You are not involved in this task'}), 403
        
        # Check if user already left a review
        existing_review = Review.query.filter_by(
            task_id=task_id,
            reviewer_id=current_user_id
        ).first()
        
        if existing_review:
            return jsonify({'error': 'You have already reviewed this task'}), 400
        
        data = request.get_json()
        
        # Validate rating
        if not data or 'rating' not in data:
            return jsonify({'error': 'Rating is required'}), 400
        
        if not (1 <= data['rating'] <= 5):
            return jsonify({'error': 'Rating must be between 1 and 5'}), 400
        
        # Validate content - now required with minimum length
        content = data.get('content', '').strip()
        if not content:
            return jsonify({'error': 'Please write a review to share your experience'}), 400
        
        if len(content) < MIN_REVIEW_CONTENT_LENGTH:
            return jsonify({
                'error': f'Review must be at least {MIN_REVIEW_CONTENT_LENGTH} characters long',
                'min_length': MIN_REVIEW_CONTENT_LENGTH,
                'current_length': len(content)
            }), 400
        
        # Determine review type and reviewee
        if is_creator:
            reviewed_user_id = task.assigned_to_id
            review_type = 'client_review'
        else:
            reviewed_user_id = task.creator_id
            review_type = 'worker_review'
        
        review = Review(
            reviewer_id=current_user_id,
            reviewed_user_id=reviewed_user_id,
            rating=data['rating'],
            content=content,
            task_id=task_id,
            review_type=review_type
        )
        
        db.session.add(review)
        db.session.commit()
        
        # Reload with relationships for response
        review = Review.query.options(
            joinedload(Review.reviewer)
        ).get(review.id)
        
        review_dict = review.to_dict()
        if review.reviewer:
            review_dict['reviewer'] = {
                'id': review.reviewer.id,
                'username': review.reviewer.username,
                'profile_picture_url': review.reviewer.profile_picture_url
            }
        
        return jsonify({
            'message': 'Review submitted successfully',
            'review': review_dict
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@reviews_bp.route('/user/<int:user_id>/stats', methods=['GET'])
def get_user_review_stats(user_id):
    """Get review statistics for a user."""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get all reviews received by user
        reviews = Review.query.filter_by(reviewed_user_id=user_id).all()
        
        if not reviews:
            return jsonify({
                'user_id': user_id,
                'total_reviews': 0,
                'average_rating': None,
                'rating_breakdown': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                'as_worker': {'count': 0, 'average': None},
                'as_client': {'count': 0, 'average': None}
            }), 200
        
        total = len(reviews)
        avg = sum(r.rating for r in reviews) / total
        
        # Breakdown by rating
        breakdown = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for r in reviews:
            rating_int = int(round(r.rating))
            if rating_int in breakdown:
                breakdown[rating_int] += 1
        
        # Split by review type (as worker vs as client)
        worker_reviews = [r for r in reviews if r.review_type == 'client_review']
        client_reviews = [r for r in reviews if r.review_type == 'worker_review']
        
        worker_avg = sum(r.rating for r in worker_reviews) / len(worker_reviews) if worker_reviews else None
        client_avg = sum(r.rating for r in client_reviews) / len(client_reviews) if client_reviews else None
        
        return jsonify({
            'user_id': user_id,
            'total_reviews': total,
            'average_rating': round(avg, 1),
            'rating_breakdown': breakdown,
            'as_worker': {
                'count': len(worker_reviews),
                'average': round(worker_avg, 1) if worker_avg else None
            },
            'as_client': {
                'count': len(client_reviews),
                'average': round(client_avg, 1) if client_avg else None
            }
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@reviews_bp.route('/can-review-user/<int:user_id>', methods=['GET'])
@token_required
def can_review_user(current_user_id, user_id):
    """
    Check if current user can review another user.
    Returns list of completed transactions that allow reviewing.
    
    Reviews can only be left after completing a transaction together.
    """
    try:
        if current_user_id == user_id:
            return jsonify({
                'can_review': False,
                'reason': 'You cannot review yourself',
                'reviewable_transactions': []
            }), 200
        
        # Find completed tasks where both users were involved
        # Case 1: Current user was creator, other user was worker
        tasks_as_creator = TaskRequest.query.filter(
            TaskRequest.creator_id == current_user_id,
            TaskRequest.assigned_to_id == user_id,
            TaskRequest.status == 'completed'
        ).all()
        
        # Case 2: Current user was worker, other user was creator
        tasks_as_worker = TaskRequest.query.filter(
            TaskRequest.creator_id == user_id,
            TaskRequest.assigned_to_id == current_user_id,
            TaskRequest.status == 'completed'
        ).all()
        
        reviewable_transactions = []
        
        # Check each task if already reviewed
        for task in tasks_as_creator:
            existing_review = Review.query.filter_by(
                task_id=task.id,
                reviewer_id=current_user_id
            ).first()
            
            if not existing_review:
                reviewable_transactions.append({
                    'type': 'task',
                    'id': task.id,
                    'title': task.title,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                    'your_role': 'client',
                    'review_type': 'client_review'
                })
        
        for task in tasks_as_worker:
            existing_review = Review.query.filter_by(
                task_id=task.id,
                reviewer_id=current_user_id
            ).first()
            
            if not existing_review:
                reviewable_transactions.append({
                    'type': 'task',
                    'id': task.id,
                    'title': task.title,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                    'your_role': 'worker',
                    'review_type': 'worker_review'
                })
        
        # TODO: Add listing transactions when implemented
        
        return jsonify({
            'can_review': len(reviewable_transactions) > 0,
            'reason': 'No completed transactions with this user' if not reviewable_transactions else None,
            'reviewable_transactions': reviewable_transactions
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# REMOVED: Generic POST /api/reviews endpoint
# Reviews must now go through specific transaction endpoints:
# - POST /api/reviews/task/<task_id> for task reviews
# - POST /api/reviews/listing/<listing_id> for listing reviews (TODO)


@reviews_bp.route('/<int:review_id>', methods=['GET'])
def get_review(review_id):
    """Get a specific review by ID."""
    try:
        # Eager load reviewer to avoid extra query
        review = Review.query.options(
            joinedload(Review.reviewer)
        ).get(review_id)
        
        if not review:
            return jsonify({'error': 'Review not found'}), 404
        
        review_dict = review.to_dict()
        if review.reviewer:
            review_dict['reviewer'] = {
                'id': review.reviewer.id,
                'username': review.reviewer.username,
                'profile_picture_url': review.reviewer.profile_picture_url
            }
        
        return jsonify(review_dict), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@reviews_bp.route('/<int:review_id>', methods=['PUT'])
@token_required
def update_review(current_user_id, review_id):
    """Update a review (only within 24 hours of creation)."""
    try:
        review = Review.query.get(review_id)
        if not review:
            return jsonify({'error': 'Review not found'}), 404
        
        if review.reviewer_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Check if review is within edit window (24 hours)
        time_since_creation = datetime.utcnow() - review.created_at
        if time_since_creation.total_seconds() > 86400:  # 24 hours
            return jsonify({'error': 'Reviews can only be edited within 24 hours of creation'}), 400
        
        data = request.get_json()
        
        if 'rating' in data:
            if not (1 <= data['rating'] <= 5):
                return jsonify({'error': 'Rating must be between 1 and 5'}), 400
            review.rating = data['rating']
        
        if 'content' in data:
            content = data['content'].strip()
            if len(content) < MIN_REVIEW_CONTENT_LENGTH:
                return jsonify({
                    'error': f'Review must be at least {MIN_REVIEW_CONTENT_LENGTH} characters long',
                    'min_length': MIN_REVIEW_CONTENT_LENGTH,
                    'current_length': len(content)
                }), 400
            review.content = content
        
        review.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Review updated', 'review': review.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@reviews_bp.route('/<int:review_id>', methods=['DELETE'])
@token_required
def delete_review(current_user_id, review_id):
    """Delete a review (only within 24 hours of creation)."""
    try:
        review = Review.query.get(review_id)
        if not review:
            return jsonify({'error': 'Review not found'}), 404
        
        if review.reviewer_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Check if review is within delete window (24 hours)
        time_since_creation = datetime.utcnow() - review.created_at
        if time_since_creation.total_seconds() > 86400:  # 24 hours
            return jsonify({'error': 'Reviews can only be deleted within 24 hours of creation'}), 400
        
        db.session.delete(review)
        db.session.commit()
        
        return jsonify({'message': 'Review deleted'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
