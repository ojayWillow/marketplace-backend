"""Skill models for user profile skills and matching."""

from datetime import datetime
from app import db


class Skill(db.Model):
    """Skill model - predefined skills organized by category."""
    
    __tablename__ = 'skills'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)  # e.g., 'carpentry'
    name = db.Column(db.String(100), nullable=False)  # e.g., 'Carpentry'
    category = db.Column(db.String(50), nullable=False, index=True)  # e.g., 'construction'
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def to_dict(self):
        """Convert skill to dictionary."""
        return {
            'id': self.id,
            'key': self.key,
            'name': self.name,
            'category': self.category,
            'description': self.description,
            'is_active': self.is_active
        }
    
    def __repr__(self):
        return f'<Skill {self.key}: {self.name}>'


class UserSkill(db.Model):
    """Association table for user skills with proficiency level."""
    
    __tablename__ = 'user_skills'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id', ondelete='CASCADE'), nullable=False, index=True)
    proficiency_level = db.Column(db.String(20), default='intermediate', nullable=False)  # 'beginner', 'intermediate', 'advanced', 'expert'
    years_experience = db.Column(db.Integer, nullable=True)  # Optional years of experience
    is_verified = db.Column(db.Boolean, default=False, nullable=False)  # For future skill verification
    added_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Unique constraint: user can only have each skill once
    __table_args__ = (
        db.UniqueConstraint('user_id', 'skill_id', name='unique_user_skill'),
    )
    
    # Relationships with string references to avoid circular imports
    # Use lazy='joined' for skill to prevent N+1 queries
    user = db.relationship('User', backref=db.backref('user_skills_rel', lazy='dynamic', cascade='all, delete-orphan'))
    skill = db.relationship('Skill', backref=db.backref('user_skills_rel', lazy='dynamic'), lazy='joined')
    
    def to_dict(self, include_skill=True):
        """Convert user skill to dictionary."""
        result = {
            'id': self.id,
            'user_id': self.user_id,
            'skill_id': self.skill_id,
            'proficiency_level': self.proficiency_level,
            'years_experience': self.years_experience,
            'is_verified': self.is_verified,
            'added_at': self.added_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        # Include skill details if requested (already loaded via eager loading)
        if include_skill and self.skill:
            result['skill'] = self.skill.to_dict()
        
        return result
    
    def __repr__(self):
        return f'<UserSkill user_id={self.user_id} skill_id={self.skill_id}>'
