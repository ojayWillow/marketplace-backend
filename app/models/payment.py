"""Payment model for tracking Revolut payment orders."""

from datetime import datetime
from app import db


class Payment(db.Model):
    """Tracks Revolut payment orders for paid features.
    
    Each payment links a user to a paid feature (urgent, promote, boost)
    on a specific entity (task or offering).
    """
    
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    revolut_order_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Payment type: 'urgent_task', 'promote_task', 'promote_offering', 'boost_offering'
    type = db.Column(db.String(30), nullable=False)
    
    # The task_request.id or offering.id this payment applies to
    entity_id = db.Column(db.Integer, nullable=False)
    
    # Amount in cents (e.g. 200 = €2.00)
    amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), default='EUR', nullable=False)
    
    # 'pending', 'completed', 'failed', 'expired'
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationship to user
    user = db.relationship('User', backref=db.backref('payments', lazy='dynamic'))
    
    # Valid payment types and their prices in cents
    PRICES = {
        'urgent_task': 200,       # €2.00
        'promote_task': 100,      # €1.00
        'promote_offering': 100,  # €1.00
        'boost_offering': 100,    # €1.00
    }
    
    # Map payment type to the model it applies to
    ENTITY_TYPES = {
        'urgent_task': 'task_request',
        'promote_task': 'task_request',
        'promote_offering': 'offering',
        'boost_offering': 'offering',
    }
    
    @classmethod
    def get_price(cls, payment_type):
        """Get the price in cents for a payment type."""
        return cls.PRICES.get(payment_type)
    
    @classmethod
    def is_valid_type(cls, payment_type):
        """Check if a payment type is valid."""
        return payment_type in cls.PRICES
    
    def to_dict(self):
        """Convert payment to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'revolut_order_id': self.revolut_order_id,
            'type': self.type,
            'entity_id': self.entity_id,
            'amount': self.amount,
            'currency': self.currency,
            'status': self.status,
            'created_at': self.created_at.isoformat() + 'Z',
            'completed_at': self.completed_at.isoformat() + 'Z' if self.completed_at else None,
        }
    
    def __repr__(self):
        return f'<Payment {self.id}: {self.type} ({self.status})>'
