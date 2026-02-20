"""Core authentication routes: registration and login."""

from flask import request, jsonify, current_app
from app import db, limiter
from app.models import User
from app.routes.auth import auth_bp
from datetime import datetime, timedelta
import jwt
import re
import secrets
import string

# ---------------------------------------------------------------------------
# Shared constants & helpers (used by sibling modules via import)
# ---------------------------------------------------------------------------

# Email validation regex
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# Username validation: 3-30 chars, alphanumeric + underscores
USERNAME_REGEX = re.compile(r'^[a-zA-Z0-9_]{3,30}$')

# Allowed fields for profile update (prevent mass assignment)
PROFILE_ALLOWED_FIELDS = {
    'first_name', 'last_name', 'bio', 'phone', 'city', 'country',
    'avatar_url', 'profile_picture_url', 'is_helper', 'skills',
    'helper_categories', 'hourly_rate', 'latitude', 'longitude'
}


def _get_secret_key():
    """Get JWT secret from Flask app config (single source of truth)."""
    return current_app.config['JWT_SECRET_KEY']


def generate_temp_username():
    """Generate a temporary username for new phone users."""
    random_suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    return f"user_{random_suffix}"


def generate_temp_password():
    """Generate a secure random password for phone-authenticated users."""
    return secrets.token_urlsafe(32)


def _validate_profile_data(data):
    """Validate profile update fields. Returns error message or None."""
    # Check for unknown fields
    unknown = set(data.keys()) - PROFILE_ALLOWED_FIELDS
    if unknown:
        return f"Unknown fields: {', '.join(unknown)}"
    
    # String length limits
    length_limits = {
        'first_name': 50,
        'last_name': 50,
        'bio': 500,
        'phone': 20,
        'city': 100,
        'country': 100,
        'avatar_url': 500,
        'profile_picture_url': 500,
    }
    
    for field, max_len in length_limits.items():
        if field in data and data[field] is not None:
            if not isinstance(data[field], str):
                return f"{field} must be a string"
            if len(data[field]) > max_len:
                return f"{field} must be less than {max_len} characters"
    
    # Numeric validations
    if 'hourly_rate' in data and data['hourly_rate'] is not None:
        try:
            rate = float(data['hourly_rate'])
            if rate < 0 or rate > 10000:
                return "hourly_rate must be between 0 and 10000"
        except (TypeError, ValueError):
            return "hourly_rate must be a number"
    
    if 'latitude' in data and data['latitude'] is not None:
        try:
            lat = float(data['latitude'])
            if lat < -90 or lat > 90:
                return "latitude must be between -90 and 90"
        except (TypeError, ValueError):
            return "latitude must be a number"
    
    if 'longitude' in data and data['longitude'] is not None:
        try:
            lng = float(data['longitude'])
            if lng < -180 or lng > 180:
                return "longitude must be between -180 and 180"
        except (TypeError, ValueError):
            return "longitude must be a number"
    
    # Boolean validation
    if 'is_helper' in data and not isinstance(data['is_helper'], bool):
        return "is_helper must be a boolean"
    
    # List validations
    for list_field in ('skills', 'helper_categories'):
        if list_field in data and data[list_field] is not None:
            val = data[list_field]
            if isinstance(val, list):
                if len(val) > 20:
                    return f"{list_field} can have at most 20 items"
                for item in val:
                    if not isinstance(item, str) or len(item) > 50:
                        return f"Each item in {list_field} must be a string under 50 characters"
            elif isinstance(val, str):
                if len(val) > 1000:
                    return f"{list_field} must be less than 1000 characters"
            else:
                return f"{list_field} must be a list or string"
    
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@auth_bp.route('/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    """Register a new user account."""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['username', 'email', 'password']):
            return jsonify({'error': 'Missing required fields'}), 400
        
        username = data['username'].strip()
        email = data['email'].strip().lower()
        password = data['password']
        first_name = data.get('first_name', '').strip() if data.get('first_name') else None
        last_name = data.get('last_name', '').strip() if data.get('last_name') else None
        
        # Validate username: 3-30 chars, alphanumeric + underscores
        if not USERNAME_REGEX.match(username):
            return jsonify({'error': 'Username must be 3-30 characters and contain only letters, numbers, and underscores'}), 400
        
        # Validate email format
        if not EMAIL_REGEX.match(email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        if len(email) > 254:
            return jsonify({'error': 'Email is too long'}), 400
        
        # Validate password: 6-128 chars
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        if len(password) > 128:
            return jsonify({'error': 'Password must be less than 128 characters'}), 400
        
        # Validate optional name fields
        if first_name and len(first_name) > 50:
            return jsonify({'error': 'First name must be less than 50 characters'}), 400
        
        if last_name and len(last_name) > 50:
            return jsonify({'error': 'Last name must be less than 50 characters'}), 400
        
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 409
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 409
        
        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Generate token for auto-login after registration
        payload = {
            'user_id': user.id,
            'username': user.username,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, _get_secret_key(), algorithm='HS256')
        
        return jsonify({
            'message': 'User registered successfully',
            'token': token,
            'user': user.to_dict()
        }), 201
    except Exception:
        db.session.rollback()
        raise


@auth_bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
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
        token = jwt.encode(payload, _get_secret_key(), algorithm='HS256')
        
        return jsonify({
            'message': 'Login successful',
            'token': token,
            'user': user.to_dict()
        }), 200
    except Exception:
        raise
