"""Legacy Firebase phone authentication endpoints.

DEPRECATED: Use Vonage OTP endpoints instead:
- /phone/send-otp + /phone/verify-otp (replaces /phone/verify)
- /phone/send-otp + /phone/link-otp (replaces /phone/link)

These endpoints are kept for backward compatibility with older
client versions. They should be removed once all clients have
migrated to the Vonage OTP flow.
"""

from flask import request, jsonify, current_app
from app import db
from app.models import User
from app.utils import token_required
from app.routes.auth import auth_bp
from app.routes.auth.core import (
    _get_secret_key, generate_temp_username, generate_temp_password
)
from datetime import datetime, timedelta
import jwt


@auth_bp.route('/phone/verify', methods=['POST'])
def phone_verify():
    """Legacy Firebase phone verification endpoint.
    
    DEPRECATED: Use /phone/send-otp and /phone/verify-otp instead.
    """
    try:
        try:
            from app.services.firebase import verify_firebase_token, normalize_phone_number as firebase_normalize
        except ImportError:
            return jsonify({'error': 'Firebase authentication is not available. Use /phone/send-otp instead.'}), 501
        
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
            'message': 'Phone verification successful',
            'access_token': token,
            'user': user.to_dict(),
            'is_new_user': is_new_user
        }), 200
        
    except Exception:
        db.session.rollback()
        raise


@auth_bp.route('/phone/link', methods=['POST'])
@token_required
def phone_link(current_user_id):
    """Legacy Firebase phone link endpoint.
    
    DEPRECATED: Use /phone/send-otp and /phone/link-otp instead.
    """
    try:
        try:
            from app.services.firebase import verify_firebase_token, normalize_phone_number as firebase_normalize
        except ImportError:
            return jsonify({'error': 'Firebase authentication is not available. Use /phone/link-otp instead.'}), 501
        
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
        
        current_app.logger.info(f"Phone linked to user {user.id}: {normalized_phone}")
        
        return jsonify({
            'message': 'Phone number verified and linked successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception:
        db.session.rollback()
        raise
