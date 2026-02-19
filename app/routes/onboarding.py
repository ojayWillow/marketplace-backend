"""Onboarding routes for new user setup."""

from flask import Blueprint, request, jsonify
from app import db
from app.models import User
from app.utils import token_required
from datetime import datetime

onboarding_bp = Blueprint('onboarding', __name__)


@onboarding_bp.route('/complete-onboarding', methods=['PUT'])
@token_required
def complete_onboarding(current_user_id):
    """Mark onboarding as completed.
    
    Called after the user finishes the mandatory onboarding steps
    (basic info + skills). Optionally accepts profile fields to
    save in the same request.
    """
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json() or {}
        
        # Update profile fields if provided
        if 'username' in data:
            new_username = data['username'].lower().strip()
            if len(new_username) < 3:
                return jsonify({'error': 'Username must be at least 3 characters'}), 400
            if not new_username.replace('_', '').isalnum():
                return jsonify({'error': 'Username can only contain letters, numbers, and underscores'}), 400
            existing = User.query.filter_by(username=new_username).first()
            if existing and existing.id != user.id:
                return jsonify({'error': 'Username already exists'}), 409
            user.username = new_username
        
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'avatar_url' in data:
            user.avatar_url = data['avatar_url']
        if 'profile_picture_url' in data:
            user.profile_picture_url = data['profile_picture_url']
        if 'city' in data:
            user.city = data['city']
        if 'country' in data:
            user.country = data['country']
        if 'bio' in data:
            user.bio = data['bio']
        if 'skills' in data:
            if isinstance(data['skills'], list):
                user.skills = ','.join(data['skills'])
            else:
                user.skills = data['skills']
        if 'helper_categories' in data:
            if isinstance(data['helper_categories'], list):
                user.helper_categories = ','.join(data['helper_categories'])
            else:
                user.helper_categories = data['helper_categories']
        if 'latitude' in data:
            user.latitude = data['latitude']
        if 'longitude' in data:
            user.longitude = data['longitude']
        if 'email' in data:
            new_email = data['email'].lower().strip()
            if new_email and '@' in new_email:
                existing_email = User.query.filter_by(email=new_email).first()
                if existing_email and existing_email.id != user.id:
                    return jsonify({'error': 'Email already exists'}), 409
                user.email = new_email
        
        # Mark onboarding as done
        user.onboarding_completed = True
        user.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Onboarding completed',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@onboarding_bp.route('/onboarding-status', methods=['GET'])
@token_required
def onboarding_status(current_user_id):
    """Check what onboarding steps are complete.
    
    Returns which fields are filled so the frontend wizard
    can resume from where the user left off.
    """
    try:
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        has_real_username = user.username and not user.username.startswith('user_')
        has_name = bool(user.first_name)
        has_city = bool(user.city)
        has_avatar = bool(user.avatar_url or user.profile_picture_url)
        has_skills = bool(user.skills or user.helper_categories)
        
        basic_info_complete = has_real_username and has_name and has_city
        skills_complete = has_skills
        
        return jsonify({
            'onboarding_completed': user.onboarding_completed,
            'steps': {
                'basic_info': {
                    'complete': basic_info_complete,
                    'has_username': has_real_username,
                    'has_name': has_name,
                    'has_city': has_city,
                    'has_avatar': has_avatar,
                },
                'skills': {
                    'complete': skills_complete,
                    'has_skills': has_skills,
                },
                'notifications': {
                    'complete': False,  # Frontend tracks this locally
                },
                'phone_verification': {
                    'complete': user.phone_verified,
                    'is_verified': user.is_verified,
                },
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
