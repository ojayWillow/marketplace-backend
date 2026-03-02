"""Basic CRUD operations for tasks."""

from flask import request, jsonify
from sqlalchemy.orm import joinedload
from sqlalchemy import func, case
from app import db
from app.models import TaskRequest, User, TaskApplication
from app.utils import token_required
from app.utils.auth import _resolve_user_from_token
from app.routes.tasks import tasks_bp
from app.routes.tasks.helpers import (
    get_bounding_box,
    distance,
    translate_task_if_needed,
)
from app.routes.helpers import validate_price_range
from app.constants.categories import validate_category, normalize_category
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

DEFAULT_RADIUS_KM = 25
MIN_RESULTS_DEFAULT = 5
RADIUS_EXPANSION_STEPS = [50, 100, 200, 500]


def get_current_user_id_optional():
    """Extract user_id from token if present, return None otherwise."""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None
    user_id, error, status = _resolve_user_from_token(auth_header)
    if error:
        return None
    return user_id


def get_pending_applications_counts(task_ids: list[int]) -> dict[int, int]:
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
        counts = {task_id: 0 for task_id in task_ids}
        for task_id, count in results:
            counts[task_id] = count
        return counts
    except Exception as e:
        logger.error(f"Error fetching application counts: {e}")
        return {task_id: 0 for task_id in task_ids}


def get_user_applied_task_ids(user_id: int | None, task_ids: list[int]) -> set[int]:
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
    if not lang or not tasks_list:
        return tasks_list
    try:
        from app.services.translation import is_translation_enabled
        if not is_translation_enabled():
            return tasks_list
    except:
        return tasks_list
    for task in tasks_list:
        task = translate_task_if_needed(task, lang)
    return tasks_list


def _premium_sort_key(task_dict):
    """Sort key for premium ordering: promoted first, then urgent, then regular.
    
    Returns a tuple (priority_tier, secondary) where:
    - priority_tier 0 = active promoted
    - priority_tier 1 = active urgent
    - priority_tier 2 = regular
    """
    if task_dict.get('is_promote_active'):
        return (0,)
    if task_dict.get('is_urgent_active'):
        return (1,)
    return (2,)


def _find_tasks_within_radius(base_query, latitude, longitude, radius_km):
    """Find tasks within a given radius from coordinates.
    
    Returns list of (task_id, task_dict) tuples sorted by:
    1. Promoted tasks first
    2. Urgent tasks second
    3. Then by distance
    """
    min_lat, max_lat, min_lng, max_lng = get_bounding_box(latitude, longitude, radius_km)
    query = base_query.filter(
        TaskRequest.latitude.isnot(None),
        TaskRequest.longitude.isnot(None),
        TaskRequest.latitude >= min_lat,
        TaskRequest.latitude <= max_lat,
        TaskRequest.longitude >= min_lng,
        TaskRequest.longitude <= max_lng
    )
    
    all_tasks = query.all()
    
    tasks_with_distance = []
    for task in all_tasks:
        dist = distance(latitude, longitude, task.latitude, task.longitude)
        if dist <= radius_km:
            task_dict = task.to_dict()
            task_dict['distance'] = round(dist, 2)
            tasks_with_distance.append((task.id, task_dict))
    
    # Sort: promoted first → urgent second → then by distance
    tasks_with_distance.sort(
        key=lambda x: (*_premium_sort_key(x[1]), x[1]['distance'])
    )
    return tasks_with_distance


@tasks_bp.route('', methods=['GET'])
def get_tasks():
    """Get task requests with filtering, geolocation, and optional translation.
    
    Query params:
        - lang: Language code (lv, en, ru) for auto-translation
        - latitude, longitude: User location
        - radius: Search radius in km (default 25)
        - min_results: Minimum results before auto-expanding radius (default 5).
        - status: Task status filter (default 'open')
        - category: Category filter. Supports comma-separated values.
        - page, per_page: Pagination
    
    Sorting order:
        1. Promoted tasks (paid) first
        2. Urgent tasks (paid) second
        3. Regular tasks by distance or date
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', 'open')
        category = request.args.get('category')
        latitude = request.args.get('latitude', type=float)
        longitude = request.args.get('longitude', type=float)
        radius = request.args.get('radius', DEFAULT_RADIUS_KM, type=float)
        min_results = request.args.get('min_results', MIN_RESULTS_DEFAULT, type=int)
        lang = request.args.get('lang')
        
        if request.args.get('radius') and (latitude is None or longitude is None):
            logger.warning(
                'GET /api/tasks: radius=%s provided without latitude/longitude — '
                'radius will be ignored, returning all tasks',
                request.args.get('radius')
            )
        
        current_user_id = get_current_user_id_optional()
        
        query = TaskRequest.query.options(
            joinedload(TaskRequest.creator),
            joinedload(TaskRequest.assigned_user)
        ).filter_by(status=status)
        
        if category:
            categories = [normalize_category(c.strip()) for c in category.split(',') if c.strip()]
            if len(categories) == 1:
                query = query.filter_by(category=categories[0])
            elif len(categories) > 1:
                query = query.filter(TaskRequest.category.in_(categories))
        
        if latitude is not None and longitude is not None:
            effective_radius = radius
            radius_expanded = False
            
            tasks_with_distance = _find_tasks_within_radius(query, latitude, longitude, radius)
            
            if min_results > 0 and len(tasks_with_distance) < min_results:
                for expanded_radius in RADIUS_EXPANSION_STEPS:
                    if expanded_radius <= radius:
                        continue
                    tasks_with_distance = _find_tasks_within_radius(
                        query, latitude, longitude, expanded_radius
                    )
                    effective_radius = expanded_radius
                    radius_expanded = True
                    if len(tasks_with_distance) >= min_results:
                        break
                
                if len(tasks_with_distance) < min_results:
                    all_geo_tasks = query.filter(
                        TaskRequest.latitude.isnot(None),
                        TaskRequest.longitude.isnot(None),
                    ).all()
                    
                    tasks_with_distance = []
                    for task in all_geo_tasks:
                        dist = distance(latitude, longitude, task.latitude, task.longitude)
                        task_dict = task.to_dict()
                        task_dict['distance'] = round(dist, 2)
                        tasks_with_distance.append((task.id, task_dict))
                    
                    tasks_with_distance.sort(
                        key=lambda x: (*_premium_sort_key(x[1]), x[1]['distance'])
                    )
                    
                    if tasks_with_distance:
                        effective_radius = tasks_with_distance[-1][1]['distance']
                    radius_expanded = True
                    
                    logger.info(
                        'Smart radius: expanded to ALL tasks (%d found) '
                        'for location (%.4f, %.4f), original radius was %skm',
                        len(tasks_with_distance), latitude, longitude, radius
                    )
            
            total = len(tasks_with_distance)
            start = (page - 1) * per_page
            end = start + per_page
            paginated = tasks_with_distance[start:end]
            
            task_ids = [t[0] for t in paginated]
            tasks_list = [t[1] for t in paginated]
            
            pending_counts = get_pending_applications_counts(task_ids)
            user_applied_ids = get_user_applied_task_ids(current_user_id, task_ids)
            
            for i, task_dict in enumerate(tasks_list):
                task_dict['pending_applications_count'] = pending_counts.get(task_ids[i], 0)
                task_dict['has_applied'] = task_ids[i] in user_applied_ids
            
            tasks_list = batch_translate_tasks(tasks_list, lang)
            
            return jsonify({
                'tasks': tasks_list,
                'total': total,
                'page': page,
                'per_page': per_page,
                'has_more': end < total,
                'effective_radius': round(effective_radius, 1),
                'radius_expanded': radius_expanded,
            }), 200
        else:
            # No location: sort promoted → urgent → newest
            now = datetime.utcnow()
            tasks = query.order_by(
                case(
                    (db.and_(TaskRequest.is_promoted == True, TaskRequest.promoted_expires_at > now), 0),
                    (db.and_(TaskRequest.is_urgent == True, TaskRequest.urgent_expires_at > now), 1),
                    (db.and_(TaskRequest.is_urgent == True, TaskRequest.urgent_expires_at.is_(None)), 1),
                    else_=2
                ),
                TaskRequest.created_at.desc()
            ).paginate(page=page, per_page=per_page)
            
            task_ids = []
            tasks_list = []
            for task in tasks.items:
                task_ids.append(task.id)
                tasks_list.append(task.to_dict())
            
            pending_counts = get_pending_applications_counts(task_ids)
            user_applied_ids = get_user_applied_task_ids(current_user_id, task_ids)
            
            for i, task_dict in enumerate(tasks_list):
                task_dict['pending_applications_count'] = pending_counts.get(task_ids[i], 0)
                task_dict['has_applied'] = task_ids[i] in user_applied_ids
            
            tasks_list = batch_translate_tasks(tasks_list, lang)
            
            return jsonify({
                'tasks': tasks_list,
                'total': tasks.total,
                'page': page,
                'per_page': per_page,
                'has_more': tasks.has_next,
                'effective_radius': None,
                'radius_expanded': False,
            }), 200
            
    except Exception as e:
        logger.error(f"Error in get_tasks: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """Get a specific task request by ID."""
    try:
        lang = request.args.get('lang')
        
        task = TaskRequest.query.options(
            joinedload(TaskRequest.creator),
            joinedload(TaskRequest.assigned_user)
        ).get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        task_dict = task.to_dict()
        
        pending_counts = get_pending_applications_counts([task_id])
        task_dict['pending_applications_count'] = pending_counts.get(task_id, 0)
        
        task_dict = translate_task_if_needed(task_dict, lang)
        
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
@token_required
def create_task(current_user_id):
    """Create a new task request."""
    try:
        data = request.get_json()
        
        logger.info(f'Creating task for user {current_user_id} with data: {data}')
        
        if data.get('creator_id') and data['creator_id'] != current_user_id:
            logger.warning(
                f'create_task: body creator_id={data["creator_id"]} differs from '
                f'JWT user_id={current_user_id} — using JWT user_id'
            )
        
        required_fields = ['title', 'description', 'category', 'latitude', 'longitude', 'location']
        if not all(k in data for k in required_fields):
            missing = [k for k in required_fields if k not in data]
            return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
        
        category, cat_error = validate_category(data['category'])
        if cat_error:
            return jsonify({'error': cat_error}), 400
        
        budget = data.get('budget')
        if budget is not None:
            error_response = validate_price_range(budget, 'Budget')
            if error_response:
                return error_response
        
        deadline = None
        if data.get('deadline'):
            try:
                deadline = datetime.fromisoformat(data['deadline'])
            except ValueError:
                return jsonify({'error': 'Invalid deadline format. Use ISO format (YYYY-MM-DDTHH:MM)'}), 400
        
        difficulty = data.get('difficulty', 'medium')
        if difficulty not in ['easy', 'medium', 'hard']:
            return jsonify({'error': 'Invalid difficulty. Must be easy, medium, or hard'}), 400
        
        task = TaskRequest(
            title=data['title'],
            description=data['description'],
            category=category,
            location=data['location'],
            latitude=data['latitude'],
            longitude=data['longitude'],
            creator_id=current_user_id,
            budget=data.get('budget'),
            difficulty=difficulty,
            deadline=deadline,
            priority=data.get('priority', 'normal'),
            is_urgent=data.get('is_urgent', False),
            images=data.get('images')
        )
        
        db.session.add(task)
        db.session.commit()
        
        logger.info(f'Task created successfully: {task.id}, category: {task.category}, difficulty: {task.difficulty}, images: {task.images}')
        
        try:
            from app.services.job_alerts import send_job_alerts_for_task
            alerts_sent = send_job_alerts_for_task(task)
            if alerts_sent > 0:
                logger.info(f'Sent {alerts_sent} job alert(s) for new task {task.id}')
        except Exception as alert_err:
            logger.error(f'Job alerts failed for task {task.id}: {alert_err}', exc_info=True)
        
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
    """Update an existing task request."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        if task.creator_id != current_user_id:
            return jsonify({'error': 'Only the task creator can edit this task'}), 403
        
        if task.status != 'open':
            return jsonify({'error': 'Only open tasks can be edited'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        logger.info(f'Updating task {task_id} for user {current_user_id} with data: {data}')
        
        if 'budget' in data and data['budget'] is not None:
            error_response = validate_price_range(data['budget'], 'Budget')
            if error_response:
                return error_response
        
        if 'title' in data and data['title'].strip():
            task.title = data['title'].strip()
        if 'description' in data and data['description'].strip():
            task.description = data['description'].strip()
        if 'category' in data:
            category, cat_error = validate_category(data['category'])
            if cat_error:
                return jsonify({'error': cat_error}), 400
            task.category = category
        if 'location' in data and data['location'].strip():
            task.location = data['location'].strip()
        if 'latitude' in data:
            task.latitude = data['latitude']
        if 'longitude' in data:
            task.longitude = data['longitude']
        if 'budget' in data:
            task.budget = data['budget']
        if 'deadline' in data:
            if data['deadline']:
                try:
                    task.deadline = datetime.fromisoformat(data['deadline'])
                except ValueError:
                    return jsonify({'error': 'Invalid deadline format. Use ISO format (YYYY-MM-DDTHH:MM)'}), 400
            else:
                task.deadline = None
        if 'difficulty' in data:
            if data['difficulty'] not in ['easy', 'medium', 'hard']:
                return jsonify({'error': 'Invalid difficulty. Must be easy, medium, or hard'}), 400
            task.difficulty = data['difficulty']
        if 'images' in data:
            task.images = data['images']
        
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f'Task {task_id} updated successfully')
        
        return jsonify({
            'message': 'Task updated successfully',
            'task': task.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error updating task {task_id}: {str(e)}', exc_info=True)
        return jsonify({'error': str(e)}), 500
