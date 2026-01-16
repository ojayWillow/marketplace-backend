"""Shared authentication utilities.

This module provides JWT authentication decorators that can be used
across all route files to ensure consistent authentication behavior.
"""

from functools import wraps
from flask import request, jsonify, current_app
import jwt
import os

# Use JWT_SECRET_KEY consistently across all routes
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')


def token_required(f):
    """
    Decorator to require valid JWT token.
    
    Extracts user_id from JWT token and passes it as the first argument
    to the decorated function.
    
    Usage:
        @app.route('/protected')
        @token_required
        def protected_route(current_user_id):
            # current_user_id is extracted from JWT
            return jsonify({'user_id': current_user_id})
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Skip authentication in testing mode
        if current_app.config.get('TESTING'):
            current_user_id = 1  # Default test user
            return f(current_user_id, *args, **kwargs)
        
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            # Support both "Bearer <token>" and raw token formats
            token = auth_header.split(' ')[1] if ' ' in auth_header else auth_header
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            current_user_id = payload['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token is invalid'}), 401
        except Exception as e:
            return jsonify({'error': 'Token is invalid'}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorated


def token_optional(f):
    """
    Decorator that optionally validates JWT token.
    
    If a valid token is provided, extracts user_id. Otherwise, passes None.
    Useful for endpoints that work for both authenticated and anonymous users.
    
    Usage:
        @app.route('/items')
        @token_optional
        def get_items(current_user_id):
            # current_user_id is user's ID or None if not authenticated
            if current_user_id:
                # Show personalized content
                pass
            return jsonify({'items': items})
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        current_user_id = None
        
        if auth_header:
            try:
                token = auth_header.split(' ')[1] if ' ' in auth_header else auth_header
                payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
                current_user_id = payload['user_id']
            except:
                pass  # Token invalid, but that's ok - it's optional
        
        return f(current_user_id, *args, **kwargs)
    return decorated
