from app import db
from datetime import datetime

class TaskApplication(db.Model):
    __tablename__ = 'task_applications'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task_requests.id'), nullable=False)
    applicant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text)  # Optional message from applicant
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    task = db.relationship('TaskRequest', backref=db.backref('applications', lazy=True))
    applicant = db.relationship('User', backref=db.backref('task_applications', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'applicant_id': self.applicant_id,
            'applicant_name': self.applicant.full_name if self.applicant else 'Unknown',
            'applicant_avatar': self.applicant.avatar_url if self.applicant else None,
            'applicant_rating': self.applicant.average_rating() if self.applicant else 0.0,
            'message': self.message,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
