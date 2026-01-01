"""Task response for user applications."""
from datetime import datetime
from app import db


class TaskResponse(db.Model):
    """TaskResponse model for task applications and claiming."""

    __tablename__ = 'task_responses'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task_requests.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    message = db.Column(db.Text, nullable=True)
    is_accepted = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    task = db.relationship('TaskRequest', backref='responses')
    user = db.relationship('User', backref='task_responses')

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'user_id': self.user_id,
            'message': self.message,
            'is_accepted': self.is_accepted,
            'created_at': self.created_at.isoformat()
        }
