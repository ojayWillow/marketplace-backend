"""User profile routes: get/update own profile, public profiles, reviews."""

from flask import request, jsonify, current_app
from app import db
from app.models import User, Review, Listing, Offering, TaskRequest, TaskApplication
from app.utils import token_required
from app.routes.auth import auth_bp
from app.routes.auth.core import _validate_profile_data
from datetime import datetime
from sqlalchemy.orm import joinedload
from sqlalchemy import func, or_


@auth_bp.route('/profile', methods=['GET'])
@token_required
def get_profile(current_user_id):
    """Get current user profile.
    
    Uses user.rating and user.review_count which are now efficient
    single-query properties (func.avg + func.count, cached per instance).
    """
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user_data = user.to_dict()
        user_data['reviews_count'] = user.review_count
        user_data['average_rating'] = round(user.rating, 1) if user.rating else 0
        
        return jsonify(user_data), 200
    except Exception:
        raise


@auth_bp.route('/profile/full', methods=['GET'])
@token_required
def get_profile_full(current_user_id):
    """Get complete profile data including all related entities."""
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Use efficient properties for rating stats
        profile_data = user.to_dict()
        profile_data['reviews_count'] = user.review_count
        profile_data['average_rating'] = round(user.rating, 1) if user.rating else 0
        
        # Load reviews with reviewer data (eagerly) for the reviews list
        reviews_received = Review.query\
            .filter_by(reviewed_user_id=current_user_id)\
            .options(joinedload(Review.reviewer))\
            .order_by(Review.created_at.desc()).all()
        
        reviews_data = []
        for review in reviews_received:
            review_dict = review.to_dict()
            if review.reviewer:
                review_dict['reviewer_name'] = review.reviewer.username
                review_dict['reviewer_avatar'] = review.reviewer.avatar_url
            else:
                review_dict['reviewer_name'] = 'Unknown'
                review_dict['reviewer_avatar'] = None
            reviews_data.append(review_dict)
        
        listings = Listing.query.filter_by(seller_id=current_user_id)\
            .order_by(Listing.created_at.desc()).all()
        listings_data = [listing.to_dict() for listing in listings]
        
        offerings = Offering.query.filter_by(creator_id=current_user_id)\
            .order_by(Offering.created_at.desc()).all()
        offerings_data = [offering.to_dict() for offering in offerings]
        
        created_tasks = TaskRequest.query.filter_by(creator_id=current_user_id)\
            .order_by(TaskRequest.created_at.desc()).all()
        
        assigned_user_ids = [t.assigned_to_id for t in created_tasks if t.assigned_to_id]
        assigned_users_map = {}
        if assigned_user_ids:
            assigned_users = User.query.filter(User.id.in_(assigned_user_ids)).all()
            assigned_users_map = {u.id: u for u in assigned_users}
        
        task_ids = [t.id for t in created_tasks]
        pending_counts = {}
        if task_ids:
            counts = db.session.query(
                TaskApplication.task_id,
                func.count(TaskApplication.id)
            ).filter(
                TaskApplication.task_id.in_(task_ids),
                TaskApplication.status == 'pending'
            ).group_by(TaskApplication.task_id).all()
            pending_counts = {task_id: count for task_id, count in counts}
        
        created_tasks_data = []
        for task in created_tasks:
            task_dict = task.to_dict()
            task_dict['pending_applications_count'] = pending_counts.get(task.id, 0)
            
            if task.assigned_to_id and task.assigned_to_id in assigned_users_map:
                assigned_user = assigned_users_map[task.assigned_to_id]
                task_dict['assigned_user'] = {
                    'id': assigned_user.id,
                    'username': assigned_user.username,
                    'avatar_url': assigned_user.avatar_url or assigned_user.profile_picture_url
                }
            
            created_tasks_data.append(task_dict)
        
        applications = TaskApplication.query.filter_by(applicant_id=current_user_id)\
            .options(joinedload(TaskApplication.task))\
            .order_by(TaskApplication.created_at.desc()).all()
        
        creator_ids = [app.task.creator_id for app in applications if app.task and app.task.creator_id]
        creators_map = {}
        if creator_ids:
            creators = User.query.filter(User.id.in_(creator_ids)).all()
            creators_map = {u.id: u for u in creators}
        
        applications_data = []
        for app in applications:
            app_dict = app.to_dict()
            if app.task:
                task_dict = app.task.to_dict()
                if app.task.creator_id and app.task.creator_id in creators_map:
                    creator = creators_map[app.task.creator_id]
                    task_dict['creator'] = {
                        'id': creator.id,
                        'username': creator.username,
                        'avatar_url': creator.avatar_url or creator.profile_picture_url
                    }
                app_dict['task'] = task_dict
            applications_data.append(app_dict)
        
        return jsonify({
            'profile': profile_data,
            'reviews': reviews_data,
            'listings': listings_data,
            'offerings': offerings_data,
            'created_tasks': created_tasks_data,
            'applications': applications_data
        }), 200
        
    except Exception:
        raise


@auth_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile(current_user_id):
    """Update current user profile."""
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate all fields before applying any changes
        validation_error = _validate_profile_data(data)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'bio' in data:
            user.bio = data['bio']
        if 'phone' in data:
            user.phone = data['phone']
        if 'city' in data:
            user.city = data['city']
        if 'country' in data:
            user.country = data['country']
        if 'avatar_url' in data:
            user.avatar_url = data['avatar_url']
        if 'profile_picture_url' in data:
            user.profile_picture_url = data['profile_picture_url']
        
        if 'is_helper' in data:
            user.is_helper = data['is_helper']
        if 'skills' in data:
            if isinstance(data['skills'], list):
                user.skills = ','.join(data['skills'])
            else:
                user.skills = data['skills']
        if 'helper_categories' in data:
            if isinstance(data['helper_categories'], list):
                user.helper_categories = ','.join(data['helper_categories'])
            else:
                user.helper_categories = data['helper_categories']
        if 'hourly_rate' in data:
            user.hourly_rate = data['hourly_rate']
        if 'latitude' in data:
            user.latitude = data['latitude']
        if 'longitude' in data:
            user.longitude = data['longitude']
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Profile updated successfully',
            'user': user.to_dict()
        }), 200
    except Exception:
        db.session.rollback()
        raise


@auth_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user_public(user_id):
    """Get public profile of any user.
    
    Uses efficient batch queries for review stats and completed tasks
    instead of loading all Review rows into memory.
    """
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Efficient: uses cached single-query property
        avg_rating = user.rating or 0
        review_count = user.review_count
        
        # Efficient: single COUNT query
        completed_tasks_count = TaskRequest.query.filter(
            or_(
                TaskRequest.creator_id == user_id,
                TaskRequest.assigned_to_id == user_id
            ),
            TaskRequest.status == 'completed'
        ).count()
        
        public_data = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'avatar_url': user.avatar_url,
            'profile_picture_url': user.profile_picture_url,
            'bio': user.bio,
            'city': user.city,
            'country': user.country,
            'is_verified': user.is_verified,
            'reputation_score': user.reputation_score,
            'completion_rate': user.completion_rate,
            'reviews_count': review_count,
            'average_rating': round(avg_rating, 1),
            'completed_tasks_count': completed_tasks_count,
            'is_helper': user.is_helper,
            'skills': user.skills.split(',') if user.skills else [],
            'helper_categories': user.helper_categories.split(',') if user.helper_categories else [],
            'hourly_rate': user.hourly_rate,
            'created_at': user.created_at.isoformat()
        }
        
        return jsonify(public_data), 200
    except Exception:
        raise


@auth_bp.route('/users/<int:user_id>/reviews', methods=['GET'])
def get_user_reviews(user_id):
    """Get reviews for a specific user."""
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        reviews = Review.query\
            .filter_by(reviewed_user_id=user_id)\
            .options(joinedload(Review.reviewer))\
            .order_by(Review.created_at.desc()).all()
        
        reviews_data = []
        for review in reviews:
            review_dict = review.to_dict()
            if review.reviewer:
                review_dict['reviewer_name'] = review.reviewer.username
                review_dict['reviewer_avatar'] = review.reviewer.avatar_url
            else:
                review_dict['reviewer_name'] = 'Unknown'
                review_dict['reviewer_avatar'] = None
            reviews_data.append(review_dict)
        
        return jsonify({
            'reviews': reviews_data,
            'total': len(reviews_data)
        }), 200
    except Exception:
        raise
