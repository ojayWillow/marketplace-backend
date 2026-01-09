"""Offering model for service offerings (e.g., Plumber - €20/hr)."""

from datetime import datetime
from app import db


class Offering(db.Model):
    """Offering model for services that users advertise."""
    
    __tablename__ = 'offerings'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    location = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=True)
    price_type = db.Column(db.String(20), default='hourly', nullable=False)  # 'hourly', 'fixed', 'negotiable'
    currency = db.Column(db.String(3), default='EUR', nullable=False)
    status = db.Column(db.String(20), default='active', nullable=False, index=True)  # 'active', 'paused', 'closed'
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    availability = db.Column(db.String(255), nullable=True)  # e.g., "Weekdays 9-17", "Evenings only"
    experience = db.Column(db.Text, nullable=True)  # Description of experience
    service_radius = db.Column(db.Float, default=25.0, nullable=False)  # Service area in km
    images = db.Column(db.JSON, nullable=True)  # Array of image URLs
    contact_count = db.Column(db.Integer, default=0, nullable=False)  # How many times contacted
    
    # Boost/Premium visibility fields
    is_boosted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    boost_expires_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship to creator
    creator = db.relationship('User', backref=db.backref('offerings', lazy='dynamic'))
    
    def is_boost_active(self):
        """Check if the boost is currently active (not expired)."""
        if not self.is_boosted:
            return False
        if self.boost_expires_at is None:
            return False
        return datetime.utcnow() < self.boost_expires_at
    
    def to_dict(self):
        """Convert offering to dictionary."""
        from app.models import User
        
        # Get creator info
        creator_name = None
        creator_avatar = None
        creator_rating = None
        creator_review_count = 0
        creator_completed_tasks = 0
        
        if self.creator_id:
            creator = User.query.get(self.creator_id)
            if creator:
                if creator.first_name and creator.last_name:
                    creator_name = f"{creator.first_name} {creator.last_name}"
                else:
                    creator_name = creator.username
                # Use correct field names from User model
                creator_avatar = creator.avatar_url or creator.profile_picture_url
                creator_rating = creator.reputation_score or 0
                creator_review_count = 0  # User model doesn't have review_count
                creator_completed_tasks = int(creator.completion_rate) if creator.completion_rate else 0
        
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'location': self.location,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'price': self.price,
            'price_type': self.price_type,
            'currency': self.currency,
            'status': self.status,
            'creator_id': self.creator_id,
            'creator_name': creator_name,
            'creator_avatar': creator_avatar,
            'creator_rating': creator_rating,
            'creator_review_count': creator_review_count,
            'creator_completed_tasks': creator_completed_tasks,
            'availability': self.availability,
            'experience': self.experience,
            'service_radius': self.service_radius,
            'images': self.images,
            'contact_count': self.contact_count,
            'is_boosted': self.is_boosted,
            'is_boost_active': self.is_boost_active(),
            'boost_expires_at': self.boost_expires_at.isoformat() if self.boost_expires_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<Offering {self.id}: {self.title}>'
