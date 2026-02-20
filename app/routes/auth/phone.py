"""Vonage phone authentication routes: OTP send, verify, link, check."""

from flask import request, jsonify, current_app
from app import db, limiter
from app.models import User
from app.utils import token_required
from app.routes.auth import auth_bp
from app.routes.auth.core import (
    _get_secret_key, generate_temp_username, generate_temp_password,
    USERNAME_REGEX, EMAIL_REGEX
)
from app.services.vonage_sms import send_verification_code, verify_code, normalize_phone_number
from datetime import datetime, timedelta
import jwt


@auth_bp.route('/phone/send-otp', methods=['POST'])
@limiter.limit("3 per minute")
def phone_send_otp():
    """Send OTP verification code to phone number via Vonage."""
    try:
        data = request.get_json()
        
        if not data or 'phoneNumber' not in data:
            return jsonify({'error': 'Phone number is required'}), 400
        
        phone_number = data['phoneNumber']
        
        normalized = normalize_phone_number(phone_number)
        if not normalized or len(normalized) < 10:
            return jsonify({'error': 'Invalid phone number format'}), 400
        
        result = send_verification_code(phone_number)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Verification code sent',
                'phone': result['phone']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except ValueError as e:
        current_app.logger.error(f"Vonage configuration error: {e}")
        return jsonify({'error': 'SMS service not configured'}), 500
    except Exception:
        raise


@auth_bp.route('/phone/verify-otp', methods=['POST'])
@limiter.limit("5 per minute")
def phone_verify_otp():
    """Verify OTP code and create/login user."""
    try:
        data = request.get_json()
        
        if not data or 'phoneNumber' not in data or 'code' not in data:
            return jsonify({'error': 'Phone number and verification code are required'}), 400
        
        phone_number = data['phoneNumber']
        code = data['code']
        
        result = verify_code(phone_number, code)
        
        if not result['success']:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
        
        normalized_phone = result['phone']
        
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
            temp_email = f"{temp_username}@phone.tirgus.local"
            
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
        
        payload = {
            'user_id': user.id,
            'username': user.username,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, _get_secret_key(), algorithm='HS256')
        
        return jsonify({
            'success': True,
            'message': 'Phone verification successful',
            'access_token': token,
            'user': user.to_dict(),
            'is_new_user': is_new_user
        }), 200
        
    except Exception:
        db.session.rollback()
        raise


@auth_bp.route('/phone/link-otp', methods=['POST'])
@token_required
def phone_link_otp(current_user_id):
    """Link a verified phone number to existing user account."""
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user.is_active:
            return jsonify({'error': 'Account is disabled'}), 403
        
        data = request.get_json()
        
        if not data or 'phoneNumber' not in data or 'code' not in data:
            return jsonify({'error': 'Phone number and verification code are required'}), 400
        
        phone_number = data['phoneNumber']
        code = data['code']
        
        result = verify_code(phone_number, code)
        
        if not result['success']:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
        
        normalized_phone = result['phone']
        
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
        
        current_app.logger.info(f"Phone linked to user {user.id}: {normalized_phone}")
        
        return jsonify({
            'success': True,
            'message': 'Phone number verified and linked successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception:
        db.session.rollback()
        raise


@auth_bp.route('/phone/check/<phone>', methods=['GET'])
def phone_check(phone):
    """Check if a phone number is already registered."""
    try:
        normalized_phone = normalize_phone_number(phone)
        
        if not normalized_phone:
            return jsonify({'error': 'Invalid phone number'}), 400
        
        user = User.query.filter_by(phone=normalized_phone).first()
        
        return jsonify({
            'exists': user is not None,
            'phone': normalized_phone
        }), 200
        
    except Exception:
        raise


@auth_bp.route('/complete-registration', methods=['PUT'])
@token_required
@limiter.limit("5 per minute")
def complete_registration(current_user_id):
    """Complete registration for phone-authenticated users."""
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        if not data or 'username' not in data:
            return jsonify({'error': 'Username is required'}), 400
        
        new_username = data['username'].lower().strip()
        new_email = data.get('email', '').lower().strip() if data.get('email') else None
        
        if not USERNAME_REGEX.match(new_username):
            return jsonify({'error': 'Username must be 3-30 characters and contain only letters, numbers, and underscores'}), 400
        
        existing_user = User.query.filter_by(username=new_username).first()
        if existing_user and existing_user.id != user.id:
            return jsonify({'error': 'Username already exists'}), 409
        
        if new_email:
            if not EMAIL_REGEX.match(new_email):
                return jsonify({'error': 'Invalid email format'}), 400
            
            if len(new_email) > 254:
                return jsonify({'error': 'Email is too long'}), 400
            
            existing_email = User.query.filter_by(email=new_email).first()
            if existing_email and existing_email.id != user.id:
                return jsonify({'error': 'Email already exists'}), 409
            
            user.email = new_email
        
        user.username = new_username
        user.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        payload = {
            'user_id': user.id,
            'username': user.username,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, _get_secret_key(), algorithm='HS256')
        
        return jsonify({
            'message': 'Registration completed successfully',
            'access_token': token,
            'user': user.to_dict()
        }), 200
        
    except Exception:
        db.session.rollback()
        raise
