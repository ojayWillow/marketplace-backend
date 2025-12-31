"""Task Request model for quick help services."""

from datetime import datetime
from app import db


class TaskRequest(db.Model):
    """TaskRequest model for quick help/services segment."""
    
    __tablename__ = 'task_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)  # 'delivery', 'cleaning', 'repair', 'tutoring', etc.
    budget = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(3), default='EUR', nullable=False)
    location = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    radius = db.Column(db.Float, default=5.0, nullable=False)  # Search radius in km
    required_skills = db.Column(db.JSON, nullable=True)  # Array of required skills
    images = db.Column(db.JSON, nullable=True)  # Array of image URLs
    priority = db.Column(db.String(20), default='normal', nullable=False)  # 'low', 'normal', 'high', 'urgent'
    status = db.Column(db.String(20), default='open', nullable=False, index=True)  # 'open', 'assigned', 'in_progress', 'completed', 'cancelled'
    deadline = db.Column(db.DateTime, nullable=True)
    responses_count = db.Column(db.Integer, default=0, nullable=False)
    is_urgent = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        """Convert task request to dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'budget': self.budget,
            'currency': self.currency,
            'location': self.location,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'creator_id': self.creator_id,
            'creator': self.creator.username if self.creator else None,
            'assigned_to_id': self.assigned_to_id,
            'assigned_to': self.assigned_to.username if self.assigned_to else None,
            'radius': self.radius,
            'required_skills': self.required_skills,
            'images': self.images,
            'priority': self.priority,
            'status': self.status,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'responses_count': self.responses_count,
            'is_urgent': self.is_urgent,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
    
    def __repr__(self):
        return f'<TaskRequest {self.id}: {self.title}>'
