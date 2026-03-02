"""Shared authentication utilities.

This module provides JWT authentication decorators that can be used
across all route files to ensure consistent authentication behavior.

All tokens are Supabase JWTs, decoded using SUPABASE_JWT_SECRET.
Users are looked up by the `sub` claim -> User.supabase_user_id.
"""

from functools import wraps
from flask import request, jsonify, current_app, g
import jwt


def _get_supabase_jwt_secret():
    """Get Supabase JWT secret, return None if not configured."""
    import os
    return os.getenv('SUPABASE_JWT_SECRET')


def _resolve_user_from_token(auth_header):
    """Decode Supabase JWT and resolve to local user_id.

    Returns:
        (user_id, error_message, status_code)
        On success: (user_id, None, None)
        On failure: (None, error_string, http_status)
    """
    try:
        token = auth_header.split(' ')[1] if ' ' in auth_header else auth_header
    except (IndexError, AttributeError):
        return None, 'Token is missing', 401

    supabase_secret = _get_supabase_jwt_secret()
    if not supabase_secret:
        current_app.logger.error('SUPABASE_JWT_SECRET is not configured')
        return None, 'Server authentication configuration error', 500

    try:
        payload = jwt.decode(token, supabase_secret, algorithms=['HS256'], audience='authenticated')
        supabase_uid = payload.get('sub')
        if supabase_uid:
            from app.models import User
            user = User.query.filter_by(supabase_user_id=supabase_uid).first()
            if user:
                return user.id, None, None
            current_app.logger.warning(
                f'Valid Supabase token but no local user for sub={supabase_uid}'
            )
            return None, 'User not found. Please complete registration.', 401
        return None, 'Token is invalid', 401
    except jwt.ExpiredSignatureError:
        return None, 'Token has expired', 401
    except jwt.InvalidTokenError:
        return None, 'Token is invalid', 401


def token_required(f):
    """Decorator to require valid Supabase JWT token.

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
    """Decorator that optionally validates Supabase JWT token.

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
    """Decorator to require valid Supabase JWT, setting g.current_user.

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
    """Decorator for optional Supabase JWT authentication, setting g.current_user.

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
