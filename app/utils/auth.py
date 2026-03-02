"""Shared authentication utilities.

This module provides JWT authentication decorators that can be used
across all route files to ensure consistent authentication behavior.

All tokens are Supabase JWTs. For ES256 tokens, verified using the
public key from Supabase's JWKS endpoint. For HS256 tokens (legacy),
verified using SUPABASE_JWT_SECRET.

Users are looked up by the `sub` claim -> User.supabase_user_id.
"""

import os
import time
from functools import wraps
from flask import request, jsonify, current_app, g
import jwt
from jwt import PyJWKClient

# Cache the JWKS client to avoid re-fetching keys on every request
_jwks_client = None
_jwks_client_init_time = 0
_JWKS_CACHE_TTL = 3600  # Re-create client every hour


def _get_supabase_jwt_secret():
    """Get Supabase JWT secret, return None if not configured."""
    return os.getenv('SUPABASE_JWT_SECRET')


def _get_jwks_client():
    """Get or create a cached JWKS client for Supabase."""
    global _jwks_client, _jwks_client_init_time

    supabase_url = os.getenv('SUPABASE_URL')
    if not supabase_url:
        return None

    now = time.time()
    if _jwks_client is None or (now - _jwks_client_init_time) > _JWKS_CACHE_TTL:
        jwks_url = f'{supabase_url.rstrip("/")}/auth/v1/.well-known/jwks.json'
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
        _jwks_client_init_time = now

    return _jwks_client


def _resolve_user_from_token(auth_header):
    """Decode Supabase JWT and resolve to local user_id.

    Supports both ES256 (asymmetric, verified via JWKS) and
    HS256 (symmetric, verified via SUPABASE_JWT_SECRET).

    Returns:
        (user_id, error_message, status_code)
        On success: (user_id, None, None)
        On failure: (None, error_string, http_status)
    """
    try:
        token = auth_header.split(' ')[1] if ' ' in auth_header else auth_header
    except (IndexError, AttributeError):
        return None, 'Token is missing', 401

    try:
        # Peek at the header to determine algorithm
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get('alg', 'HS256')
    except Exception:
        return None, 'Token is invalid', 401

    try:
        if alg.startswith('ES') or alg.startswith('RS') or alg.startswith('PS'):
            # Asymmetric algorithm — use JWKS public key
            jwks_client = _get_jwks_client()
            if not jwks_client:
                current_app.logger.error(
                    'SUPABASE_URL not configured — cannot verify ES256 tokens'
                )
                return None, 'Server authentication configuration error', 500

            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience='authenticated',
            )
        else:
            # Symmetric (HS256/HS384/HS512) — use JWT secret
            supabase_secret = _get_supabase_jwt_secret()
            if not supabase_secret:
                current_app.logger.error('SUPABASE_JWT_SECRET is not configured')
                return None, 'Server authentication configuration error', 500

            payload = jwt.decode(
                token,
                supabase_secret,
                algorithms=['HS256', 'HS384', 'HS512'],
                audience='authenticated',
            )

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
    except jwt.InvalidTokenError as e:
        current_app.logger.warning(f'Invalid Supabase token: {e}')
        return None, 'Token is invalid', 401
    except Exception as e:
        current_app.logger.error(f'Token verification error: {e}')
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
