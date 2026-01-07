"""Authentication routes for user registration and login."""

from flask import Blueprint, request, jsonify
from app import db
from app.models import User, Review
import os
from datetime import datetime, timedelta
import jwt
from functools import wraps
import pyotp
import qrcode
import qrcode.image.svg
from io import BytesIO
import base64

auth_bp = Blueprint('auth', __name__)

# Use JWT_SECRET_KEY consistently across all routes
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')
APP_NAME = os.getenv('APP_NAME', 'Marketplace')


def token_required(f):
    """Decorator to require valid JWT token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            token = auth_header.split(' ')[1] if ' ' in auth_header else auth_header
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            
            # Check if this is a partial token (2FA pending)
            if payload.get('requires_2fa'):
                return jsonify({'error': '2FA verification required', 'requires_2fa': True}), 401
            
            current_user_id = payload['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except Exception as e:
            return jsonify({'error': 'Token is invalid'}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorated


def generate_full_token(user):
    """Generate a full access token."""
    payload = {
        'user_id': user.id,
        'username': user.username,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


def generate_partial_token(user):
    """Generate a partial token that requires 2FA verification."""
    payload = {
        'user_id': user.id,
        'username': user.username,
        'requires_2fa': True,
        'exp': datetime.utcnow() + timedelta(minutes=10)  # Short expiry for 2FA
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user account."""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['username', 'email', 'password']):
            return jsonify({'error': 'Missing required fields'}), 400
        
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
        token = generate_full_token(user)
        
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
        
        # Check if 2FA is enabled
        if user.totp_enabled:
            # Return partial token - user must verify with TOTP
            partial_token = generate_partial_token(user)
            return jsonify({
                'message': '2FA verification required',
                'requires_2fa': True,
                'partial_token': partial_token,
                'user_id': user.id
            }), 200
        
        # No 2FA - return full token
        token = generate_full_token(user)
        
        return jsonify({
            'message': 'Login successful',
            'token': token,
            'user': user.to_dict()
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# TWO-FACTOR AUTHENTICATION ENDPOINTS
# ============================================

@auth_bp.route('/2fa/setup', methods=['POST'])
@token_required
def setup_2fa(current_user_id):
    """Generate TOTP secret and QR code for 2FA setup."""
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if user.totp_enabled:
            return jsonify({'error': '2FA is already enabled'}), 400
        
        # Generate new secret
        secret = pyotp.random_base32()
        user.totp_secret = secret
        db.session.commit()
        
        # Create TOTP URI for QR code
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name=APP_NAME
        )
        
        # Generate QR code as base64 PNG
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return jsonify({
            'message': 'Scan QR code with your authenticator app',
            'secret': secret,  # Manual entry backup
            'qr_code': f'data:image/png;base64,{qr_base64}',
            'provisioning_uri': provisioning_uri
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/2fa/enable', methods=['POST'])
@token_required
def enable_2fa(current_user_id):
    """Verify TOTP code and enable 2FA."""
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if user.totp_enabled:
            return jsonify({'error': '2FA is already enabled'}), 400
        
        if not user.totp_secret:
            return jsonify({'error': 'Please run /2fa/setup first'}), 400
        
        data = request.get_json()
        code = data.get('code', '').replace(' ', '').replace('-', '')
        
        if not code:
            return jsonify({'error': 'Verification code required'}), 400
        
        # Verify the code
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(code, valid_window=1):  # Allow 1 step tolerance (30 sec)
            return jsonify({'error': 'Invalid verification code'}), 401
        
        # Enable 2FA and generate backup codes
        user.totp_enabled = True
        backup_codes = user.generate_backup_codes()
        db.session.commit()
        
        return jsonify({
            'message': '2FA enabled successfully',
            'backup_codes': backup_codes,
            'warning': 'Save these backup codes! They can only be viewed once.'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/2fa/verify', methods=['POST'])
def verify_2fa():
    """Verify TOTP code during login and return full token."""
    try:
        data = request.get_json()
        
        partial_token = data.get('partial_token')
        code = data.get('code', '').replace(' ', '').replace('-', '')
        
        if not partial_token or not code:
            return jsonify({'error': 'Partial token and code required'}), 400
        
        # Decode partial token
        try:
            payload = jwt.decode(partial_token, SECRET_KEY, algorithms=['HS256'])
            if not payload.get('requires_2fa'):
                return jsonify({'error': 'Invalid partial token'}), 401
            user_id = payload['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': '2FA session expired, please login again'}), 401
        except:
            return jsonify({'error': 'Invalid partial token'}), 401
        
        user = User.query.get(user_id)
        if not user or not user.totp_enabled:
            return jsonify({'error': 'Invalid request'}), 400
        
        # Try TOTP code first
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(code, valid_window=1):
            token = generate_full_token(user)
            return jsonify({
                'message': 'Login successful',
                'token': token,
                'user': user.to_dict()
            }), 200
        
        # Try backup code
        if user.verify_backup_code(code):
            db.session.commit()
            token = generate_full_token(user)
            return jsonify({
                'message': 'Login successful (backup code used)',
                'token': token,
                'user': user.to_dict(),
                'warning': f'Backup code used. {user.get_backup_codes_count()} codes remaining.'
            }), 200
        
        return jsonify({'error': 'Invalid verification code'}), 401
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/2fa/disable', methods=['POST'])
@token_required
def disable_2fa(current_user_id):
    """Disable 2FA for user account."""
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user.totp_enabled:
            return jsonify({'error': '2FA is not enabled'}), 400
        
        data = request.get_json()
        code = data.get('code', '').replace(' ', '').replace('-', '')
        password = data.get('password', '')
        
        # Require password confirmation
        if not user.check_password(password):
            return jsonify({'error': 'Invalid password'}), 401
        
        # Verify TOTP or backup code
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(code, valid_window=1) and not user.verify_backup_code(code):
            return jsonify({'error': 'Invalid verification code'}), 401
        
        # Disable 2FA
        user.totp_enabled = False
        user.totp_secret = None
        user.totp_backup_codes = None
        db.session.commit()
        
        return jsonify({
            'message': '2FA disabled successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/2fa/backup-codes', methods=['POST'])
@token_required
def regenerate_backup_codes(current_user_id):
    """Regenerate backup codes (invalidates old ones)."""
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user.totp_enabled:
            return jsonify({'error': '2FA is not enabled'}), 400
        
        data = request.get_json()
        code = data.get('code', '').replace(' ', '').replace('-', '')
        
        # Verify TOTP code
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(code, valid_window=1):
            return jsonify({'error': 'Invalid verification code'}), 401
        
        # Generate new backup codes
        backup_codes = user.generate_backup_codes()
        db.session.commit()
        
        return jsonify({
            'message': 'Backup codes regenerated',
            'backup_codes': backup_codes,
            'warning': 'Save these codes! Old codes are now invalid.'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/2fa/status', methods=['GET'])
@token_required
def get_2fa_status(current_user_id):
    """Get current 2FA status."""
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'totp_enabled': user.totp_enabled,
            'backup_codes_remaining': user.get_backup_codes_count()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# EXISTING PROFILE ENDPOINTS
# ============================================

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
        
        reviews = Review.query.filter_by(reviewed_user_id=user_id).order_by(Review.created_at.desc()).all()
        
        reviews_data = []
        for review in reviews:
            reviewer = User.query.get(review.reviewer_id)
            review_dict = review.to_dict()
            review_dict['reviewer_name'] = reviewer.username if reviewer else 'Unknown'
            review_dict['reviewer_avatar'] = reviewer.avatar_url if reviewer else None
            reviews_data.append(review_dict)
        
        return jsonify({
            'reviews': reviews_data,
            'total': len(reviews_data)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
