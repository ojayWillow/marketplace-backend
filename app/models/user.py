"""User model for authentication and user management."""

from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
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
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)  # Track user activity
    
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
    
    def update_last_seen(self):
        """Update the last_seen timestamp."""
        self.last_seen = datetime.utcnow()
    
    def get_online_status(self):
        """
        Get user's online status based on last_seen.
        Returns: 'online', 'recently', or 'inactive'
        """
        if not self.last_seen:
            return 'inactive'
        
        now = datetime.utcnow()
        time_diff = now - self.last_seen
        
        # Online: active in last 5 minutes
        if time_diff < timedelta(minutes=5):
            return 'online'
        
        # Recently: active in last 30 minutes
        if time_diff < timedelta(minutes=30):
            return 'recently'
        
        # Inactive: not seen for 3+ days
        if time_diff > timedelta(days=3):
            return 'inactive'
        
        # Default: recently (between 30 min and 3 days)
        return 'recently'
    
    def get_last_seen_display(self):
        """
        Get human-readable last seen text.
        Returns string like "5 minutes ago", "2 hours ago", "3 days ago"
        """
        if not self.last_seen:
            return None
        
        now = datetime.utcnow()
        time_diff = now - self.last_seen
        
        if time_diff < timedelta(minutes=1):
            return "just now"
        elif time_diff < timedelta(minutes=60):
            minutes = int(time_diff.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif time_diff < timedelta(hours=24):
            hours = int(time_diff.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif time_diff < timedelta(days=7):
            days = int(time_diff.total_seconds() / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        else:
            return self.last_seen.strftime("%b %d, %Y")
    
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
            'is_helper': self.is_helper or False,
            'skills': self.skills,
            'helper_categories': self.helper_categories,
            'hourly_rate': self.hourly_rate,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'online_status': self.get_online_status(),
            'last_seen_display': self.get_last_seen_display()
        }
    
    def to_public_dict(self):
        """Convert user to dictionary for public viewing (excludes sensitive data)."""
        return {
            'id': self.id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'avatar_url': self.avatar_url,
            'bio': self.bio,
            'city': self.city,
            'country': self.country,
            'is_verified': self.is_verified,
            'profile_picture_url': self.profile_picture_url,
            'reputation_score': self.reputation_score,
            'completion_rate': self.completion_rate,
            'is_helper': self.is_helper or False,
            'skills': self.skills,
            'helper_categories': self.helper_categories,
            'hourly_rate': self.hourly_rate,
            'created_at': self.created_at.isoformat(),
            'online_status': self.get_online_status(),
            'last_seen_display': self.get_last_seen_display()
        }
    
    def __repr__(self):
        return f'<User {self.username}>'
