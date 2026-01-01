"""Review model for marketplace."""
from datetime import datetime
from app import db


class Review(db.Model):
    """Review model for ratings and feedback system."""

    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Float, nullable=False)
    content = db.Column(db.Text, nullable=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    reviewed_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'), nullable=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task_requests.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    reviewer = db.relationship('User', foreign_keys=[reviewer_id], backref='reviews_given')
    reviewed = db.relationship('User', foreign_keys=[reviewed_user_id], backref='reviews_received')

    def to_dict(self):
        """Convert review to dictionary."""
        return {
            'id': self.id,
            'rating': self.rating,
            'content': self.content,
            'reviewer_id': self.reviewer_id,
            'reviewed_user_id': self.reviewed_user_id,
            'listing_id': self.listing_id,
            'task_id': self.task_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def __repr__(self):
        return f'<Review {self.id}: {self.rating}stars>'
