"""User model for authentication and user management."""

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
from app import db


class User(db.Model):
    """User model for marketplace platform."""
    
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)
    avatar_url = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(80), nullable=True)
    country = db.Column(db.String(80), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    user_type = db.Column(db.String(20), default='both', nullable=False)  # 'seller', 'buyer', 'helper', 'both'
    profile_picture_url = db.Column(db.String(500), nullable=True)
    phone_verified = db.Column(db.Boolean, default=False, nullable=False)
    reputation_score = db.Column(db.Float, default=0.0, nullable=False) # Average rating
    completion_rate = db.Column(db.Float, default=0.0, nullable=False) # Percentage of completed tasks
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # TOTP Two-Factor Authentication fields
    totp_secret = db.Column(db.String(32), nullable=True)  # Base32 encoded secret
    totp_enabled = db.Column(db.Boolean, default=False, nullable=False)
    totp_backup_codes = db.Column(db.Text, nullable=True)  # Comma-separated backup codes
    
    # Helper-specific fields (all nullable for SQLite compatibility)
    is_helper = db.Column(db.Boolean, default=False, nullable=True)  # User is available to help
    skills = db.Column(db.Text, nullable=True)  # Comma-separated list of skills
    helper_categories = db.Column(db.Text, nullable=True)  # Comma-separated categories they help with
    hourly_rate = db.Column(db.Float, nullable=True)  # Optional hourly rate
    latitude = db.Column(db.Float, nullable=True)  # User's location latitude
    longitude = db.Column(db.Float, nullable=True)  # User's location longitude
    
    # Relationships
    listings = db.relationship('Listing', backref='seller', lazy=True, foreign_keys='Listing.seller_id')
    task_requests = db.relationship('TaskRequest', backref='creator', lazy=True, foreign_keys='TaskRequest.creator_id')
    assigned_tasks = db.relationship('TaskRequest', backref='assigned_user', lazy=True, foreign_keys='TaskRequest.assigned_to_id')
    
    def set_password(self, password):
        """Hash and set the user password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if the provided password matches the hash."""
        return check_password_hash(self.password_hash, password)
    
    def generate_backup_codes(self, count=8):
        """Generate backup codes for 2FA recovery."""
        codes = [secrets.token_hex(4).upper() for _ in range(count)]  # 8-char codes like "A1B2C3D4"
        self.totp_backup_codes = ','.join(codes)
        return codes
    
    def verify_backup_code(self, code):
        """Verify and consume a backup code."""
        if not self.totp_backup_codes:
            return False
        
        codes = self.totp_backup_codes.split(',')
        code_upper = code.upper().replace('-', '').replace(' ', '')
        
        if code_upper in codes:
            codes.remove(code_upper)
            self.totp_backup_codes = ','.join(codes) if codes else None
            return True
        return False
    
    def get_backup_codes_count(self):
        """Get number of remaining backup codes."""
        if not self.totp_backup_codes:
            return 0
        return len(self.totp_backup_codes.split(','))
    
    def to_dict(self):
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'phone': self.phone,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'avatar_url': self.avatar_url,
            'bio': self.bio,
            'city': self.city,
            'country': self.country,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'user_type': self.user_type,
            'profile_picture_url': self.profile_picture_url,
            'phone_verified': self.phone_verified,
            'reputation_score': self.reputation_score,
            'completion_rate': self.completion_rate,
            'totp_enabled': self.totp_enabled,
            'backup_codes_remaining': self.get_backup_codes_count(),
            'is_helper': self.is_helper or False,
            'skills': self.skills,
            'helper_categories': self.helper_categories,
            'hourly_rate': self.hourly_rate,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<User {self.username}>'
