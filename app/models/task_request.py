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
    
    # Payment fields
    payment_required = db.Column(db.Boolean, default=False, nullable=False, index=True)  # Whether task requires upfront payment
    payment_status = db.Column(db.String(20), default='not_required', nullable=False, index=True)
    # 'not_required' - Task doesn't need payment
    # 'pending' - Waiting for payment
    # 'held' - Payment captured in escrow
    # 'released' - Payment sent to worker
    # 'refunded' - Payment returned to creator
    # 'partially_refunded' - Partial refund processed
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True, index=True)  # Link to payment
    
    # Note: Relationships are defined in User model with eager loading.
    # Use self.creator and self.assigned_user (backref names from User model)
    
    def to_dict(self):
        """Convert task request to dictionary.
        
        Uses relationships defined in User model to avoid N+1 queries.
        The User model defines these with backref names 'creator' and 'assigned_user'.
        """
        from app.models import User
        
        # Get creator info - try relationship first, fallback to query
        creator_name = None
        creator_avatar = None
        creator_city = None
        creator_rating = None
        creator_review_count = None
        
        if self.creator_id:
            # Use the relationship if available (eager loaded from User model)
            creator = getattr(self, 'creator', None)
            if creator is None:
                creator = User.query.get(self.creator_id)
            if creator:
                if creator.first_name and creator.last_name:
                    creator_name = f"{creator.first_name} {creator.last_name}"
                else:
                    creator_name = creator.username
                creator_avatar = creator.avatar_url
                creator_city = creator.city
                # Get rating and review_count from User model properties
                creator_rating = creator.rating
                creator_review_count = creator.review_count
        
        # Get assigned user name - try relationship first, fallback to query
        assigned_to_name = None
        if self.assigned_to_id:
            # Use the relationship if available (eager loaded from User model)
            assigned_user = getattr(self, 'assigned_user', None)
            if assigned_user is None:
                assigned_user = User.query.get(self.assigned_to_id)
            if assigned_user:
                if assigned_user.first_name and assigned_user.last_name:
                    assigned_to_name = f"{assigned_user.first_name} {assigned_user.last_name}"
                else:
                    assigned_to_name = assigned_user.username
        
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
            'creator_name': creator_name,
            'creator_avatar': creator_avatar,
            'creator_city': creator_city,
            'creator_rating': creator_rating,
            'creator_review_count': creator_review_count,
            'assigned_to_id': self.assigned_to_id,
            'assigned_to_name': assigned_to_name,
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
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'payment_required': self.payment_required,
            'payment_status': self.payment_status,
        }
    
    def __repr__(self):
        return f'<TaskRequest {self.id}: {self.title}>'
