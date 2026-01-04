"""Task request routes for quick help services marketplace."""

from flask import Blueprint, request, jsonify
from app import db
from app.models import TaskRequest, User
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2
from functools import wraps
import jwt
import os

tasks_bp = Blueprint('tasks', __name__)

# IMPORTANT: Use JWT_SECRET_KEY consistently with auth.py
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')


def token_required(f):
    """Decorator to require valid JWT token - same method as auth.py"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            # Remove 'Bearer ' prefix
            token = auth_header.split(' ')[1] if ' ' in auth_header else auth_header
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            current_user_id = payload['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except Exception as e:
            return jsonify({'error': 'Token is invalid', 'details': str(e)}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorated


def distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two coordinates."""
    R = 6371  # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


@tasks_bp.route('/my', methods=['GET'])
@token_required
def get_my_tasks(current_user_id):
    """Get tasks assigned to the current user (as worker)."""
    try:
        my_tasks = TaskRequest.query.filter(
            TaskRequest.assigned_to_id == current_user_id,
            TaskRequest.status.in_(['assigned', 'accepted', 'in_progress', 'pending_confirmation'])
        ).order_by(TaskRequest.created_at.desc()).all()
        
        return jsonify({
            'tasks': [task.to_dict() for task in my_tasks],
            'total': len(my_tasks)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/created', methods=['GET'])
@token_required
def get_created_tasks(current_user_id):
    """Get tasks created by the current user (as client)."""
    try:
        created_tasks = TaskRequest.query.filter(
            TaskRequest.creator_id == current_user_id
        ).order_by(TaskRequest.created_at.desc()).all()
        
        return jsonify({
            'tasks': [task.to_dict() for task in created_tasks],
            'total': len(created_tasks)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('', methods=['GET'])
def get_tasks():
    """Get task requests with filtering and geolocation."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', 'open')
        category = request.args.get('category')
        latitude = request.args.get('latitude', type=float)
        longitude = request.args.get('longitude', type=float)
        radius = request.args.get('radius', 10, type=float)
        
        query = TaskRequest.query.filter_by(status=status)
        
        if category:
            query = query.filter_by(category=category)
        
        tasks = query.paginate(page=page, per_page=per_page)
        
        results = []
        for task in tasks.items:
            if latitude and longitude:
                dist = distance(latitude, longitude, task.latitude, task.longitude)
                if dist <= radius:
                    task_dict = task.to_dict()
                    task_dict['distance'] = round(dist, 2)
                    results.append(task_dict)
            else:
                results.append(task.to_dict())
        
        return jsonify({
            'tasks': results,
            'total': len(results),
            'page': page
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """Get a specific task request by ID."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        return jsonify(task.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('', methods=['POST'])
def create_task():
    """Create a new task request."""
    try:
        data = request.get_json()
        
        if not all(k in data for k in ['title', 'description', 'category', 'creator_id', 'latitude', 'longitude', 'location']):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Parse deadline if provided
        deadline = None
        if data.get('deadline'):
            try:
                deadline = datetime.fromisoformat(data['deadline'])
            except ValueError:
                return jsonify({'error': 'Invalid deadline format. Use ISO format (YYYY-MM-DDTHH:MM)'}), 400
        
        task = TaskRequest(
            title=data['title'],
            description=data['description'],
            category=data['category'],
            location=data['location'],
            latitude=data['latitude'],
            longitude=data['longitude'],
            creator_id=data['creator_id'],
            budget=data.get('budget'),
            deadline=deadline,
            priority=data.get('priority', 'normal'),
            is_urgent=data.get('is_urgent', False)
        )
        
        db.session.add(task)
        db.session.commit()
        
        return jsonify({
            'message': 'Task created successfully',
            'task': task.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/<int:task_id>', methods=['PUT'])
@token_required
def update_task(current_user_id, task_id):
    """Update an existing task (only creator can update, only if status is 'open')."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Only the creator can update
        if task.creator_id != current_user_id:
            return jsonify({'error': 'Only the task creator can update this task'}), 403
        
        # Can only update open tasks
        if task.status != 'open':
            return jsonify({'error': 'Only open tasks can be edited'}), 400
        
        data = request.get_json()
        
        # Update allowed fields
        if 'title' in data:
            task.title = data['title']
        if 'description' in data:
            task.description = data['description']
        if 'category' in data:
            task.category = data['category']
        if 'location' in data:
            task.location = data['location']
        if 'latitude' in data:
            task.latitude = data['latitude']
        if 'longitude' in data:
            task.longitude = data['longitude']
        if 'budget' in data:
            task.budget = data['budget']
        if 'priority' in data:
            task.priority = data['priority']
        if 'is_urgent' in data:
            task.is_urgent = data['is_urgent']
        
        # Parse deadline if provided
        if 'deadline' in data:
            if data['deadline']:
                try:
                    task.deadline = datetime.fromisoformat(data['deadline'])
                except ValueError:
                    return jsonify({'error': 'Invalid deadline format. Use ISO format (YYYY-MM-DDTHH:MM)'}), 400
            else:
                task.deadline = None
        
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Task updated successfully',
            'task': task.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/<int:task_id>/accept', methods=['POST'])
def accept_task(task_id):
    """Accept and assign task to a user."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        if task.status != 'open':
            return jsonify({'error': 'Task is no longer available'}), 400
        
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
        
        # Can't accept your own task
        if task.creator_id == user_id:
            return jsonify({'error': 'You cannot accept your own task'}), 400
        
        task.assigned_to_id = user_id
        task.status = 'assigned'
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Task accepted successfully',
            'task': task.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/<int:task_id>/mark-done', methods=['POST'])
@token_required
def mark_task_done(current_user_id, task_id):
    """Worker marks task as done - awaiting creator confirmation."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Only the assigned worker can mark as done
        if task.assigned_to_id != current_user_id:
            return jsonify({'error': 'Only the assigned worker can mark this task as done'}), 403
        
        if task.status not in ['assigned', 'in_progress']:
            return jsonify({'error': 'Task cannot be marked as done in current status'}), 400
        
        task.status = 'pending_confirmation'
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Task marked as done. Waiting for creator confirmation.',
            'task': task.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/<int:task_id>/confirm', methods=['POST'])
@token_required
def confirm_task_completion(current_user_id, task_id):
    """Creator confirms task completion."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Only the creator can confirm completion
        if task.creator_id != current_user_id:
            return jsonify({'error': 'Only the task creator can confirm completion'}), 403
        
        if task.status != 'pending_confirmation':
            return jsonify({'error': 'Task is not pending confirmation'}), 400
        
        task.status = 'completed'
        task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Task completed! Both parties can now leave reviews.',
            'task': task.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/<int:task_id>/dispute', methods=['POST'])
@token_required
def dispute_task(current_user_id, task_id):
    """Creator disputes that task was completed properly."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Only the creator can dispute
        if task.creator_id != current_user_id:
            return jsonify({'error': 'Only the task creator can dispute'}), 403
        
        if task.status != 'pending_confirmation':
            return jsonify({'error': 'Task is not pending confirmation'}), 400
        
        data = request.get_json() or {}
        reason = data.get('reason', '')
        
        task.status = 'disputed'
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Task has been disputed. Please resolve with the worker.',
            'task': task.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/<int:task_id>/cancel', methods=['POST'])
@token_required
def cancel_task(current_user_id, task_id):
    """Cancel a task (only creator can cancel, only if not yet completed)."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Only the creator can cancel
        if task.creator_id != current_user_id:
            return jsonify({'error': 'Only the task creator can cancel'}), 403
        
        if task.status in ['completed', 'cancelled']:
            return jsonify({'error': 'Task cannot be cancelled'}), 400
        
        task.status = 'cancelled'
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Task has been cancelled.',
            'task': task.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
