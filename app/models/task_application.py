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
        
        # Count completed tasks for applicant
        completed_tasks_count = 0
        if self.applicant:
            from app.models.task_request import TaskRequest
            completed_tasks_count = TaskRequest.query.filter_by(
                assigned_to_id=self.applicant_id,
                status='completed'
            ).count()
        
        # Count reviews received by applicant
        review_count = 0
        if self.applicant:
            from app.models.review import Review
            review_count = Review.query.filter_by(reviewee_id=self.applicant_id).count()
        
        return {
            'id': self.id,
            'task_id': self.task_id,
            'applicant_id': self.applicant_id,
            'applicant_name': applicant_name,
            'applicant_email': self.applicant.email if self.applicant else None,
            'applicant_avatar': self.applicant.profile_picture_url or self.applicant.avatar_url if self.applicant else None,
            'applicant_rating': self.applicant.reputation_score if self.applicant else 0,
            'applicant_review_count': review_count,
            'applicant_completed_tasks': completed_tasks_count,
            'applicant_member_since': self.applicant.created_at.isoformat() if self.applicant and self.applicant.created_at else None,
            'applicant_bio': self.applicant.bio if self.applicant else None,
            'applicant_city': self.applicant.city if self.applicant else None,
            'message': self.message,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
