"""User model for authentication and user management."""

import json
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from app import db


# Default job alert preferences
DEFAULT_JOB_ALERT_PREFERENCES = {
    'enabled': False,
    'radius_km': 5,
    'categories': [],  # empty = all categories
}


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
    
    # Presence tracking fields
    is_online = db.Column(db.Boolean, default=False, nullable=False)
    socket_id = db.Column(db.String(100), nullable=True)
    
    # Helper-specific fields
    is_helper = db.Column(db.Boolean, default=False, nullable=True)
    skills = db.Column(db.Text, nullable=True)
    helper_categories = db.Column(db.Text, nullable=True)
    hourly_rate = db.Column(db.Float, nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    
    # Job alert preferences (JSON string)
    # Stores: { enabled: bool, radius_km: float, categories: list[str] }
    job_alert_preferences = db.Column(db.Text, nullable=True)
    
    # Relationships
    listings = db.relationship('Listing', backref='seller', lazy='dynamic', foreign_keys='Listing.seller_id')
    task_requests = db.relationship('TaskRequest', backref='creator', lazy='dynamic', foreign_keys='TaskRequest.creator_id')
    assigned_tasks = db.relationship('TaskRequest', backref='assigned_user', lazy='dynamic', foreign_keys='TaskRequest.assigned_to_id')
    
    # --- Review stats (cached per-request to avoid N+1) ---
    _review_stats_cache = None
    
    def _get_review_stats(self):
        """Get rating + review_count in a SINGLE query. Cached per instance."""
        if self._review_stats_cache is None:
            from app.models.review import Review
            result = db.session.query(
                func.avg(Review.rating),
                func.count(Review.id)
            ).filter(
                Review.reviewed_user_id == self.id
            ).first()
            
            avg_rating = round(float(result[0]), 2) if result[0] is not None else None
            count = result[1] or 0
            self._review_stats_cache = (avg_rating, count)
        return self._review_stats_cache
    
    @property
    def rating(self):
        """Average rating from reviews received (single query, cached)."""
        return self._get_review_stats()[0]
    
    @property
    def review_count(self):
        """Total number of reviews received (single query, cached)."""
        return self._get_review_stats()[1]
    
    @staticmethod
    def get_review_stats_batch(user_ids):
        """Get rating + review_count for multiple users in ONE query.
        
        Returns dict: {user_id: (avg_rating, review_count)}
        Use this when serializing lists of users/applications to avoid N+1.
        """
        if not user_ids:
            return {}
        
        from app.models.review import Review
        results = db.session.query(
            Review.reviewed_user_id,
            func.avg(Review.rating),
            func.count(Review.id)
        ).filter(
            Review.reviewed_user_id.in_(user_ids)
        ).group_by(Review.reviewed_user_id).all()
        
        stats = {}
        for user_id, avg_rating, count in results:
            avg_r = round(float(avg_rating), 2) if avg_rating is not None else None
            stats[user_id] = (avg_r, count)
        
        # Fill in users with no reviews
        for uid in user_ids:
            if uid not in stats:
                stats[uid] = (None, 0)
        
        return stats
    
    @staticmethod
    def get_completed_tasks_batch(user_ids):
        """Get completed task count for multiple users in ONE query.
        
        Returns dict: {user_id: completed_count}
        """
        if not user_ids:
            return {}
        
        from app.models.task_request import TaskRequest
        results = db.session.query(
            TaskRequest.assigned_to_id,
            func.count(TaskRequest.id)
        ).filter(
            TaskRequest.assigned_to_id.in_(user_ids),
            TaskRequest.status == 'completed'
        ).group_by(TaskRequest.assigned_to_id).all()
        
        counts = {uid: 0 for uid in user_ids}
        for user_id, count in results:
            counts[user_id] = count
        return counts
    
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
        Get user's online status based on is_online flag and last_seen.
        Returns: 'online', 'recently', or 'offline'
        """
        if self.is_online:
            return 'online'
        
        if not self.last_seen:
            return 'offline'
        
        now = datetime.utcnow()
        time_diff = now - self.last_seen
        
        if time_diff < timedelta(minutes=5):
            return 'online'
        if time_diff < timedelta(minutes=30):
            return 'recently'
        return 'offline'
    
    def get_last_seen_display(self):
        """Get human-readable last seen text. None if currently online."""
        if self.is_online:
            return None
        
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
    
    def get_job_alert_prefs(self) -> dict:
        """Get job alert preferences as a dictionary."""
        if self.job_alert_preferences:
            try:
                return json.loads(self.job_alert_preferences)
            except (json.JSONDecodeError, TypeError):
                return DEFAULT_JOB_ALERT_PREFERENCES.copy()
        return DEFAULT_JOB_ALERT_PREFERENCES.copy()
    
    def set_job_alert_prefs(self, prefs: dict):
        """Set job alert preferences from a dictionary."""
        self.job_alert_preferences = json.dumps(prefs) if prefs else None
    
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
            'rating': self.rating,
            'review_count': self.review_count,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'is_online': self.is_online,
            'online_status': self.get_online_status(),
            'last_seen_display': self.get_last_seen_display(),
            'job_alert_preferences': self.get_job_alert_prefs(),
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
            'rating': self.rating,
            'review_count': self.review_count,
            'created_at': self.created_at.isoformat(),
            'is_online': self.is_online,
            'online_status': self.get_online_status(),
            'last_seen_display': self.get_last_seen_display()
        }
    
    def __repr__(self):
        return f'<User {self.username}>'
