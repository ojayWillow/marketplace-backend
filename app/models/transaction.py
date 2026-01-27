"""Transaction model for payment tracking."""

from datetime import datetime
from app import db


class Transaction(db.Model):
    """Transaction model for tracking payments and escrow."""
    
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task_requests.id'), nullable=False, index=True)
    payer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)  # Creator
    payee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)  # Worker (null until assigned)
    
    # Amounts in cents to avoid float issues
    amount = db.Column(db.Integer, nullable=False)  # Total amount in cents
    platform_fee = db.Column(db.Integer, nullable=False)  # Platform commission in cents
    worker_amount = db.Column(db.Integer, nullable=False)  # Amount worker receives in cents
    currency = db.Column(db.String(3), default='EUR', nullable=False)
    
    # Stripe IDs
    stripe_payment_intent_id = db.Column(db.String(255), unique=True, index=True)
    stripe_transfer_id = db.Column(db.String(255), unique=True, nullable=True)  # Set when paid to worker
    stripe_refund_id = db.Column(db.String(255), unique=True, nullable=True)  # Set when refunded
    
    # Status tracking
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    # 'pending' - Payment being processed
    # 'held' - Funds captured and held in escrow
    # 'released' - Funds transferred to worker
    # 'refunded' - Funds returned to creator
    # 'partially_refunded' - Partial refund processed
    # 'failed' - Payment failed
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    held_at = db.Column(db.DateTime, nullable=True)  # When funds captured
    released_at = db.Column(db.DateTime, nullable=True)  # When transferred to worker
    refunded_at = db.Column(db.DateTime, nullable=True)  # When refunded to creator
    
    # Metadata
    failure_reason = db.Column(db.Text, nullable=True)  # Error message if failed
    notes = db.Column(db.Text, nullable=True)  # Admin notes
    
    def to_dict(self):
        """Convert transaction to dictionary."""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'payer_id': self.payer_id,
            'payee_id': self.payee_id,
            'amount': self.amount / 100,  # Convert cents to currency
            'platform_fee': self.platform_fee / 100,
            'worker_amount': self.worker_amount / 100,
            'currency': self.currency,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'held_at': self.held_at.isoformat() if self.held_at else None,
            'released_at': self.released_at.isoformat() if self.released_at else None,
            'refunded_at': self.refunded_at.isoformat() if self.refunded_at else None,
            'failure_reason': self.failure_reason,
            'notes': self.notes
        }
    
    def __repr__(self):
        return f'<Transaction {self.id}: {self.amount/100} {self.currency} - {self.status}>'
