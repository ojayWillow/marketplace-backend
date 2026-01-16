"""Authentication routes for user registration and login."""

from flask import Blueprint, request, jsonify
from app import db
from app.models import User, Review, PasswordResetToken, Listing, Offering, TaskRequest, TaskApplication
from app.services.email import email_service
from app.utils import token_required
from app.utils.auth import SECRET_KEY  # Single source of truth for JWT secret
from datetime import datetime, timedelta
import jwt
import traceback
from sqlalchemy.orm import joinedload
from sqlalchemy import func

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user account."""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['username', 'email', 'password']):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Validate password length (consistent with reset-password)
        if len(data['password']) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 409
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 409
        
        user = User(
            username=data['username'],
            email=data['email'],
            first_name=data.get('first_name'),
            last_name=data.get('last_name')
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        # Generate token for auto-login after registration
        payload = {
            'user_id': user.id,
            'username': user.username,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
        
        return jsonify({
            'message': 'User registered successfully',
            'token': token,
            'user': user.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return JWT token."""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['email', 'password']):
            return jsonify({'error': 'Missing email or password'}), 400
        
        user = User.query.filter_by(email=data['email']).first()
        
        if not user or not user.check_password(data['password']):
            return jsonify({'error': 'Invalid email or password'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account is disabled'}), 403
        
        payload = {
            'user_id': user.id,
            'username': user.username,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
        
        return jsonify({
            'message': 'Login successful',
            'token': token,
            'user': user.to_dict()
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """
    Request a password reset email.
    Accepts email and sends reset link if user exists.
    """
    try:
        print("[AUTH] forgot-password endpoint called")
        data = request.get_json()
        print(f"[AUTH] Request data: {data}")
        
        if not data or 'email' not in data:
            return jsonify({'error': 'Email is required'}), 400
        
        email = data['email'].lower().strip()
        print(f"[AUTH] Looking up user with email: {email}")
        
        user = User.query.filter_by(email=email).first()
        print(f"[AUTH] User found: {user is not None}")
        
        # Always return success to prevent email enumeration
        # But only send email if user exists
        if user:
            try:
                print(f"[AUTH] Generating reset token for user_id: {user.id}")
                # Generate reset token
                reset_token = PasswordResetToken.generate_token(user.id)
                print(f"[AUTH] Reset token generated successfully")
                
                # Send reset email
                print(f"[AUTH] Sending password reset email...")
                email_service.send_password_reset_email(
                    to_email=user.email,
                    username=user.username,
                    reset_token=reset_token
                )
                print(f"[AUTH] Email send completed")
            except Exception as inner_e:
                print(f"[AUTH] Error in token/email process: {str(inner_e)}")
                print(traceback.format_exc())
                # Don't raise - still return success to prevent email enumeration
        
        # Return success regardless of whether user exists
        return jsonify({
            'message': 'If an account with that email exists, we have sent a password reset link.'
        }), 200
        
    except Exception as e:
        print(f"[AUTH] Forgot password error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': 'Failed to process request'}), 500


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """
    Reset password using token from email.
    Accepts token and new password.
    """
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['token', 'password']):
            return jsonify({'error': 'Token and password are required'}), 400
        
        token = data['token']
        new_password = data['password']
        
        # Validate password length
        if len(new_password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        # Verify token and get user_id
        user_id = PasswordResetToken.verify_token(token)
        
        if not user_id:
            return jsonify({'error': 'Invalid or expired reset link'}), 400
        
        # Get user and update password
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user.is_active:
            return jsonify({'error': 'Account is disabled'}), 403
        
        # Update password
        user.set_password(new_password)
        user.updated_at = datetime.utcnow()
        
        # Mark token as used
        PasswordResetToken.use_token(token)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Password has been reset successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"[AUTH] Reset password error: {str(e)}")
        return jsonify({'error': 'Failed to reset password'}), 500


@auth_bp.route('/profile', methods=['GET'])
@token_required
def get_profile(current_user_id):
    """Get current user profile."""
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user's reviews
        reviews_received = Review.query.filter_by(reviewed_user_id=current_user_id).all()
        
        # Calculate average rating
        avg_rating = 0
        if reviews_received:
            avg_rating = sum(r.rating for r in reviews_received) / len(reviews_received)
        
        user_data = user.to_dict()
        user_data['reviews_count'] = len(reviews_received)
        user_data['average_rating'] = round(avg_rating, 1)
        
        return jsonify(user_data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/profile/full', methods=['GET'])
@token_required
def get_profile_full(current_user_id):
    """Get complete profile data including all related entities in a single call.
    
    Returns profile, reviews, listings, offerings, created tasks, and applications.
    This is optimized for the profile page to load everything at once.
    
    Performance optimizations:
    - Uses joinedload for eager loading relationships
    - Batch-fetches related users in single queries
    - Uses grouped query for application counts
    """
    try:
        # Get user
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get reviews received with reviewer info (eager load reviewer relationship)
        reviews_received = Review.query\
            .filter_by(reviewed_user_id=current_user_id)\
            .options(joinedload(Review.reviewer))\
            .order_by(Review.created_at.desc()).all()
        
        # Calculate average rating
        avg_rating = 0
        if reviews_received:
            avg_rating = sum(r.rating for r in reviews_received) / len(reviews_received)
        
        # Build profile data
        profile_data = user.to_dict()
        profile_data['reviews_count'] = len(reviews_received)
        profile_data['average_rating'] = round(avg_rating, 1)
        
        # Get reviews with reviewer details (no extra queries - already eager loaded)
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
        
        # Get user's listings (use seller_id, not user_id)
        listings = Listing.query.filter_by(seller_id=current_user_id)\
            .order_by(Listing.created_at.desc()).all()
        listings_data = [listing.to_dict() for listing in listings]
        
        # Get user's offerings
        offerings = Offering.query.filter_by(creator_id=current_user_id)\
            .order_by(Offering.created_at.desc()).all()
        offerings_data = [offering.to_dict() for offering in offerings]
        
        # Get tasks created by user
        created_tasks = TaskRequest.query.filter_by(creator_id=current_user_id)\
            .order_by(TaskRequest.created_at.desc()).all()
        
        # Batch-fetch all assigned users in one query (instead of N queries)
        assigned_user_ids = [t.assigned_to_id for t in created_tasks if t.assigned_to_id]
        assigned_users_map = {}
        if assigned_user_ids:
            assigned_users = User.query.filter(User.id.in_(assigned_user_ids)).all()
            assigned_users_map = {u.id: u for u in assigned_users}
        
        # Batch-fetch pending application counts in one grouped query
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
            # Get pending count from pre-fetched map (default 0)
            task_dict['pending_applications_count'] = pending_counts.get(task.id, 0)
            
            # Get assigned worker info from pre-fetched map
            if task.assigned_to_id and task.assigned_to_id in assigned_users_map:
                assigned_user = assigned_users_map[task.assigned_to_id]
                task_dict['assigned_user'] = {
                    'id': assigned_user.id,
                    'username': assigned_user.username,
                    'avatar_url': assigned_user.avatar_url or assigned_user.profile_picture_url
                }
            
            created_tasks_data.append(task_dict)
        
        # Get user's applications (jobs they applied to) with task eager-loaded
        applications = TaskApplication.query.filter_by(applicant_id=current_user_id)\
            .options(joinedload(TaskApplication.task))\
            .order_by(TaskApplication.created_at.desc()).all()
        
        # Batch-fetch task creators for all applications
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
                # Get task creator info from pre-fetched map
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
        
    except Exception as e:
        print(f"[AUTH] Profile full error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile(current_user_id):
    """Update current user profile."""
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        # Basic profile fields
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
        
        # Helper-specific fields
        if 'is_helper' in data:
            user.is_helper = data['is_helper']
        if 'skills' in data:
            # Accept either comma-separated string or array
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
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user_public(user_id):
    """Get public profile of any user."""
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user's reviews
        reviews_received = Review.query.filter_by(reviewed_user_id=user_id).all()
        
        # Calculate average rating
        avg_rating = 0
        if reviews_received:
            avg_rating = sum(r.rating for r in reviews_received) / len(reviews_received)
        
        # Return only public info (no email, phone)
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
            'reviews_count': len(reviews_received),
            'average_rating': round(avg_rating, 1),
            'is_helper': user.is_helper,
            'skills': user.skills.split(',') if user.skills else [],
            'helper_categories': user.helper_categories.split(',') if user.helper_categories else [],
            'hourly_rate': user.hourly_rate,
            'created_at': user.created_at.isoformat()
        }
        
        return jsonify(public_data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/users/<int:user_id>/reviews', methods=['GET'])
def get_user_reviews(user_id):
    """Get reviews for a specific user."""
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Eager load reviewer to avoid N+1 queries
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
    except Exception as e:
        return jsonify({'error': str(e)}), 500
