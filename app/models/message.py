"""Message and Conversation models for user-to-user communication."""

from datetime import datetime
from app import db


def utc_isoformat(dt):
    """Convert datetime to ISO format with Z suffix to indicate UTC."""
    if dt is None:
        return None
    return dt.isoformat() + 'Z'


class Conversation(db.Model):
    """Conversation model representing a chat between two users."""
    
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    participant_1_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    participant_2_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task_requests.id'), nullable=True, index=True)
    offering_id = db.Column(db.Integer, db.ForeignKey('offerings.id'), nullable=True, index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    participant_1 = db.relationship('User', foreign_keys=[participant_1_id], backref='conversations_as_p1')
    participant_2 = db.relationship('User', foreign_keys=[participant_2_id], backref='conversations_as_p2')
    task = db.relationship('TaskRequest', backref='conversations')
    offering = db.relationship('Offering', backref='conversations')
    messages = db.relationship('Message', backref='conversation', lazy='dynamic', order_by='Message.created_at')
    
    def get_other_participant(self, user_id):
        """Get the other participant in the conversation."""
        if self.participant_1_id == user_id:
            return self.participant_2
        return self.participant_1
    
    def get_last_message(self):
        """Get the most recent message in the conversation."""
        return self.messages.order_by(Message.created_at.desc()).first()
    
    def get_unread_count(self, user_id):
        """Get count of unread messages for a user."""
        return self.messages.filter(
            Message.sender_id != user_id,
            Message.is_read == False
        ).count()
    
    def to_dict(self, current_user_id=None):
        """Convert conversation to dictionary."""
        other_participant = None
        unread_count = 0
        
        if current_user_id:
            other_user = self.get_other_participant(current_user_id)
            if other_user:
                other_participant = {
                    'id': other_user.id,
                    'username': other_user.username,
                    'first_name': other_user.first_name,
                    'last_name': other_user.last_name,
                    'avatar_url': other_user.avatar_url or other_user.profile_picture_url,
                    'is_verified': other_user.is_verified,
                    'online_status': other_user.get_online_status(),
                    'last_seen_display': other_user.get_last_seen_display()
                }
            unread_count = self.get_unread_count(current_user_id)
        
        last_message = self.get_last_message()
        
        return {
            'id': self.id,
            'participant_1_id': self.participant_1_id,
            'participant_2_id': self.participant_2_id,
            'task_id': self.task_id,
            'offering_id': self.offering_id,
            'other_participant': other_participant,
            'unread_count': unread_count,
            'last_message': last_message.to_dict() if last_message else None,
            'created_at': utc_isoformat(self.created_at),
            'updated_at': utc_isoformat(self.updated_at)
        }
    
    def __repr__(self):
        return f'<Conversation {self.id}: User {self.participant_1_id} <-> User {self.participant_2_id}>'


class Message(db.Model):
    """Message model for individual messages within a conversation."""
    
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    
    # Attachments
    attachment_url = db.Column(db.String(500), nullable=True)
    attachment_type = db.Column(db.String(20), nullable=True)  # 'image', 'file', 'video', 'audio'
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    sender = db.relationship('User', backref='sent_messages')
    
    def to_dict(self):
        """Convert message to dictionary."""
        sender_data = None
        if self.sender:
            sender_data = {
                'id': self.sender.id,
                'username': self.sender.username,
                'first_name': self.sender.first_name,
                'last_name': self.sender.last_name,
                'avatar_url': self.sender.avatar_url or self.sender.profile_picture_url,
                'online_status': self.sender.get_online_status(),
                'last_seen_display': self.sender.get_last_seen_display()
            }
        
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'sender_id': self.sender_id,
            'sender': sender_data,
            'content': self.content,
            'is_read': self.is_read,
            'attachment_url': self.attachment_url,
            'attachment_type': self.attachment_type,
            'created_at': utc_isoformat(self.created_at)
        }
    
    def __repr__(self):
        return f'<Message {self.id} in Conversation {self.conversation_id}>'
