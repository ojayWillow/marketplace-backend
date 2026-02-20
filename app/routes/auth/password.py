"""Password reset routes: forgot-password and reset-password."""

from flask import request, jsonify, current_app
from app import db, limiter
from app.models import User, PasswordResetToken
from app.services.email import email_service
from app.routes.auth import auth_bp
from datetime import datetime


@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit("3 per minute")
def forgot_password():
    """Request a password reset email."""
    try:
        data = request.get_json()
        
        if not data or 'email' not in data:
            return jsonify({'error': 'Email is required'}), 400
        
        email = data['email'].lower().strip()
        current_app.logger.debug(f"Password reset requested for email: {email}")
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            try:
                reset_token = PasswordResetToken.generate_token(user.id)
                current_app.logger.debug(f"Reset token generated for user_id: {user.id}")
                
                email_service.send_password_reset_email(
                    to_email=user.email,
                    username=user.username,
                    reset_token=reset_token
                )
                current_app.logger.debug(f"Password reset email sent to user_id: {user.id}")
            except Exception as inner_e:
                current_app.logger.error(f"Error in password reset process: {inner_e}")
        
        # Always return success to prevent email enumeration
        return jsonify({
            'message': 'If an account with that email exists, we have sent a password reset link.'
        }), 200
        
    except Exception:
        raise


@auth_bp.route('/reset-password', methods=['POST'])
@limiter.limit("5 per minute")
def reset_password():
    """Reset password using token from email."""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['token', 'password']):
            return jsonify({'error': 'Token and password are required'}), 400
        
        token = data['token']
        new_password = data['password']
        
        if len(new_password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        if len(new_password) > 128:
            return jsonify({'error': 'Password must be less than 128 characters'}), 400
        
        user_id = PasswordResetToken.verify_token(token)
        
        if not user_id:
            return jsonify({'error': 'Invalid or expired reset link'}), 400
        
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user.is_active:
            return jsonify({'error': 'Account is disabled'}), 403
        
        user.set_password(new_password)
        user.updated_at = datetime.utcnow()
        
        PasswordResetToken.use_token(token)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Password has been reset successfully'
        }), 200
        
    except Exception:
        db.session.rollback()
        raise
