"""Authentication routes for user registration and login."""

from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import User, Review, PasswordResetToken, Listing, Offering, TaskRequest, TaskApplication
from app.services.email import email_service
from app.services.firebase import verify_firebase_token, normalize_phone_number
from app.utils import token_required
from app.utils.auth import SECRET_KEY  # Single source of truth for JWT secret
from datetime import datetime, timedelta
import jwt
import traceback
import secrets
import string
from sqlalchemy.orm import joinedload
from sqlalchemy import func

auth_bp = Blueprint('auth', __name__)


def generate_temp_username():
    """Generate a temporary username for new phone users."""
    random_suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    return f"user_{random_suffix}"


def generate_temp_password():
    """Generate a secure random password for phone-authenticated users."""
    return secrets.token_urlsafe(32)


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


# ============================================================================
# PHONE AUTHENTICATION ENDPOINTS
# ============================================================================

@auth_bp.route('/phone/verify', methods=['POST'])
def phone_verify():
    """Verify Firebase phone authentication and create/login user.
    
    This endpoint receives a Firebase ID token after the user has completed
    phone verification on the frontend. It:
    1. Verifies the Firebase token
    2. Extracts the verified phone number
    3. Creates a new user or logs in existing user
    4. Returns our app's JWT token
    
    Request body:
        - idToken: Firebase ID token from frontend
        - phoneNumber: Phone number (for verification, must match token)
        
    Returns:
        - access_token: Our app's JWT for API calls
        - user: User object
    """
    try:
        data = request.get_json()
        
        if not data or 'idToken' not in data:
            return jsonify({'error': 'Firebase ID token is required'}), 400
        
        id_token = data['idToken']
        provided_phone = data.get('phoneNumber')
        
        # Verify Firebase token
        try:
            firebase_data = verify_firebase_token(id_token)
        except ValueError as e:
            current_app.logger.warning(f"Firebase token verification failed: {e}")
            return jsonify({'error': str(e)}), 401
        
        # Get verified phone number from Firebase
        verified_phone = firebase_data.get('phone_number')
        
        if not verified_phone:
            return jsonify({'error': 'Phone number not verified in token'}), 401
        
        # Normalize phone number
        normalized_phone = normalize_phone_number(verified_phone)
        
        # Optional: Verify provided phone matches token (extra security)
        if provided_phone:
            normalized_provided = normalize_phone_number(provided_phone)
            if normalized_provided != normalized_phone:
                current_app.logger.warning(
                    f"Phone mismatch: provided={normalized_provided}, token={normalized_phone}"
                )
                return jsonify({'error': 'Phone number mismatch'}), 401
        
        # Find or create user by phone number
        user = User.query.filter_by(phone=normalized_phone).first()
        
        if user:
            # Existing user - update phone verification status
            if not user.is_active:
                return jsonify({'error': 'Account is disabled'}), 403
            
            user.phone_verified = True
            user.last_seen = datetime.utcnow()
            db.session.commit()
            
            current_app.logger.info(f"Phone login: existing user {user.id}")
        else:
            # New user - create account with phone
            temp_username = generate_temp_username()
            temp_email = f"{temp_username}@phone.tirgus.local"  # Placeholder email
            
            user = User(
                username=temp_username,
                email=temp_email,
                phone=normalized_phone,
                phone_verified=True,
                is_verified=True  # Phone-verified users are considered verified
            )
            # Set a random password (user won't use it for phone auth)
            user.set_password(generate_temp_password())
            
            db.session.add(user)
            db.session.commit()
            
            current_app.logger.info(f"Phone login: new user created {user.id}")
        
        # Generate our JWT token
        payload = {
            'user_id': user.id,
            'username': user.username,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
        
        return jsonify({
            'message': 'Phone verification successful',
            'access_token': token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Phone verify error: {str(e)}")
        current_app.logger.debug(traceback.format_exc())
        return jsonify({'error': 'Phone verification failed'}), 500


@auth_bp.route('/phone/link', methods=['POST'])
@token_required
def phone_link(current_user_id):
    """Link a verified phone number to an existing user account.
    
    This is for users who registered with email and need to add phone verification.
    
    Request body:
        - idToken: Firebase ID token from frontend
        - phoneNumber: Phone number (for verification)
        
    Returns:
        - user: Updated user object with phone_verified=true
    """
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user.is_active:
            return jsonify({'error': 'Account is disabled'}), 403
        
        data = request.get_json()
        
        if not data or 'idToken' not in data:
            return jsonify({'error': 'Firebase ID token is required'}), 400
        
        id_token = data['idToken']
        
        # Verify Firebase token
        try:
            firebase_data = verify_firebase_token(id_token)
        except ValueError as e:
            current_app.logger.warning(f"Firebase token verification failed: {e}")
            return jsonify({'error': str(e)}), 401
        
        # Get verified phone number from Firebase
        verified_phone = firebase_data.get('phone_number')
        
        if not verified_phone:
            return jsonify({'error': 'Phone number not verified in token'}), 401
        
        # Normalize phone number
        normalized_phone = normalize_phone_number(verified_phone)
        
        # Check if this phone is already linked to another account
        existing_user = User.query.filter_by(phone=normalized_phone).first()
        if existing_user and existing_user.id != user.id:
            return jsonify({
                'error': 'This phone number is already linked to another account'
            }), 409
        
        # Link phone to user account
        user.phone = normalized_phone
        user.phone_verified = True
        user.is_verified = True  # Mark user as verified
        user.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        current_app.logger.info(f"Phone linked to user {user.id}: {normalized_phone}")
        
        return jsonify({
            'message': 'Phone number verified and linked successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Phone link error: {str(e)}")
        current_app.logger.debug(traceback.format_exc())
        return jsonify({'error': 'Failed to link phone number'}), 500


@auth_bp.route('/phone/check/<phone>', methods=['GET'])
def phone_check(phone):
    """Check if a phone number is already registered.
    
    Useful for frontend to determine whether to show "Login" or "Register" flow.
    
    Args:
        phone: Phone number to check (URL parameter)
        
    Returns:
        - exists: boolean indicating if phone is registered
    """
    try:
        normalized_phone = normalize_phone_number(phone)
        
        if not normalized_phone:
            return jsonify({'error': 'Invalid phone number'}), 400
        
        user = User.query.filter_by(phone=normalized_phone).first()
        
        return jsonify({
            'exists': user is not None,
            'phone': normalized_phone
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Phone check error: {str(e)}")
        return jsonify({'error': 'Failed to check phone number'}), 500


@auth_bp.route('/complete-registration', methods=['PUT'])
@token_required
def complete_registration(current_user_id):
    """Complete registration for phone-authenticated users.
    
    New phone users get a temporary username. This endpoint lets them
    set their actual username and optionally add an email.
    
    Request body:
        - username: Desired username (required)
        - email: Email address (optional)
        
    Returns:
        - access_token: New JWT with updated username
        - user: Updated user object
    """
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        if not data or 'username' not in data:
            return jsonify({'error': 'Username is required'}), 400
        
        new_username = data['username'].lower().strip()
        new_email = data.get('email', '').lower().strip() if data.get('email') else None
        
        # Validate username
        if len(new_username) < 3:
            return jsonify({'error': 'Username must be at least 3 characters'}), 400
        
        if len(new_username) > 30:
            return jsonify({'error': 'Username must be less than 30 characters'}), 400
        
        if not new_username.replace('_', '').isalnum():
            return jsonify({'error': 'Username can only contain letters, numbers, and underscores'}), 400
        
        # Check if username is taken (by another user)
        existing_user = User.query.filter_by(username=new_username).first()
        if existing_user and existing_user.id != user.id:
            return jsonify({'error': 'Username already exists'}), 409
        
        # Check email if provided
        if new_email:
            # Basic email validation
            if '@' not in new_email or '.' not in new_email:
                return jsonify({'error': 'Invalid email format'}), 400
            
            existing_email = User.query.filter_by(email=new_email).first()
            if existing_email and existing_email.id != user.id:
                return jsonify({'error': 'Email already exists'}), 409
            
            user.email = new_email
        
        # Update username
        user.username = new_username
        user.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Generate new token with updated username
        payload = {
            'user_id': user.id,
            'username': user.username,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
        
        return jsonify({
            'message': 'Registration completed successfully',
            'access_token': token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Complete registration error: {str(e)}")
        return jsonify({'error': 'Failed to complete registration'}), 500


# ============================================================================
# EXISTING ENDPOINTS (unchanged)
# ============================================================================

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Request a password reset email."""
    try:
        data = request.get_json()
        
        if not data or 'email' not in data:
            return jsonify({'error': 'Email is required'}), 400
        
        email = data['email'].lower().strip()
        current_app.logger.debug(f"Password reset requested for email: {email}")
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            try:
                reset_token = PasswordResetToken.generate_token(user.id)
                current_app.logger.debug(f"Reset token generated for user_id: {user.id}")
                
                email_service.send_password_reset_email(
                    to_email=user.email,
                    username=user.username,
                    reset_token=reset_token
                )
                current_app.logger.debug(f"Password reset email sent to user_id: {user.id}")
            except Exception as inner_e:
                current_app.logger.error(f"Error in password reset process: {str(inner_e)}")
                current_app.logger.debug(traceback.format_exc())
        
        return jsonify({
            'message': 'If an account with that email exists, we have sent a password reset link.'
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Forgot password error: {str(e)}")
        return jsonify({'error': 'Failed to process request'}), 500


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Reset password using token from email."""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['token', 'password']):
            return jsonify({'error': 'Token and password are required'}), 400
        
        token = data['token']
        new_password = data['password']
        
        if len(new_password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        user_id = PasswordResetToken.verify_token(token)
        
        if not user_id:
            return jsonify({'error': 'Invalid or expired reset link'}), 400
        
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user.is_active:
            return jsonify({'error': 'Account is disabled'}), 403
        
        user.set_password(new_password)
        user.updated_at = datetime.utcnow()
        
        PasswordResetToken.use_token(token)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Password has been reset successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Reset password error: {str(e)}")
        return jsonify({'error': 'Failed to reset password'}), 500


@auth_bp.route('/profile', methods=['GET'])
@token_required
def get_profile(current_user_id):
    """Get current user profile."""
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        reviews_received = Review.query.filter_by(reviewed_user_id=current_user_id).all()
        
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
    """Get complete profile data including all related entities."""
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        reviews_received = Review.query\
            .filter_by(reviewed_user_id=current_user_id)\
            .options(joinedload(Review.reviewer))\
            .order_by(Review.created_at.desc()).all()
        
        avg_rating = 0
        if reviews_received:
            avg_rating = sum(r.rating for r in reviews_received) / len(reviews_received)
        
        profile_data = user.to_dict()
        profile_data['reviews_count'] = len(reviews_received)
        profile_data['average_rating'] = round(avg_rating, 1)
        
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
        
    except Exception as e:
        current_app.logger.error(f"Profile full error: {str(e)}")
        current_app.logger.debug(traceback.format_exc())
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
        
        reviews_received = Review.query.filter_by(reviewed_user_id=user_id).all()
        
        avg_rating = 0
        if reviews_received:
            avg_rating = sum(r.rating for r in reviews_received) / len(reviews_received)
        
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
