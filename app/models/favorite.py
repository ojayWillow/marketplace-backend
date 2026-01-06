"""Favorite model for saving items to user's favorites/watchlist."""

from datetime import datetime
from app import db


class Favorite(db.Model):
    """Model for user favorites/watchlist items."""
    
    __tablename__ = 'favorites'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Item type: 'task', 'offering', or 'listing'
    item_type = db.Column(db.String(20), nullable=False)
    
    # Item ID (references task_requests.id, offerings.id, or listings.id)
    item_id = db.Column(db.Integer, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('favorites', lazy='dynamic'))
    
    # Unique constraint to prevent duplicate favorites
    __table_args__ = (
        db.UniqueConstraint('user_id', 'item_type', 'item_id', name='unique_user_favorite'),
    )
    
    def to_dict(self):
        """Convert favorite to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'item_type': self.item_type,
            'item_id': self.item_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def is_favorited(cls, user_id, item_type, item_id):
        """Check if an item is favorited by a user."""
        return cls.query.filter_by(
            user_id=user_id,
            item_type=item_type,
            item_id=item_id
        ).first() is not None
    
    @classmethod
    def toggle_favorite(cls, user_id, item_type, item_id):
        """Toggle favorite status for an item. Returns (is_favorited, favorite_object)."""
        existing = cls.query.filter_by(
            user_id=user_id,
            item_type=item_type,
            item_id=item_id
        ).first()
        
        if existing:
            db.session.delete(existing)
            db.session.commit()
            return False, None
        else:
            favorite = cls(
                user_id=user_id,
                item_type=item_type,
                item_id=item_id
            )
            db.session.add(favorite)
            db.session.commit()
            return True, favorite
    
    @classmethod
    def get_user_favorites(cls, user_id, item_type=None):
        """Get all favorites for a user, optionally filtered by type."""
        query = cls.query.filter_by(user_id=user_id)
        if item_type:
            query = query.filter_by(item_type=item_type)
        return query.order_by(cls.created_at.desc()).all()
