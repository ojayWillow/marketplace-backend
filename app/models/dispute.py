"""Dispute model for handling task disputes between users."""

from datetime import datetime
from app import db


class Dispute(db.Model):
    """Dispute model for task conflict resolution."""
    
    __tablename__ = 'disputes'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task_requests.id'), nullable=False, index=True)
    
    # Who filed the dispute
    filed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Who the dispute is against
    filed_against_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Dispute details
    reason = db.Column(db.String(100), nullable=False)  # 'work_quality', 'no_show', 'incomplete', etc.
    description = db.Column(db.Text, nullable=False)
    evidence_images = db.Column(db.JSON, nullable=True)  # Array of image URLs
    
    # Status: 'open', 'under_review', 'resolved'
    status = db.Column(db.String(20), default='open', nullable=False, index=True)
    
    # Resolution (filled when resolved)
    resolution = db.Column(db.String(20), nullable=True)  # 'refund', 'pay_worker', 'partial', 'cancelled'
    resolution_notes = db.Column(db.Text, nullable=True)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    # Response from the other party
    response_description = db.Column(db.Text, nullable=True)
    response_images = db.Column(db.JSON, nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    task = db.relationship('TaskRequest', backref=db.backref('disputes', lazy='dynamic'))
    filed_by = db.relationship('User', foreign_keys=[filed_by_id], backref=db.backref('disputes_filed', lazy='dynamic'))
    filed_against = db.relationship('User', foreign_keys=[filed_against_id], backref=db.backref('disputes_against', lazy='dynamic'))
    resolved_by = db.relationship('User', foreign_keys=[resolved_by_id])
    
    # Valid reasons for disputes
    VALID_REASONS = [
        'work_quality',    # Work doesn't meet expectations
        'no_show',         # Worker/Creator didn't show up
        'incomplete',      # Work not finished
        'different_work',  # Work done is different from agreed
        'communication',   # Not responding, ghosting
        'safety',          # Safety concerns
        'other'            # Other issues
    ]
    
    REASON_LABELS = {
        'work_quality': 'Poor Work Quality',
        'no_show': 'No Show',
        'incomplete': 'Incomplete Work',
        'different_work': 'Work Different Than Agreed',
        'communication': 'Communication Problems',
        'safety': 'Safety Concern',
        'other': 'Other Issue'
    }
    
    def to_dict(self):
        """Convert dispute to dictionary."""
        from app.models import User
        
        # Get user info
        filed_by_user = User.query.get(self.filed_by_id)
        filed_against_user = User.query.get(self.filed_against_id)
        
        filed_by_name = None
        if filed_by_user:
            filed_by_name = f"{filed_by_user.first_name} {filed_by_user.last_name}".strip() or filed_by_user.username
            
        filed_against_name = None
        if filed_against_user:
            filed_against_name = f"{filed_against_user.first_name} {filed_against_user.last_name}".strip() or filed_against_user.username
        
        return {
            'id': self.id,
            'task_id': self.task_id,
            'task_title': self.task.title if self.task else None,
            'filed_by_id': self.filed_by_id,
            'filed_by_name': filed_by_name,
            'filed_against_id': self.filed_against_id,
            'filed_against_name': filed_against_name,
            'reason': self.reason,
            'reason_label': self.REASON_LABELS.get(self.reason, self.reason),
            'description': self.description,
            'evidence_images': self.evidence_images or [],
            'status': self.status,
            'resolution': self.resolution,
            'resolution_notes': self.resolution_notes,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'response_description': self.response_description,
            'response_images': self.response_images or [],
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
    
    def __repr__(self):
        return f'<Dispute {self.id}: Task {self.task_id} - {self.status}>'
