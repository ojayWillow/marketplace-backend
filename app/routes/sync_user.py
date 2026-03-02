"""Sync user endpoint for Supabase Auth.

This endpoint is called by the frontend after a successful Supabase
sign-up or sign-in. It ensures the user exists in our local `users`
table and links them to their Supabase Auth UUID.

Flow:
  1. Frontend calls supabase.auth.signUp() or signInWithPassword()
  2. Frontend gets a Supabase session (access_token + refresh_token)
  3. Frontend calls POST /auth/sync-user with the Supabase access_token
  4. Backend decodes the token, creates/finds local user, returns profile

Note: This does NOT use @token_required because the user might not
exist locally yet (that's the whole point of this endpoint).
"""

import os
import secrets
import string
import traceback
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import User
import jwt as pyjwt
from jwt import PyJWKClient

sync_user_bp = Blueprint('sync_user', __name__)


def _generate_temp_username():
    """Generate a temporary username for new users."""
    random_suffix = ''.join(
        secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8)
    )
    return f"user_{random_suffix}"


def _decode_supabase_token(auth_header):
    """Decode a Supabase JWT and return the payload.

    Supports both ES256 (JWKS) and HS256 (JWT secret).

    Returns:
        (payload_dict, error_message, status_code)
    """
    try:
        token = auth_header.split(' ')[1] if ' ' in auth_header else auth_header
    except (IndexError, AttributeError):
        return None, 'Token is missing', 401

    try:
        unverified_header = pyjwt.get_unverified_header(token)
        alg = unverified_header.get('alg', 'HS256')
    except Exception:
        return None, 'Invalid token', 401

    try:
        if alg.startswith('ES') or alg.startswith('RS') or alg.startswith('PS'):
            # Asymmetric — use JWKS
            supabase_url = os.getenv('SUPABASE_URL')
            if not supabase_url:
                return None, 'Supabase Auth not configured', 501

            jwks_url = f'{supabase_url.rstrip("/")}/auth/v1/.well-known/jwks.json'
            jwks_client = PyJWKClient(jwks_url, cache_keys=True)
            signing_key = jwks_client.get_signing_key_from_jwt(token)

            payload = pyjwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience='authenticated',
            )
        else:
            # Symmetric — use JWT secret
            supabase_secret = os.getenv('SUPABASE_JWT_SECRET')
            if not supabase_secret:
                return None, 'Supabase Auth not configured', 501

            payload = pyjwt.decode(
                token,
                supabase_secret,
                algorithms=['HS256', 'HS384', 'HS512'],
                audience='authenticated',
            )

        return payload, None, None

    except pyjwt.ExpiredSignatureError:
        return None, 'Token has expired', 401
    except pyjwt.InvalidTokenError as e:
        current_app.logger.warning(f'Invalid Supabase token in sync-user: {e}')
        return None, 'Invalid token', 401
    except Exception as e:
        current_app.logger.error(f'Token decode error in sync-user: {e}')
        return None, 'Invalid token', 401


@sync_user_bp.route('/sync-user', methods=['POST'])
def sync_user():
    """Create or retrieve local user from Supabase Auth token.

    Called after Supabase signUp/signIn. Creates local user if needed.

    Headers:
        Authorization: Bearer <supabase_access_token>

    Body (optional, for new users):
        {
            "username": "john_doe",
            "first_name": "John",
            "last_name": "Doe"
        }

    Returns:
        { "user": {...}, "is_new_user": bool }
    """
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Token is missing'}), 401

        payload, error, status = _decode_supabase_token(auth_header)
        if error:
            return jsonify({'error': error}), status

        supabase_uid = payload.get('sub')
        if not supabase_uid:
            return jsonify({'error': 'Invalid token: no sub claim'}), 401

        token_email = payload.get('email')
        token_phone = payload.get('phone')

        # --- Check if user already exists ---
        user = User.query.filter_by(supabase_user_id=supabase_uid).first()

        if user:
            # Existing user — update last_seen and return
            user.last_seen = datetime.utcnow()
            db.session.commit()

            return jsonify({
                'user': user.to_dict(),
                'is_new_user': False
            }), 200

        # --- Also check by email/phone (for users migrated from legacy) ---
        if token_email:
            user = User.query.filter_by(email=token_email).first()
        if not user and token_phone:
            user = User.query.filter_by(phone=token_phone).first()

        if user:
            # Legacy user found — link to Supabase and return
            user.supabase_user_id = supabase_uid
            user.last_seen = datetime.utcnow()
            db.session.commit()

            current_app.logger.info(
                f'Linked legacy user {user.id} to Supabase {supabase_uid}'
            )
            return jsonify({
                'user': user.to_dict(),
                'is_new_user': False
            }), 200

        # --- Create new user ---
        data = request.get_json(silent=True) or {}

        username = data.get('username', '').lower().strip()
        if not username or len(username) < 3:
            username = _generate_temp_username()
        else:
            if len(username) > 30 or not username.replace('_', '').isalnum():
                username = _generate_temp_username()
            elif User.query.filter_by(username=username).first():
                username = _generate_temp_username()

        email = token_email or f"{username}@supabase.kolab.local"
        if User.query.filter_by(email=email).first():
            email = f"{username}_{secrets.token_hex(4)}@supabase.kolab.local"

        user = User(
            supabase_user_id=supabase_uid,
            username=username,
            email=email,
            phone=token_phone,
            first_name=data.get('first_name', '').strip() or None,
            last_name=data.get('last_name', '').strip() or None,
            phone_verified=bool(token_phone),
            is_verified=bool(token_email),
            onboarding_completed=False,
        )
        user.set_password(secrets.token_urlsafe(32))

        db.session.add(user)
        db.session.commit()

        current_app.logger.info(
            f'New user created: {user.id} (supabase: {supabase_uid})'
        )

        return jsonify({
            'user': user.to_dict(),
            'is_new_user': True
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Sync user error: {str(e)}')
        current_app.logger.debug(traceback.format_exc())
        return jsonify({'error': 'Failed to sync user'}), 500
