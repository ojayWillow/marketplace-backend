"""Task Response routes for applicants responding to task requests."""
from flask import Blueprint, request, jsonify
from app import db
from app.models import TaskResponse, TaskRequest, User
from app.services.push_notifications import (
    notify_application_received,
    notify_application_accepted,
    notify_application_rejected
)
from functools import wraps
import jwt
from datetime import datetime

task_responses_bp = Blueprint('task_responses', __name__, url_prefix='/api/task_responses')

# JWT token verification
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        try:
            token = token.split(' ')[1]
            data = jwt.decode(token, 'your-secret-key-change-in-production', algorithms=['HS256'])
            current_user_id = data['user_id']
        except Exception as e:
            return jsonify({'error': 'Token is invalid'}), 401
        return f(current_user_id, *args, **kwargs)
    return decorated

@task_responses_bp.route('', methods=['GET'])
def get_task_responses():
    """Get all task responses with optional filtering."""
    try:
        task_id = request.args.get('task_id')
        user_id = request.args.get('user_id')
        status = request.args.get('status')
        
        query = TaskResponse.query
        
        if task_id:
            query = query.filter_by(task_id=task_id)
        if user_id:
            query = query.filter_by(user_id=user_id)
        if status:
            query = query.filter_by(is_accepted=status.lower() == 'accepted')
        
        responses = query.all()
        return jsonify([r.to_dict() for r in responses]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@task_responses_bp.route('', methods=['POST'])
@token_required
def create_task_response(current_user_id):
    """Create a new task response (apply to a task)."""
    try:
        data = request.get_json()
        
        if not data or 'task_id' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        task = TaskRequest.query.get(data['task_id'])
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        if task.creator_id == current_user_id:
            return jsonify({'error': 'Cannot apply to your own task'}), 400
        
        # Check if already applied
        existing = TaskResponse.query.filter_by(
            task_id=data['task_id'],
            user_id=current_user_id
        ).first()
        
        if existing:
            return jsonify({'error': 'Already applied to this task'}), 400
        
        response = TaskResponse(
            task_id=data['task_id'],
            user_id=current_user_id,
            message=data.get('message', ''),
            is_accepted=False
        )
        
        db.session.add(response)
        db.session.commit()
        
        # Send push notification to task owner about new application
        try:
            applicant = User.query.get(current_user_id)
            applicant_name = applicant.name if applicant else 'Someone'
            task_title = task.title or 'your task'
            
            notify_application_received(
                task_owner_id=task.creator_id,
                applicant_name=applicant_name,
                task_title=task_title,
                task_id=task.id
            )
        except Exception as push_error:
            # Don't fail the request if push notification fails
            print(f'Push notification error: {push_error}')
        
        return jsonify({'message': 'Task response created', 'response': response.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@task_responses_bp.route('/<int:response_id>', methods=['GET'])
def get_task_response(response_id):
    """Get a specific task response by ID."""
    try:
        response = TaskResponse.query.get(response_id)
        if not response:
            return jsonify({'error': 'Response not found'}), 404
        return jsonify(response.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@task_responses_bp.route('/<int:response_id>', methods=['PUT'])
@token_required
def update_task_response(current_user_id, response_id):
    """Update task response - mainly for accepting/rejecting."""
    try:
        response = TaskResponse.query.get(response_id)
        if not response:
            return jsonify({'error': 'Response not found'}), 404
        
        task = TaskRequest.query.get(response.task_id)
        
        # Only task creator can accept/reject
        if task.creator_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        # Track if acceptance status changed for push notification
        was_accepted = response.is_accepted
        
        if 'is_accepted' in data:
            response.is_accepted = data['is_accepted']
            if data['is_accepted']:
                task.assigned_to_id = response.user_id
        
        if 'message' in data:
            response.message = data['message']
        
        response.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Send push notification based on acceptance/rejection
        try:
            task_title = task.title or 'a task'
            
            if 'is_accepted' in data:
                if data['is_accepted'] and not was_accepted:
                    # Application was accepted
                    notify_application_accepted(
                        applicant_id=response.user_id,
                        task_title=task_title,
                        task_id=task.id
                    )
                elif not data['is_accepted'] and was_accepted:
                    # Application was rejected (previously accepted, now not)
                    notify_application_rejected(
                        applicant_id=response.user_id,
                        task_title=task_title
                    )
                elif not data['is_accepted'] and not was_accepted:
                    # Explicitly rejecting a pending application
                    notify_application_rejected(
                        applicant_id=response.user_id,
                        task_title=task_title
                    )
        except Exception as push_error:
            # Don't fail the request if push notification fails
            print(f'Push notification error: {push_error}')
        
        return jsonify({'message': 'Response updated', 'response': response.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@task_responses_bp.route('/<int:response_id>', methods=['DELETE'])
@token_required
def delete_task_response(current_user_id, response_id):
    """Delete a task response (withdraw application)."""
    try:
        response = TaskResponse.query.get(response_id)
        if not response:
            return jsonify({'error': 'Response not found'}), 404
        
        # Only applicant or task creator can delete
        task = TaskRequest.query.get(response.task_id)
        if response.user_id != current_user_id and task.creator_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        db.session.delete(response)
        db.session.commit()
        
        return jsonify({'message': 'Response deleted'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
