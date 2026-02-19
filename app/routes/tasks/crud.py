"""Task CRUD and listing routes.

Provides endpoints for creating, reading, updating and deleting tasks,
including geo-search with smart radius expansion.
"""

import logging
from datetime import datetime
from flask import request, jsonify, current_app
from sqlalchemy import func, or_

from app import db
from app.models import TaskRequest, TaskApplication, User, Notification, NotificationType, Review
from app.utils.auth import token_required
from app.routes.tasks.helpers import distance, get_bounding_box
from app.constants.categories import validate_category

logger = logging.getLogger(__name__)

# Use the shared blueprint from tasks/__init__.py
from app.routes.tasks import tasks_bp


def validate_price_range(budget, label='Budget'):
    """Return an error Response if budget is out of range, else None."""
    try:
        budget = float(budget)
    except (TypeError, ValueError):
        return jsonify({'error': f'{label} must be a number'}), 400
    if budget < 0 or budget > 100_000:
        return jsonify({'error': f'{label} must be between 0 and 100 000'}), 400
    return None


# ---------------------------------------------------------------------------
# Geo helpers
# ---------------------------------------------------------------------------

DEFAULT_RADIUS_KM = 25
MIN_RESULTS_DEFAULT = 5
RADIUS_EXPANSION_STEPS = [50, 100, 200]


def _find_tasks_within_radius(base_query, latitude, longitude, radius_km):
    """Find tasks within a given radius from coordinates.

    Returns list of (task_id, task_dict) tuples sorted by distance.
    Uses bounding box pre-filter + Haversine exact distance.
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

    tasks_with_distance.sort(key=lambda x: x[1]['distance'])
    return tasks_with_distance


# ---------------------------------------------------------------------------
# LIST / SEARCH
# ---------------------------------------------------------------------------

@tasks_bp.route('', methods=['GET'])
def get_tasks():
    """List tasks with optional filters.

    Query params:
        - page, per_page: Pagination
        - status: Filter by status (default: open)
        - category: Filter by category
        - lang: Language code (lv, en, ru) for auto-translation
        - latitude, longitude: User location
        - radius: Search radius in km (default 25)
        - min_results: Minimum results before auto-expanding radius (default 5).
                       If initial radius returns fewer than this, backend expands
                       the radius automatically in steps until enough are found.
                       Set to 0 to disable auto-expansion.
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

        # Defensive: warn if radius was explicitly sent without coordinates
        if request.args.get('radius') and (latitude is None or longitude is None):
            logger.warning(
                'GET /api/tasks: radius=%s provided without latitude/longitude — '
                'radius will be ignored, returning all tasks',
                request.args.get('radius')
            )

        # Get current user ID if authenticated (for has_applied check)
        current_user_id = None
        try:
            import jwt as pyjwt
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                secret_key = current_app.config['JWT_SECRET_KEY']
                payload = pyjwt.decode(token, secret_key, algorithms=['HS256'])
                current_user_id = payload.get('user_id')
        except Exception:
            pass

        # Base query
        query = TaskRequest.query.filter_by(status=status)
        if category:
            query = query.filter_by(category=category)
        query = query.order_by(TaskRequest.created_at.desc())

        # If location filtering is requested
        if latitude is not None and longitude is not None:
            effective_radius = radius
            radius_expanded = False

            # Initial search at requested radius
            tasks_with_distance = _find_tasks_within_radius(query, latitude, longitude, radius)

            # Smart radius expansion: if too few results, expand step by step
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
                else:
                    # Even 200km wasn't enough — return all geo tasks sorted by distance
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

                    tasks_with_distance.sort(key=lambda x: x[1]['distance'])
                    effective_radius = None
                    radius_expanded = True

            if radius_expanded:
                if effective_radius:
                    logger.info(
                        'Auto-expanded radius to %skm: found %d tasks '
                        'for location (%.4f, %.4f), original radius was %skm',
                        effective_radius, len(tasks_with_distance),
                        latitude, longitude, radius
                    )
                else:
                    logger.info(
                        'Returned ALL %d geo-tasks (no radius limit) '
                        'for location (%.4f, %.4f), original radius was %skm',
                        len(tasks_with_distance), latitude, longitude, radius
                    )

            # Pagination
            total = len(tasks_with_distance)
            start = (page - 1) * per_page
            page_tasks = tasks_with_distance[start:start + per_page]

            # has_applied check
            if current_user_id:
                task_ids = [tid for tid, _ in page_tasks]
                if task_ids:
                    applied_ids = {a.task_id for a in TaskApplication.query.filter(
                        TaskApplication.task_id.in_(task_ids),
                        TaskApplication.applicant_id == current_user_id
                    ).all()}
                else:
                    applied_ids = set()

                for tid, td in page_tasks:
                    td['has_applied'] = tid in applied_ids

            tasks_data = [td for _, td in page_tasks]

            return jsonify({
                'tasks': tasks_data,
                'total': total,
                'page': page,
                'per_page': per_page,
                'radius': effective_radius,
                'radius_expanded': radius_expanded,
            }), 200

        else:
            # No location — standard pagination
            total = query.count()
            tasks = query.offset((page - 1) * per_page).limit(per_page).all()

            if current_user_id:
                task_ids = [t.id for t in tasks]
                if task_ids:
                    applied_ids = {a.task_id for a in TaskApplication.query.filter(
                        TaskApplication.task_id.in_(task_ids),
                        TaskApplication.applicant_id == current_user_id
                    ).all()}
                else:
                    applied_ids = set()
            else:
                applied_ids = set()

            tasks_data = []
            for task in tasks:
                td = task.to_dict()
                td['has_applied'] = task.id in applied_ids
                tasks_data.append(td)

            return jsonify({
                'tasks': tasks_data,
                'total': total,
                'page': page,
                'per_page': per_page,
            }), 200

    except Exception as e:
        raise


@tasks_bp.route('/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """Get a specific task by ID, including creator info and review stats."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        task_data = task.to_dict()

        # Attach creator info
        creator = User.query.get(task.creator_id)
        if creator:
            avg_rating = creator.rating or 0
            review_count = creator.review_count

            task_data['creator'] = {
                'id': creator.id,
                'username': creator.username,
                'first_name': creator.first_name,
                'last_name': creator.last_name,
                'avatar_url': creator.avatar_url,
                'profile_picture_url': creator.profile_picture_url,
                'rating': round(avg_rating, 1),
                'review_count': review_count,
            }

        return jsonify(task_data), 200
    except Exception as e:
        raise


# ---------------------------------------------------------------------------
# CREATE / UPDATE / DELETE
# ---------------------------------------------------------------------------

@tasks_bp.route('', methods=['POST'])
@token_required
def create_task(current_user_id):
    """Create a new task request.

    Requires authentication. The creator_id is extracted from the JWT
    token — any creator_id sent in the request body is ignored.

    After creation, sends job alert notifications to nearby users
    who have matching preferences (category + radius).
    """
    try:
        data = request.get_json()

        logger.info(f'Creating task for user {current_user_id} with data: {data}')

        # creator_id comes from JWT token, not from request body
        if data.get('creator_id') and data['creator_id'] != current_user_id:
            logger.warning(
                f'create_task: body creator_id={data["creator_id"]} differs from '
                f'JWT user_id={current_user_id} — using JWT user_id'
            )

        required_fields = ['title', 'description', 'category', 'latitude', 'longitude', 'location']
        if not all(k in data for k in required_fields):
            missing = [k for k in required_fields if k not in data]
            return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

        # Validate text field lengths
        if len(data['title']) > 200:
            return jsonify({'error': 'Title must be less than 200 characters'}), 400

        if len(data['description']) > 5000:
            return jsonify({'error': 'Description must be less than 5000 characters'}), 400

        if len(data['location']) > 200:
            return jsonify({'error': 'Location must be less than 200 characters'}), 400

        # Validate latitude/longitude ranges
        try:
            lat = float(data['latitude'])
            lng = float(data['longitude'])
            if lat < -90 or lat > 90:
                return jsonify({'error': 'Latitude must be between -90 and 90'}), 400
            if lng < -180 or lng > 180:
                return jsonify({'error': 'Longitude must be between -180 and 180'}), 400
        except (TypeError, ValueError):
            return jsonify({'error': 'Latitude and longitude must be numbers'}), 400

        # Validate & normalize category (converts legacy keys automatically)
        category, cat_error = validate_category(data['category'])
        if cat_error:
            return jsonify({'error': cat_error}), 400

        # Validate budget range
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

        # Validate difficulty
        difficulty = data.get('difficulty', 'medium')
        if difficulty not in ['easy', 'medium', 'hard']:
            return jsonify({'error': 'Invalid difficulty. Must be easy, medium, or hard'}), 400

        # Create task — creator_id from JWT, not request body
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
            images=','.join(data['images']) if data.get('images') else None,
        )

        db.session.add(task)
        db.session.commit()

        # ----------------------------------------------------------------
        # Job Alert Notifications — notify nearby users with matching prefs
        # ----------------------------------------------------------------
        try:
            from app.models import JobAlertPreference

            # Query all alert preferences that match this task's category
            matching_prefs = JobAlertPreference.query.filter(
                JobAlertPreference.user_id != current_user_id,  # Don't notify creator
                JobAlertPreference.is_active == True,
            ).all()

            notified_count = 0
            for pref in matching_prefs:
                # Check category match (if pref has categories set)
                if pref.categories:
                    pref_categories = [c.strip() for c in pref.categories.split(',')]
                    if category not in pref_categories:
                        continue

                # Check distance (if pref has location + radius)
                if pref.latitude and pref.longitude and pref.radius_km:
                    dist = distance(pref.latitude, pref.longitude, task.latitude, task.longitude)
                    if dist > pref.radius_km:
                        continue

                # Send notification
                notification = Notification(
                    user_id=pref.user_id,
                    type=NotificationType.JOB_ALERT,
                    title=f'New job nearby: {task.title}',
                    message=f'{task.title} in {task.location}' + (f' — €{task.budget}' if task.budget else ''),
                    related_type='task',
                    related_id=task.id,
                )
                db.session.add(notification)
                notified_count += 1

            if notified_count > 0:
                db.session.commit()
                logger.info(f'Job alerts sent to {notified_count} users for task {task.id}')

        except ImportError:
            logger.debug('JobAlertPreference not available — skipping job alerts')
        except Exception as alert_err:
            logger.warning(f'Job alert notifications failed (non-fatal): {alert_err}')
            # Don't rollback the task creation

        return jsonify(task.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        raise


@tasks_bp.route('/<int:task_id>', methods=['PUT'])
@token_required
def update_task(current_user_id, task_id):
    """Update an existing task request.

    Requires authentication. Only the task creator can edit.
    Only open tasks can be edited.
    """
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        if task.creator_id != current_user_id:
            return jsonify({'error': 'Only the task creator can edit this task'}), 403

        if task.status != 'open':
            return jsonify({'error': 'Only open tasks can be edited'}), 400

        data = request.get_json()

        if 'title' in data:
            if len(data['title']) > 200:
                return jsonify({'error': 'Title must be less than 200 characters'}), 400
            task.title = data['title']

        if 'description' in data:
            if len(data['description']) > 5000:
                return jsonify({'error': 'Description must be less than 5000 characters'}), 400
            task.description = data['description']

        if 'location' in data:
            if len(data['location']) > 200:
                return jsonify({'error': 'Location must be less than 200 characters'}), 400
            task.location = data['location']

        if 'category' in data:
            cat, cat_error = validate_category(data['category'])
            if cat_error:
                return jsonify({'error': cat_error}), 400
            task.category = cat

        if 'latitude' in data:
            try:
                lat = float(data['latitude'])
                if lat < -90 or lat > 90:
                    return jsonify({'error': 'Latitude must be between -90 and 90'}), 400
                task.latitude = lat
            except (TypeError, ValueError):
                return jsonify({'error': 'Latitude must be a number'}), 400

        if 'longitude' in data:
            try:
                lng = float(data['longitude'])
                if lng < -180 or lng > 180:
                    return jsonify({'error': 'Longitude must be between -180 and 180'}), 400
                task.longitude = lng
            except (TypeError, ValueError):
                return jsonify({'error': 'Longitude must be a number'}), 400

        if 'budget' in data:
            task.budget = data['budget']

        if 'deadline' in data:
            if data['deadline']:
                try:
                    task.deadline = datetime.fromisoformat(data['deadline'])
                except ValueError:
                    return jsonify({'error': 'Invalid deadline format'}), 400
            else:
                task.deadline = None

        if 'difficulty' in data:
            if data['difficulty'] not in ['easy', 'medium', 'hard']:
                return jsonify({'error': 'Invalid difficulty'}), 400
            task.difficulty = data['difficulty']

        if 'priority' in data:
            task.priority = data['priority']

        if 'is_urgent' in data:
            task.is_urgent = data['is_urgent']

        if 'images' in data:
            if isinstance(data['images'], list):
                task.images = ','.join(data['images'])
            else:
                task.images = data['images']

        task.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify(task.to_dict()), 200

    except Exception as e:
        db.session.rollback()
        raise
