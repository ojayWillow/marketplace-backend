"""Push subscription model for web push notifications."""

from app import db
from datetime import datetime


class PushSubscription(db.Model):
    """Stores user push notification subscriptions.
    
    Each user can have multiple subscriptions (different devices/browsers).
    The subscription contains the endpoint URL and encryption keys needed
    to send push notifications via the Web Push protocol.
    """
    __tablename__ = 'push_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # The push service endpoint URL (unique per subscription)
    endpoint = db.Column(db.Text, nullable=False, unique=True)
    
    # Encryption keys for Web Push
    p256dh_key = db.Column(db.Text, nullable=False)  # Public key
    auth_key = db.Column(db.Text, nullable=False)    # Auth secret
    
    # Optional: track device/browser info
    user_agent = db.Column(db.String(500), nullable=True)
    device_name = db.Column(db.String(100), nullable=True)  # e.g., "iPhone", "Chrome on Windows"
    
    # Notification preferences
    notify_messages = db.Column(db.Boolean, default=True)      # New messages
    notify_applications = db.Column(db.Boolean, default=True)  # Job applications
    notify_tasks = db.Column(db.Boolean, default=True)         # Task updates
    notify_new_jobs = db.Column(db.Boolean, default=True)      # New jobs nearby
    
    # Status tracking
    is_active = db.Column(db.Boolean, default=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    failed_count = db.Column(db.Integer, default=0)  # Track failed sends
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = db.relationship('User', backref=db.backref('push_subscriptions', lazy='dynamic'))

    def __repr__(self):
        return f'<PushSubscription {self.id} user={self.user_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'device_name': self.device_name,
            'notify_messages': self.notify_messages,
            'notify_applications': self.notify_applications,
            'notify_tasks': self.notify_tasks,
            'notify_new_jobs': self.notify_new_jobs,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
        }

    def get_subscription_info(self):
        """Return subscription info in format needed by pywebpush."""
        return {
            'endpoint': self.endpoint,
            'keys': {
                'p256dh': self.p256dh_key,
                'auth': self.auth_key
            }
        }

    def mark_used(self):
        """Update last_used_at timestamp."""
        self.last_used_at = datetime.utcnow()
        self.failed_count = 0  # Reset failed count on success

    def mark_failed(self):
        """Increment failed count. Deactivate if too many failures."""
        self.failed_count += 1
        if self.failed_count >= 3:
            self.is_active = False
