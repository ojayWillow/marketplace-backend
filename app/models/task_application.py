from datetime import datetime
from app import db


class TaskApplication(db.Model):
    __tablename__ = 'task_applications'
    
    __table_args__ = (
        db.UniqueConstraint('task_id', 'applicant_id', name='unique_task_application'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task_requests.id'), nullable=False)
    applicant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    task = db.relationship('TaskRequest', backref='applications')
    applicant = db.relationship('User', backref='task_applications')
    
    def to_dict(self, review_stats=None, completed_counts=None):
        """Convert to dictionary.
        
        Args:
            review_stats: Optional pre-fetched dict {user_id: (avg_rating, count)}
                          from User.get_review_stats_batch(). If None, falls back
                          to per-instance query (still 1 query, not 2).
            completed_counts: Optional pre-fetched dict {user_id: count}
                              from User.get_completed_tasks_batch(). If None,
                              falls back to per-instance query.
        """
        # Build applicant name
        applicant_name = 'Unknown'
        if self.applicant:
            if self.applicant.first_name and self.applicant.last_name:
                applicant_name = f"{self.applicant.first_name} {self.applicant.last_name}"
            elif self.applicant.first_name:
                applicant_name = self.applicant.first_name
            elif self.applicant.username:
                applicant_name = self.applicant.username
        
        # Rating + review count: use batch data if available, else per-instance
        if review_stats and self.applicant_id in review_stats:
            applicant_rating, review_count = review_stats[self.applicant_id]
            applicant_rating = applicant_rating or 0
        elif self.applicant:
            applicant_rating = self.applicant.rating or 0
            review_count = self.applicant.review_count
        else:
            applicant_rating = 0
            review_count = 0
        
        # Completed tasks count: use batch data if available, else per-instance
        if completed_counts and self.applicant_id in completed_counts:
            completed_tasks_count = completed_counts[self.applicant_id]
        elif self.applicant:
            from app.models.task_request import TaskRequest
            completed_tasks_count = TaskRequest.query.filter_by(
                assigned_to_id=self.applicant_id,
                status='completed'
            ).count()
        else:
            completed_tasks_count = 0
        
        # Avatar URL
        applicant_avatar = None
        if self.applicant:
            applicant_avatar = self.applicant.profile_picture_url or self.applicant.avatar_url
        
        return {
            'id': self.id,
            'task_id': self.task_id,
            'applicant_id': self.applicant_id,
            'applicant_name': applicant_name,
            'applicant_email': self.applicant.email if self.applicant else None,
            'applicant_avatar': applicant_avatar,
            'applicant_rating': applicant_rating,
            'applicant_review_count': review_count,
            'applicant_completed_tasks': completed_tasks_count,
            'applicant_member_since': self.applicant.created_at.isoformat() if self.applicant and self.applicant.created_at else None,
            'applicant_bio': self.applicant.bio if self.applicant else None,
            'applicant_city': self.applicant.city if self.applicant else None,
            'message': self.message,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def to_dict_batch(applications):
        """Serialize multiple applications efficiently with batch-loaded stats.
        
        Instead of N+1 queries, loads all review stats and completed task
        counts in 2 queries total regardless of how many applications.
        
        Args:
            applications: List of TaskApplication instances
            
        Returns:
            List of dicts
        """
        if not applications:
            return []
        
        from app.models.user import User
        
        # Collect unique applicant IDs
        applicant_ids = list({app.applicant_id for app in applications})
        
        # 2 batch queries instead of 3N queries
        review_stats = User.get_review_stats_batch(applicant_ids)
        completed_counts = User.get_completed_tasks_batch(applicant_ids)
        
        return [
            app.to_dict(review_stats=review_stats, completed_counts=completed_counts)
            for app in applications
        ]
