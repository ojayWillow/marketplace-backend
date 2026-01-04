from datetime import datetime
from app import db

class TaskApplication(db.Model):
    __tablename__ = 'task_applications'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task_requests.id'), nullable=False)
    applicant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=True)  # Optional application message
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    task = db.relationship('TaskRequest', backref='applications')
    applicant = db.relationship('User', backref='task_applications')
    
    def to_dict(self):
        # Build applicant name from first_name and last_name
        applicant_name = 'Unknown'
        if self.applicant:
            if self.applicant.first_name and self.applicant.last_name:
                applicant_name = f"{self.applicant.first_name} {self.applicant.last_name}"
            elif self.applicant.first_name:
                applicant_name = self.applicant.first_name
            elif self.applicant.username:
                applicant_name = self.applicant.username
        
        return {
            'id': self.id,
            'task_id': self.task_id,
            'applicant_id': self.applicant_id,
            'applicant_name': applicant_name,
            'applicant_email': self.applicant.email if self.applicant else None,
            'message': self.message,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }