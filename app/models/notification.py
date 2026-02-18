"""Notification model for user notifications."""

import json
from app import db
from datetime import datetime


class Notification(db.Model):
    """Model for storing user notifications."""
    
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # e.g., 'application_accepted', 'task_assigned', etc.
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    # Dynamic data for i18n - stores values like task_title, applicant_name, worker_name
    # Frontend uses this + type to render localized notifications
    data = db.Column(db.Text, nullable=True)  # JSON string
    
    # Related entity info (for navigation)
    related_type = db.Column(db.String(50))  # 'task', 'application', 'review', etc.
    related_id = db.Column(db.Integer)
    
    # Status
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic'))
    
    def __repr__(self):
        return f'<Notification {self.id} for User {self.user_id}: {self.type}>'
    
    def set_data(self, data_dict: dict):
        """Set the data field from a dictionary."""
        self.data = json.dumps(data_dict) if data_dict else None
    
    def get_data(self) -> dict:
        """Get the data field as a dictionary."""
        if self.data:
            try:
                return json.loads(self.data)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    def to_dict(self):
        """Convert notification to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'data': self.get_data(),  # Parse JSON and return as dict
            'related_type': self.related_type,
            'related_id': self.related_id,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
    
    def mark_as_read(self):
        """Mark notification as read."""
        self.is_read = True
        self.read_at = datetime.utcnow()


# Notification type constants
class NotificationType:
    APPLICATION_ACCEPTED = 'application_accepted'
    APPLICATION_REJECTED = 'application_rejected'
    NEW_APPLICATION = 'new_application'
    TASK_ASSIGNED = 'task_assigned'
    TASK_COMPLETED = 'task_completed'
    TASK_MARKED_DONE = 'task_marked_done'
    TASK_DISPUTED = 'task_disputed'
    TASK_CANCELLED = 'task_cancelled'
    NEW_REVIEW = 'new_review'
    NEW_MESSAGE = 'new_message'
    REVIEW_REMINDER = 'review_reminder'
    NEW_TASK_NEARBY = 'new_task_nearby'
