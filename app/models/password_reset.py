"""Password Reset Token model for forgot password functionality."""

import secrets
from datetime import datetime, timedelta
from app import db


class PasswordResetToken(db.Model):
    """Model to store password reset tokens."""
    
    __tablename__ = 'password_reset_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship
    user = db.relationship('User', backref=db.backref('reset_tokens', lazy=True))
    
    @classmethod
    def generate_token(cls, user_id, expires_in_hours=1):
        """
        Generate a new password reset token for a user.
        Invalidates any existing tokens for this user.
        """
        # Invalidate existing tokens for this user
        cls.query.filter_by(user_id=user_id, used=False).update({'used': True})
        
        # Generate a secure random token
        token = secrets.token_urlsafe(48)
        
        # Create new token record
        reset_token = cls(
            user_id=user_id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(hours=expires_in_hours)
        )
        
        db.session.add(reset_token)
        db.session.commit()
        
        return token
    
    @classmethod
    def verify_token(cls, token):
        """
        Verify a reset token and return the associated user_id if valid.
        Returns None if token is invalid, expired, or already used.
        """
        reset_token = cls.query.filter_by(token=token, used=False).first()
        
        if not reset_token:
            return None
        
        if reset_token.expires_at < datetime.utcnow():
            return None
        
        return reset_token.user_id
    
    @classmethod
    def use_token(cls, token):
        """
        Mark a token as used after successful password reset.
        """
        reset_token = cls.query.filter_by(token=token).first()
        if reset_token:
            reset_token.used = True
            db.session.commit()
    
    @classmethod
    def cleanup_expired(cls):
        """
        Remove expired tokens from the database.
        Can be called periodically to keep the table clean.
        """
        cls.query.filter(
            (cls.expires_at < datetime.utcnow()) | (cls.used == True)
        ).delete()
        db.session.commit()
    
    def __repr__(self):
        return f'<PasswordResetToken user_id={self.user_id} expires_at={self.expires_at}>'
