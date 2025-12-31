"""Authentication routes for user registration and login."""

from flask import Blueprint, request, jsonify
from app import db
from app.models import User
import os
from datetime import datetime, timedelta
import jwt

auth_bp = Blueprint('auth', __name__)
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')


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
        
        return jsonify({
            'message': 'User registered successfully',
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
        
        payload = {
            'user_id': user.id,
            'username': user.username,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
        
        return jsonify({
            'message': 'Login successful',
            'token': token,
            'user': user.to_dict()
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    """Get current user profile."""
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Missing authorization token'}), 401
        
        token = token.split(' ')[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        user = User.query.get(payload['user_id'])
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify(user.to_dict()), 200
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token has expired'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 400
