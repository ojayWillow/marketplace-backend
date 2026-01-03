"""Task request routes for quick help services marketplace."""

from flask import Blueprint, request, jsonify
from app import db
from app.models import TaskRequest, User
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

tasks_bp = Blueprint('tasks', __name__)


def distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two coordinates."""
    R = 6371  # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


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
                # Handle ISO format: "2026-01-05T19:03"
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


@tasks_bp.route('/<int:task_id>/accept', methods=['POST'])
def accept_task(task_id):
    """Accept and assign task to a user."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
        
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


@tasks_bp.route('/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    """Mark a task as completed."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        task.status = 'completed'
        task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Task completed successfully',
            'task': task.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500