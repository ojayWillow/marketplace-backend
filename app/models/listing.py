"""Listing model for classifieds marketplace."""

from datetime import datetime
from app import db


class Listing(db.Model):
    """Listing model for buy/sell classifieds segment."""
    
    __tablename__ = 'listings'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    subcategory = db.Column(db.String(50), nullable=True)
    condition = db.Column(db.String(20), nullable=True)  # 'new', 'like_new', 'used', 'refurbished'
    price = db.Column(db.Float, nullable=False, index=True)
    currency = db.Column(db.String(3), default='EUR', nullable=False)
    location = db.Column(db.String(255), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    image_urls = db.Column(db.JSON, nullable=True)  # Array of image URLs
    tags = db.Column(db.JSON, nullable=True)  # Array of tags
    views_count = db.Column(db.Integer, default=0, nullable=False)
    listing_type = db.Column(db.String(20), default='sale', nullable=False)  # 'sale', 'purchase', 'exchange'
    status = db.Column(db.String(20), default='active', nullable=False, index=True)  # 'active', 'sold', 'archived', 'pending'
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    is_negotiable = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        """Convert listing to dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'subcategory': self.subcategory,
            'condition': self.condition,
            'price': self.price,
            'currency': self.currency,
            'location': self.location,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'seller_id': self.seller_id,
            'seller': self.seller.username if self.seller else None,
            'image_urls': self.image_urls,
            'tags': self.tags,
            'views_count': self.views_count,
            'listing_type': self.listing_type,
            'status': self.status,
            'is_featured': self.is_featured,
            'is_negotiable': self.is_negotiable,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
    
    def __repr__(self):
        return f'<Listing {self.id}: {self.title}>'
