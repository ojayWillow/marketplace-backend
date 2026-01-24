"""Skills routes for managing user skills and skill catalog."""

from flask import Blueprint, request, jsonify
from app import db
from app.models import Skill, UserSkill, User
from app.utils import token_required
from sqlalchemy import or_

skills_bp = Blueprint('skills', __name__)


@skills_bp.route('/api/skills', methods=['GET'])
def get_all_skills():
    """Get all available skills with optional category filter."""
    category = request.args.get('category')
    search = request.args.get('search')
    
    query = Skill.query.filter_by(is_active=True)
    
    if category:
        query = query.filter_by(category=category)
    
    if search:
        search_term = f'%{search}%'
        query = query.filter(
            or_(
                Skill.name.ilike(search_term),
                Skill.key.ilike(search_term)
            )
        )
    
    skills = query.order_by(Skill.category, Skill.name).all()
    
    return jsonify({
        'skills': [skill.to_dict() for skill in skills],
        'total': len(skills)
    }), 200


@skills_bp.route('/api/skills/categories', methods=['GET'])
def get_skill_categories():
    """Get all unique skill categories."""
    categories = db.session.query(Skill.category).distinct().filter_by(is_active=True).all()
    
    return jsonify({
        'categories': [cat[0] for cat in categories]
    }), 200


@skills_bp.route('/api/skills/by-category', methods=['GET'])
def get_skills_by_category():
    """Get all skills organized by category."""
    skills = Skill.query.filter_by(is_active=True).order_by(Skill.category, Skill.name).all()
    
    # Group skills by category
    skills_by_category = {}
    for skill in skills:
        if skill.category not in skills_by_category:
            skills_by_category[skill.category] = []
        skills_by_category[skill.category].append(skill.to_dict())
    
    return jsonify({
        'skills_by_category': skills_by_category
    }), 200


@skills_bp.route('/api/users/<int:user_id>/skills', methods=['GET'])
def get_user_skills(user_id):
    """Get all skills for a specific user."""
    user = User.query.get_or_404(user_id)
    
    # Use joined loading to prevent N+1 queries
    user_skills = UserSkill.query.filter_by(user_id=user_id).all()
    
    return jsonify({
        'user_id': user_id,
        'username': user.username,
        'skills': [us.to_dict(include_skill=True) for us in user_skills],
        'total': len(user_skills)
    }), 200


@skills_bp.route('/api/users/me/skills', methods=['GET'])
@token_required
def get_my_skills(current_user_id):
    """Get current user's skills."""
    user_skills = UserSkill.query.filter_by(user_id=current_user_id).all()
    
    return jsonify({
        'skills': [us.to_dict(include_skill=True) for us in user_skills],
        'total': len(user_skills)
    }), 200


@skills_bp.route('/api/users/me/skills', methods=['POST'])
@token_required
def add_user_skill(current_user_id):
    """Add a skill to current user's profile."""
    data = request.get_json()
    
    if not data or 'skill_id' not in data:
        return jsonify({'error': 'skill_id is required'}), 400
    
    # Validate skill exists and is active
    skill = Skill.query.get(data['skill_id'])
    if not skill or not skill.is_active:
        return jsonify({'error': 'Invalid or inactive skill'}), 400
    
    # Check if user already has this skill
    existing = UserSkill.query.filter_by(
        user_id=current_user_id,
        skill_id=skill.id
    ).first()
    
    if existing:
        return jsonify({'error': 'Skill already added to your profile'}), 400
    
    # Validate proficiency level
    proficiency_level = data.get('proficiency_level', 'intermediate')
    valid_levels = ['beginner', 'intermediate', 'advanced', 'expert']
    if proficiency_level not in valid_levels:
        return jsonify({'error': f'Invalid proficiency_level. Must be one of: {", ".join(valid_levels)}'}), 400
    
    # Validate years_experience if provided
    years_experience = data.get('years_experience')
    if years_experience is not None:
        try:
            years_experience = int(years_experience)
            if years_experience < 0 or years_experience > 50:
                return jsonify({'error': 'years_experience must be between 0 and 50'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'years_experience must be a valid integer'}), 400
    
    # Create user skill
    user_skill = UserSkill(
        user_id=current_user_id,
        skill_id=skill.id,
        proficiency_level=proficiency_level,
        years_experience=years_experience
    )
    
    db.session.add(user_skill)
    db.session.commit()
    
    return jsonify({
        'message': 'Skill added successfully',
        'skill': user_skill.to_dict(include_skill=True)
    }), 201


@skills_bp.route('/api/users/me/skills/<int:user_skill_id>', methods=['PUT'])
@token_required
def update_user_skill(current_user_id, user_skill_id):
    """Update a user's skill proficiency or experience."""
    user_skill = UserSkill.query.filter_by(
        id=user_skill_id,
        user_id=current_user_id
    ).first_or_404()
    
    data = request.get_json()
    
    # Update proficiency level if provided
    if 'proficiency_level' in data:
        valid_levels = ['beginner', 'intermediate', 'advanced', 'expert']
        if data['proficiency_level'] not in valid_levels:
            return jsonify({'error': f'Invalid proficiency_level. Must be one of: {", ".join(valid_levels)}'}), 400
        user_skill.proficiency_level = data['proficiency_level']
    
    # Update years of experience if provided
    if 'years_experience' in data:
        years_experience = data['years_experience']
        if years_experience is not None:
            try:
                years_experience = int(years_experience)
                if years_experience < 0 or years_experience > 50:
                    return jsonify({'error': 'years_experience must be between 0 and 50'}), 400
                user_skill.years_experience = years_experience
            except (ValueError, TypeError):
                return jsonify({'error': 'years_experience must be a valid integer'}), 400
        else:
            user_skill.years_experience = None
    
    db.session.commit()
    
    return jsonify({
        'message': 'Skill updated successfully',
        'skill': user_skill.to_dict(include_skill=True)
    }), 200


@skills_bp.route('/api/users/me/skills/<int:user_skill_id>', methods=['DELETE'])
@token_required
def delete_user_skill(current_user_id, user_skill_id):
    """Remove a skill from current user's profile."""
    user_skill = UserSkill.query.filter_by(
        id=user_skill_id,
        user_id=current_user_id
    ).first_or_404()
    
    db.session.delete(user_skill)
    db.session.commit()
    
    return jsonify({
        'message': 'Skill removed successfully'
    }), 200


@skills_bp.route('/api/users/search-by-skills', methods=['POST'])
def search_users_by_skills():
    """Search for users who have specific skills."""
    data = request.get_json()
    
    if not data or 'skill_ids' not in data:
        return jsonify({'error': 'skill_ids array is required'}), 400
    
    skill_ids = data['skill_ids']
    if not isinstance(skill_ids, list) or len(skill_ids) == 0:
        return jsonify({'error': 'skill_ids must be a non-empty array'}), 400
    
    # Get users who have ANY of the specified skills
    # Use distinct to avoid duplicates if user has multiple matching skills
    users = db.session.query(User).join(UserSkill).filter(
        UserSkill.skill_id.in_(skill_ids),
        User.is_active == True
    ).distinct().all()
    
    # Include their skills in the response
    results = []
    for user in users:
        user_dict = user.to_public_dict()
        # Get user's skills that match the search
        matching_skills = UserSkill.query.filter(
            UserSkill.user_id == user.id,
            UserSkill.skill_id.in_(skill_ids)
        ).all()
        user_dict['matching_skills'] = [us.to_dict(include_skill=True) for us in matching_skills]
        results.append(user_dict)
    
    return jsonify({
        'users': results,
        'total': len(results)
    }), 200
