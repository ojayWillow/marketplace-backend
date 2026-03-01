"""TEMPORARY dev endpoints for testing. REMOVE before production."""

from flask import Blueprint, jsonify
from app import db
from app.models import User
from datetime import datetime
import secrets
import string

dev_bp = Blueprint('dev', __name__)


@dev_bp.route('/reset-onboarding/<int:user_id>', methods=['GET'])
def reset_onboarding(user_id):
    """Reset a user's onboarding state for testing.
    
    TEMPORARY — remove this endpoint after testing.
    Saves the real username so complete-registration can restore it.
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        old_username = user.username
        temp_suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
        
        user.onboarding_completed = False
        user.username = f'user_{temp_suffix}'
        user.username_changes_remaining = 1
        user.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': f'Onboarding reset for user {user_id}',
            'old_username': old_username,
            'temp_username': user.username,
            'note': 'Log out and log back in to see the onboarding wizard'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
