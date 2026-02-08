"""Basic CRUD operations for tasks."""

from flask import request, jsonify
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from app import db
from app.models import TaskRequest, User, TaskApplication
from app.utils import token_required
from app.utils.auth import SECRET_KEY
from app.routes.tasks import tasks_bp
from app.routes.tasks.helpers import (
    get_bounding_box,
    distance,
    translate_task_if_needed,
)
from datetime import datetime
import jwt
import logging

logger = logging.getLogger(__name__)

DEFAULT_RADIUS_KM = 25  # Default search radius in km — keep in sync with frontend


def get_current_user_id_optional():
    """Extract user_id from token if present, return None otherwise."""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None
    try:
        token = auth_header.split(' ')[1] if ' ' in auth_header else auth_header
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload.get('user_id')
    except:
        return None


def get_pending_applications_counts(task_ids: list[int]) -> dict[int, int]:
    """
    Get pending applications count for multiple tasks in a SINGLE query.
    Returns dict mapping task_id -> count
    """
    if not task_ids:
        return {}
    
    try:
        results = db.session.query(
            TaskApplication.task_id,
            func.count(TaskApplication.id)
        ).filter(
            TaskApplication.task_id.in_(task_ids),
            TaskApplication.status == 'pending'
        ).group_by(TaskApplication.task_id).all()
        
        # Convert to dict, defaulting to 0 for tasks with no applications
        counts = {task_id: 0 for task_id in task_ids}
        for task_id, count in results:
            counts[task_id] = count
        return counts
    except Exception as e:
        logger.error(f"Error fetching application counts: {e}")
        return {task_id: 0 for task_id in task_ids}


def get_user_applied_task_ids(user_id: int | None, task_ids: list[int]) -> set[int]:
    """
    Get set of task IDs that the user has applied to (any status).
    Returns empty set if user_id is None or no applications found.
    """
    if not user_id or not task_ids:
        return set()
    
    try:
        results = db.session.query(TaskApplication.task_id).filter(
            TaskApplication.task_id.in_(task_ids),
            TaskApplication.applicant_id == user_id
        ).all()
        return {r[0] for r in results}
    except Exception as e:
        logger.error(f"Error fetching user applications: {e}")
        return set()


def batch_translate_tasks(tasks_list: list[dict], lang: str | None) -> list[dict]:
    """
    Translate multiple tasks efficiently.
    Only translates if lang is provided and translation is enabled.
    """
    if not lang or not tasks_list:
        return tasks_list
    
    # Quick check if translation is even enabled
    try:
        from app.services.translation import is_translation_enabled
        if not is_translation_enabled():
            return tasks_list
    except:
        return tasks_list
    
    # Translate each task (translation service handles caching)
    # Future optimization: could batch all texts in single API call
    for task in tasks_list:
        task = translate_task_if_needed(task, lang)
    
    return tasks_list


@tasks_bp.route('', methods=['GET'])
def get_tasks():
    """Get task requests with filtering, geolocation, and optional translation.
    
    Query params:
        - lang: Language code (lv, en, ru) for auto-translation
        - latitude, longitude: User location
        - radius: Search radius in km (default 25)
        - status: Task status filter (default 'open')
        - category: Category filter
        - page, per_page: Pagination
    
    If authenticated, each task includes:
        - has_applied: boolean indicating if current user has applied
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', 'open')
        category = request.args.get('category')
        latitude = request.args.get('latitude', type=float)
        longitude = request.args.get('longitude', type=float)
        radius = request.args.get('radius', DEFAULT_RADIUS_KM, type=float)
        lang = request.args.get('lang')
        
        # Defensive: warn if radius was explicitly sent without coordinates
        if request.args.get('radius') and (latitude is None or longitude is None):
            logger.warning(
                'GET /api/tasks: radius=%s provided without latitude/longitude — '
                'radius will be ignored, returning all tasks',
                request.args.get('radius')
            )
        
        # Get current user ID if authenticated (for has_applied check)
        current_user_id = get_current_user_id_optional()
        
        # Build base query with eager loading
        query = TaskRequest.query.options(
            joinedload(TaskRequest.creator),
            joinedload(TaskRequest.assigned_user)
        ).filter_by(status=status)
        
        if category:
            query = query.filter_by(category=category)
        
        # If location filtering is requested
        if latitude is not None and longitude is not None:
            min_lat, max_lat, min_lng, max_lng = get_bounding_box(latitude, longitude, radius)
            query = query.filter(
                TaskRequest.latitude.isnot(None),
                TaskRequest.longitude.isnot(None),
                TaskRequest.latitude >= min_lat,
                TaskRequest.latitude <= max_lat,
                TaskRequest.longitude >= min_lng,
                TaskRequest.longitude <= max_lng
            )
            
            all_tasks = query.all()
            
            # Filter by exact distance
            tasks_with_distance = []
            for task in all_tasks:
                dist = distance(latitude, longitude, task.latitude, task.longitude)
                if dist <= radius:
                    task_dict = task.to_dict()
                    task_dict['distance'] = round(dist, 2)
                    tasks_with_distance.append((task.id, task_dict))
            
            # Sort by distance
            tasks_with_distance.sort(key=lambda x: x[1]['distance'])
            
            # Pagination
            total = len(tasks_with_distance)
            start = (page - 1) * per_page
            end = start + per_page
            paginated = tasks_with_distance[start:end]
            
            # Get task IDs and dicts
            task_ids = [t[0] for t in paginated]
            tasks_list = [t[1] for t in paginated]
            
            # BATCH: Get all pending counts in ONE query
            pending_counts = get_pending_applications_counts(task_ids)
            
            # BATCH: Get user's applied task IDs in ONE query
            user_applied_ids = get_user_applied_task_ids(current_user_id, task_ids)
            
            for i, task_dict in enumerate(tasks_list):
                task_dict['pending_applications_count'] = pending_counts.get(task_ids[i], 0)
                task_dict['has_applied'] = task_ids[i] in user_applied_ids
            
            # BATCH: Translate all tasks
            tasks_list = batch_translate_tasks(tasks_list, lang)
            
            return jsonify({
                'tasks': tasks_list,
                'total': total,
                'page': page,
                'per_page': per_page,
                'has_more': end < total
            }), 200
        else:
            # No location filtering
            tasks = query.order_by(TaskRequest.created_at.desc()).paginate(page=page, per_page=per_page)
            
            # Convert to dicts and collect IDs
            task_ids = []
            tasks_list = []
            for task in tasks.items:
                task_ids.append(task.id)
                tasks_list.append(task.to_dict())
            
            # BATCH: Get all pending counts in ONE query
            pending_counts = get_pending_applications_counts(task_ids)
            
            # BATCH: Get user's applied task IDs in ONE query
            user_applied_ids = get_user_applied_task_ids(current_user_id, task_ids)
            
            for i, task_dict in enumerate(tasks_list):
                task_dict['pending_applications_count'] = pending_counts.get(task_ids[i], 0)
                task_dict['has_applied'] = task_ids[i] in user_applied_ids
            
            # BATCH: Translate all tasks
            tasks_list = batch_translate_tasks(tasks_list, lang)
            
            return jsonify({
                'tasks': tasks_list,
                'total': tasks.total,
                'page': page,
                'per_page': per_page,
                'has_more': tasks.has_next
            }), 200
            
    except Exception as e:
        logger.error(f"Error in get_tasks: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """Get a specific task request by ID.
    
    If authenticated, also returns:
        - has_applied: boolean indicating if user has applied
        - user_application: the user's application object if exists
    """
    try:
        lang = request.args.get('lang')
        
        task = TaskRequest.query.options(
            joinedload(TaskRequest.creator),
            joinedload(TaskRequest.assigned_user)
        ).get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        task_dict = task.to_dict()
        
        # Single query for this task's pending count
        pending_counts = get_pending_applications_counts([task_id])
        task_dict['pending_applications_count'] = pending_counts.get(task_id, 0)
        
        # Translate if needed
        task_dict = translate_task_if_needed(task_dict, lang)
        
        # Check if current user has applied (if authenticated)
        current_user_id = get_current_user_id_optional()
        if current_user_id:
            existing_application = TaskApplication.query.filter_by(
                task_id=task_id,
                applicant_id=current_user_id
            ).first()
            task_dict['has_applied'] = existing_application is not None
            task_dict['user_application'] = existing_application.to_dict() if existing_application else None
        else:
            task_dict['has_applied'] = False
            task_dict['user_application'] = None
        
        return jsonify(task_dict), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('', methods=['POST'])
def create_task():
    """Create a new task request."""
    try:
        data = request.get_json()
        
        logger.info(f'Creating task with data: {data}')
        
        if not all(k in data for k in ['title', 'description', 'category', 'creator_id', 'latitude', 'longitude', 'location']):
            return jsonify({'error': 'Missing required fields'}), 400
        
        deadline = None
        if data.get('deadline'):
            try:
                deadline = datetime.fromisoformat(data['deadline'])
            except ValueError:
                return jsonify({'error': 'Invalid deadline format. Use ISO format (YYYY-MM-DDTHH:MM)'}), 400
        
        # Note: difficulty field is sent by mobile app but not stored in TaskRequest model
        # We validate it here but don't pass it to the constructor
        difficulty = data.get('difficulty', 'medium')
        if difficulty not in ['easy', 'medium', 'hard']:
            return jsonify({'error': 'Invalid difficulty. Must be easy, medium, or hard'}), 400
        
        # Create task WITHOUT payment fields (they're commented out in the model)
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
            is_urgent=data.get('is_urgent', False),
            images=data.get('images')
        )
        
        db.session.add(task)
        db.session.commit()
        
        logger.info(f'Task created successfully: {task.id}, images: {task.images}')
        
        return jsonify({
            'message': 'Task created successfully',
            'task': task.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error creating task: {str(e)}', exc_info=True)
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/<int:task_id>', methods=['PUT'])
@token_required
def update_task(current_user_id, task_id):
    """Update an existing task (only creator can update, only if status is 'open')."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        if task.creator_id != current_user_id:
            return jsonify({'error': 'Only the task creator can update this task'}), 403
        
        if task.status != 'open':
            return jsonify({'error': 'Only open tasks can be edited'}), 400
        
        data = request.get_json()
        
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
        if 'images' in data:
            task.images = data['images']
        
        # Note: difficulty field is validated but not stored (TaskRequest model doesn't have this field)
        if 'difficulty' in data:
            if data['difficulty'] not in ['easy', 'medium', 'hard']:
                return jsonify({'error': 'Invalid difficulty. Must be easy, medium, or hard'}), 400
            # Field is valid but we don't set it since the model doesn't support it
        
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
