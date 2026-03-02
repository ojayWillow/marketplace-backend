"""Authentication routes for user registration and login."""

from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import User, Review, Listing, Offering, TaskRequest, TaskApplication
from app.utils import token_required
from datetime import datetime, timedelta
import traceback
import secrets
import string
from sqlalchemy.orm import joinedload
from sqlalchemy import func, or_

auth_bp = Blueprint('auth', __name__)


def generate_temp_username():
    """Generate a temporary username for new phone users."""
    random_suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    return f"user_{random_suffix}"


def generate_temp_password():
    """Generate a secure random password for phone-authenticated users."""
    return secrets.token_urlsafe(32)


def _ensure_supabase_user(user, phone=None, email=None):
    """Create a Supabase Auth user for a local user if they don't have one.

    This is called during phone/verify and complete-registration to ensure
    every user has a linked Supabase Auth account.

    IMPORTANT: Always pass user.email (even placeholder .kolab.local) so
    that Supabase user is created with an email. This is required because
    sign_in_with_password with phone is unreliable.

    Args:
        user: Local User model instance
        phone: Phone number (E.164) to register with
        email: Email to register with (including placeholder emails)

    Returns:
        Tuple of (supabase_user_id, password_used) or (supabase_user_id, None)
        password_used is the password set on the Supabase user (needed for session generation)
    """
    if user.supabase_user_id:
        return user.supabase_user_id, None

    try:
        from app.services.supabase_auth import (
            create_supabase_user,
            get_supabase_user_by_phone,
            get_supabase_user_by_email,
        )
    except (ImportError, RuntimeError):
        current_app.logger.debug('Supabase not available, skipping user creation')
        return None, None

    try:
        # Check if Supabase user already exists (e.g., created via another flow)
        existing = None
        if phone:
            existing = get_supabase_user_by_phone(phone)
        if not existing and email and not email.endswith('.kolab.local'):
            existing = get_supabase_user_by_email(email)

        if existing:
            user.supabase_user_id = str(existing.id)
            db.session.commit()
            current_app.logger.info(
                f'Linked existing Supabase user {existing.id} to local user {user.id}'
            )
            return user.supabase_user_id, None

        # Create new Supabase Auth user
        # ALWAYS include email (even placeholder) so sign_in_with_password works
        supabase_user, password_used = create_supabase_user(
            phone=phone,
            email=email or user.email,
            phone_confirm=True,
            email_confirm=True,
            user_metadata={
                'local_user_id': user.id,
                'username': user.username,
            },
        )

        user.supabase_user_id = str(supabase_user.id)
        db.session.commit()
        current_app.logger.info(
            f'Created Supabase user {supabase_user.id} for local user {user.id}'
        )
        return user.supabase_user_id, password_used

    except Exception as e:
        current_app.logger.error(
            f'Failed to create Supabase user for local user {user.id}: {e}'
        )
        current_app.logger.debug(traceback.format_exc())
        return None, None


def _get_supabase_session(user, phone=None, email=None, password=None):
    """Generate a Supabase session for a user.

    Attempts to generate a Supabase session using the given credentials.
    Always passes email (even placeholder) for reliable sign-in.
    Returns None if Supabase is not available or session generation fails.
    """
    supabase_user_id = user.supabase_user_id
    if not supabase_user_id:
        return None

    try:
        from app.services.supabase_auth import generate_supabase_session
        return generate_supabase_session(
            email=email or user.email,
            phone=phone or user.phone,
            password=password,
            supabase_user_id=supabase_user_id,
        )
    except Exception as e:
        current_app.logger.error(
            f'Supabase session generation failed for user {user.id}: {e}'
        )
        current_app.logger.debug(traceback.format_exc())
        return None


def _build_session_response(user, message, supabase_session=None, **extra):
    """Build a standardized auth response with Supabase session tokens.

    Requires a valid Supabase session. Returns 500 if session generation failed.
    """
    response_data = {
        'message': message,
        'user': user.to_dict(),
    }
    response_data.update(extra)

    if supabase_session:
        response_data['access_token'] = supabase_session['access_token']
        response_data['refresh_token'] = supabase_session['refresh_token']
        response_data['expires_in'] = supabase_session['expires_in']
        response_data['expires_at'] = supabase_session['expires_at']
        response_data['token_type'] = 'supabase'
    else:
        current_app.logger.error(
            f'Supabase session generation failed for user {user.id}'
        )
        return None

    return response_data


# ============================================================================
# FIREBASE PHONE AUTHENTICATION ENDPOINTS
# ============================================================================

@auth_bp.route('/phone/verify', methods=['POST'])
def phone_verify():
    """Firebase phone verification endpoint.
    
    Verifies a Firebase ID token and creates/logs in the user.
    Creates a Supabase Auth user and returns a Supabase session
    (access_token + refresh_token) for the frontend to use.
    """
    try:
        try:
            from app.services.firebase import verify_firebase_token, normalize_phone_number as firebase_normalize
        except ImportError:
            return jsonify({'error': 'Firebase authentication is not available.'}), 501
        
        data = request.get_json()
        
        if not data or 'idToken' not in data:
            return jsonify({'error': 'Firebase ID token is required'}), 400
        
        id_token = data['idToken']
        provided_phone = data.get('phoneNumber')
        
        try:
            firebase_data = verify_firebase_token(id_token)
        except ValueError as e:
            current_app.logger.warning(f"Firebase token verification failed: {e}")
            return jsonify({'error': str(e)}), 401
        
        verified_phone = firebase_data.get('phone_number')
        
        if not verified_phone:
            return jsonify({'error': 'Phone number not verified in token'}), 401
        
        normalized_phone = firebase_normalize(verified_phone)
        
        if provided_phone:
            normalized_provided = firebase_normalize(provided_phone)
            if normalized_provided != normalized_phone:
                current_app.logger.warning(
                    f"Phone mismatch: provided={normalized_provided}, token={normalized_phone}"
                )
                return jsonify({'error': 'Phone number mismatch'}), 401
        
        user = User.query.filter_by(phone=normalized_phone).first()
        is_new_user = False
        
        if user:
            if not user.is_active:
                return jsonify({'error': 'Account is disabled'}), 403
            
            user.phone_verified = True
            user.last_seen = datetime.utcnow()
            db.session.commit()
            
            current_app.logger.info(f"Phone login: existing user {user.id}")
        else:
            is_new_user = True
            temp_username = generate_temp_username()
            temp_email = f"{temp_username}@phone.kolab.local"
            
            user = User(
                username=temp_username,
                email=temp_email,
                phone=normalized_phone,
                phone_verified=True,
                is_verified=True
            )
            user.set_password(generate_temp_password())
            
            db.session.add(user)
            db.session.commit()
            
            current_app.logger.info(f"Phone login: new user created {user.id}")
        
        # --- Create/link Supabase Auth user ---
        # Always pass email (even placeholder) so Supabase user has an email
        # for reliable sign_in_with_password
        supabase_user_id, password_used = _ensure_supabase_user(
            user, phone=normalized_phone, email=user.email
        )
        
        # --- Generate Supabase session ---
        supabase_session = _get_supabase_session(
            user, phone=normalized_phone, email=user.email, password=password_used
        )
        
        response_data = _build_session_response(
            user, 'Phone verification successful',
            supabase_session, is_new_user=is_new_user
        )
        
        if response_data is None:
            return jsonify({'error': 'Authentication failed — could not generate session'}), 500
        
        return jsonify(response_data), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Phone verify error: {str(e)}")
        current_app.logger.debug(traceback.format_exc())
        return jsonify({'error': 'Phone verification failed'}), 500


@auth_bp.route('/phone/link', methods=['POST'])
@token_required
def phone_link(current_user_id):
    """Link a verified phone number to existing user account via Firebase.

    After linking, returns a fresh Supabase session so the frontend
    has up-to-date tokens reflecting the new phone number.
    """
    try:
        try:
            from app.services.firebase import verify_firebase_token, normalize_phone_number as firebase_normalize
        except ImportError:
            return jsonify({'error': 'Firebase authentication is not available.'}), 501
        
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user.is_active:
            return jsonify({'error': 'Account is disabled'}), 403
        
        data = request.get_json()
        
        if not data or 'idToken' not in data:
            return jsonify({'error': 'Firebase ID token is required'}), 400
        
        id_token = data['idToken']
        
        try:
            firebase_data = verify_firebase_token(id_token)
        except ValueError as e:
            current_app.logger.warning(f"Firebase token verification failed: {e}")
            return jsonify({'error': str(e)}), 401
        
        verified_phone = firebase_data.get('phone_number')
        
        if not verified_phone:
            return jsonify({'error': 'Phone number not verified in token'}), 401
        
        normalized_phone = firebase_normalize(verified_phone)
        
        existing_user = User.query.filter_by(phone=normalized_phone).first()
        if existing_user and existing_user.id != user.id:
            return jsonify({
                'error': 'This phone number is already linked to another account'
            }), 409
        
        user.phone = normalized_phone
        user.phone_verified = True
        user.is_verified = True
        user.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Ensure Supabase user exists with this phone
        supabase_user_id, password_used = _ensure_supabase_user(
            user, phone=normalized_phone, email=user.email
        )
        
        current_app.logger.info(f"Phone linked to user {user.id}: {normalized_phone}")
        
        # Generate fresh Supabase session
        supabase_session = _get_supabase_session(
            user, phone=normalized_phone, email=user.email, password=password_used
        )
        
        response_data = _build_session_response(
            user, 'Phone number verified and linked successfully',
            supabase_session
        )
        
        if response_data is None:
            return jsonify({'error': 'Phone linked but session refresh failed'}), 500
        
        return jsonify(response_data), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Phone link error: {str(e)}")
        current_app.logger.debug(traceback.format_exc())
        return jsonify({'error': 'Failed to link phone number'}), 500


@auth_bp.route('/complete-registration', methods=['PUT'])
@token_required
def complete_registration(current_user_id):
    """Complete onboarding for new users.
    
    This is the single onboarding endpoint that every new user goes through
    exactly once after phone verification. Collects all required profile
    information in one call.

    Returns a fresh Supabase session after onboarding so the frontend
    has tokens with updated user metadata.
    
    Required fields: username, first_name, last_name
    Optional fields: email, country, city, skills, bio, job_alert_preferences
    """
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Prevent completing onboarding twice
        if user.onboarding_completed:
            return jsonify({'error': 'Onboarding already completed'}), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # ── Required fields ─────────────────────────────────────────────
        
        # Username (required)
        if 'username' not in data or not data['username']:
            return jsonify({'error': 'Username is required'}), 400
        
        new_username = data['username'].lower().strip()
        
        if len(new_username) < 3:
            return jsonify({'error': 'Username must be at least 3 characters'}), 400
        
        if len(new_username) > 30:
            return jsonify({'error': 'Username must be less than 30 characters'}), 400
        
        if not new_username.replace('_', '').isalnum():
            return jsonify({'error': 'Username can only contain letters, numbers, and underscores'}), 400
        
        existing_user = User.query.filter_by(username=new_username).first()
        if existing_user and existing_user.id != user.id:
            return jsonify({'error': 'Username already exists'}), 409
        
        # First name (required)
        if 'first_name' not in data or not data.get('first_name', '').strip():
            return jsonify({'error': 'First name is required'}), 400
        
        # Last name (required)
        if 'last_name' not in data or not data.get('last_name', '').strip():
            return jsonify({'error': 'Last name is required'}), 400
        
        # ── Set all fields ──────────────────────────────────────────────
        
        user.username = new_username
        user.first_name = data['first_name'].strip()
        user.last_name = data['last_name'].strip()
        
        # Email (optional — replace placeholder if provided)
        new_email = data.get('email', '').lower().strip() if data.get('email') else None
        if new_email:
            if '@' not in new_email or '.' not in new_email:
                return jsonify({'error': 'Invalid email format'}), 400
            
            existing_email = User.query.filter_by(email=new_email).first()
            if existing_email and existing_email.id != user.id:
                return jsonify({'error': 'Email already exists'}), 409
            
            user.email = new_email
        
        # Country (optional)
        if 'country' in data:
            user.country = data['country'].strip() if data['country'] else None
        
        # City (optional)
        if 'city' in data:
            user.city = data['city'].strip() if data['city'] else None
        
        # Skills (optional — sets is_helper automatically)
        if 'skills' in data:
            if isinstance(data['skills'], list):
                user.skills = ','.join(data['skills'])
            else:
                user.skills = data['skills']
            # Auto-set helper status if skills provided
            if user.skills:
                user.is_helper = True
        
        # Bio (optional, max 500 chars)
        if 'bio' in data:
            bio_text = data['bio'].strip() if data['bio'] else None
            user.bio = bio_text[:500] if bio_text else None
        
        # Job alert preferences (optional)
        if 'job_alert_preferences' in data and isinstance(data['job_alert_preferences'], dict):
            user.set_job_alert_prefs(data['job_alert_preferences'])
        
        # ── Mark onboarding as completed ────────────────────────────────
        
        user.onboarding_completed = True
        user.username_changes_remaining = 1  # One free username change allowed
        user.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Ensure Supabase user is created/linked (email may have been set now)
        supabase_user_id, password_used = _ensure_supabase_user(
            user, phone=user.phone, email=user.email
        )
        
        # Generate fresh Supabase session with updated user data
        supabase_session = _get_supabase_session(
            user, phone=user.phone, email=user.email, password=password_used
        )
        
        response_data = _build_session_response(
            user, 'Registration completed successfully',
            supabase_session
        )
        
        if response_data is None:
            return jsonify({'error': 'Registration completed but session generation failed'}), 500
        
        return jsonify(response_data), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Complete registration error: {str(e)}")
        current_app.logger.debug(traceback.format_exc())
        return jsonify({'error': 'Failed to complete registration'}), 500


@auth_bp.route('/check-username/<username>', methods=['GET'])
def check_username(username):
    """Check if a username is available.
    
    Used by the frontend onboarding wizard for live availability checks.
    """
    try:
        clean = username.lower().strip()
        
        if len(clean) < 3:
            return jsonify({'available': False, 'reason': 'Too short'}), 200
        
        if len(clean) > 30:
            return jsonify({'available': False, 'reason': 'Too long'}), 200
        
        if not clean.replace('_', '').isalnum():
            return jsonify({'available': False, 'reason': 'Invalid characters'}), 200
        
        existing = User.query.filter_by(username=clean).first()
        
        return jsonify({
            'available': existing is None,
            'username': clean
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Check username error: {str(e)}")
        return jsonify({'error': 'Failed to check username'}), 500


# ============================================================================
# PROFILE & USER ENDPOINTS
# ============================================================================

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
        
        profile_data = user.to_dict()
        profile_data['reviews_count'] = user.review_count
        profile_data['average_rating'] = round(user.rating, 1) if user.rating else 0
        
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
        
        if 'username' in data:
            new_username = data['username'].lower().strip()
            if new_username != user.username:
                if user.username_changes_remaining <= 0:
                    return jsonify({'error': 'Username change limit reached. You cannot change your username again.'}), 403
                
                if len(new_username) < 3:
                    return jsonify({'error': 'Username must be at least 3 characters'}), 400
                if len(new_username) > 30:
                    return jsonify({'error': 'Username must be less than 30 characters'}), 400
                if not new_username.replace('_', '').isalnum():
                    return jsonify({'error': 'Username can only contain letters, numbers, and underscores'}), 400
                
                existing_user = User.query.filter_by(username=new_username).first()
                if existing_user and existing_user.id != user.id:
                    return jsonify({'error': 'Username already exists'}), 409
                
                user.username = new_username
                user.username_changes_remaining -= 1
        
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
        
        avg_rating = user.rating or 0
        review_count = user.review_count
        
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
