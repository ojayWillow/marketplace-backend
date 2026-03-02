"""Shared authentication utilities.

This module provides JWT authentication decorators that can be used
across all route files to ensure consistent authentication behavior.

Supports TWO token types during migration:
1. Supabase JWT (primary) - decoded using SUPABASE_JWT_SECRET, user looked up by `sub` -> supabase_user_id
2. Legacy custom JWT (temporary) - decoded using JWT_SECRET_KEY, user looked up by `user_id` in payload

Once all users are migrated to Supabase Auth, remove the legacy fallback (tracked in #53).
"""

from functools import wraps
from flask import request, jsonify, current_app, g
import jwt
import os

# Legacy secret (kept for backward compatibility during migration)
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')


def _get_supabase_jwt_secret():
    """Get Supabase JWT secret, return None if not configured."""
    return os.getenv('SUPABASE_JWT_SECRET')


def _resolve_user_from_token(auth_header):
    """Decode token and resolve to local user_id.

    Tries Supabase JWT first, falls back to legacy custom JWT.

    Returns:
        (user_id, error_message, status_code)
        On success: (user_id, None, None)
        On failure: (None, error_string, http_status)
    """
    try:
        token = auth_header.split(' ')[1] if ' ' in auth_header else auth_header
    except (IndexError, AttributeError):
        return None, 'Token is missing', 401

    # --- Attempt 1: Supabase JWT ---
    supabase_secret = _get_supabase_jwt_secret()
    if supabase_secret:
        try:
            payload = jwt.decode(token, supabase_secret, algorithms=['HS256'], audience='authenticated')
            supabase_uid = payload.get('sub')
            if supabase_uid:
                from app.models import User
                user = User.query.filter_by(supabase_user_id=supabase_uid).first()
                if user:
                    return user.id, None, None
                # Supabase token is valid but user not synced yet
                # This can happen on first login before /sync-user is called
                current_app.logger.warning(
                    f'Valid Supabase token but no local user for sub={supabase_uid}'
                )
                return None, 'User not found. Please complete registration.', 401
        except jwt.ExpiredSignatureError:
            return None, 'Token has expired', 401
        except jwt.InvalidTokenError:
            # Not a Supabase token, try legacy
            pass

    # --- Attempt 2: Legacy custom JWT (remove after migration #53) ---
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
        if user_id:
            return user_id, None, None
        return None, 'Token is invalid', 401
    except jwt.ExpiredSignatureError:
        return None, 'Token has expired', 401
    except jwt.InvalidTokenError:
        return None, 'Token is invalid', 401


def token_required(f):
    """Decorator to require valid JWT token.

    Supports both Supabase and legacy JWTs.
    Extracts user_id and passes it as the first argument.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            return jsonify({'error': 'Token is missing'}), 401

        user_id, error, status = _resolve_user_from_token(auth_header)
        if error:
            return jsonify({'error': error}), status

        return f(user_id, *args, **kwargs)
    return decorated


def token_optional(f):
    """Decorator that optionally validates JWT token.

    If a valid token is provided, extracts user_id. Otherwise, passes None.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        current_user_id = None

        if auth_header:
            user_id, error, status = _resolve_user_from_token(auth_header)
            if not error:
                current_user_id = user_id

        return f(current_user_id, *args, **kwargs)
    return decorated


# ============ g.current_user variants ============

def token_required_g(f):
    """Decorator to require valid JWT token, setting g.current_user.

    Sets g.current_user to the full User object.
    Does NOT pass current_user_id as a parameter.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from app.models import User

        auth_header = request.headers.get('Authorization')

        if not auth_header:
            return jsonify({'error': 'Token is missing'}), 401

        user_id, error, status = _resolve_user_from_token(auth_header)
        if error:
            return jsonify({'error': error}), status

        current_user = User.query.get(user_id)
        if not current_user:
            return jsonify({'error': 'User not found'}), 401
        g.current_user = current_user

        return f(*args, **kwargs)
    return decorated


def token_optional_g(f):
    """Decorator for optional JWT authentication, setting g.current_user.

    Sets g.current_user to the User object if authenticated, None otherwise.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from app.models import User

        g.current_user = None
        auth_header = request.headers.get('Authorization')

        if auth_header:
            user_id, error, status = _resolve_user_from_token(auth_header)
            if not error:
                g.current_user = User.query.get(user_id)

        return f(*args, **kwargs)
    return decorated
