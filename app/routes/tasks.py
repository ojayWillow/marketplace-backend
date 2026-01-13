"""Task request routes for quick help services marketplace."""

from flask import Blueprint, request, jsonify
from app import db
from app.models import TaskRequest, User, TaskApplication
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


def translate_task_if_needed(task_dict: dict, lang: str | None) -> dict:
    """Translate task title and description if language is specified."""
    if not lang:
        return task_dict
    
    try:
        from app.services.translation import translate_task
        return translate_task(task_dict, lang)
    except Exception as e:
        # If translation fails, return original
        print(f"Translation error: {e}")
        return task_dict


def safe_create_notification(notify_func, *args, **kwargs):
    """
    Safely call a notification function, handling errors gracefully.
    If notification fails (e.g., table doesn't exist), rollback and continue.
    """
    try:
        notify_func(*args, **kwargs)
        db.session.commit()
    except Exception as e:
        # Rollback to clean the session state after failed notification
        db.session.rollback()
        print(f"Notification skipped (non-critical): {e}")


def get_pending_applications_count(task_id: int) -> int:
    """Get count of pending applications for a task."""
    try:
        return TaskApplication.query.filter_by(
            task_id=task_id,
            status='pending'
        ).count()
    except Exception:
        return 0


@tasks_bp.route('/notifications', methods=['GET'])
@token_required
def get_task_notifications(current_user_id):
    """Get notification counts for the current user (pending applications on their tasks)."""
    try:
        # Count pending applications on tasks created by current user
        pending_applications_count = db.session.query(TaskApplication).join(
            TaskRequest, TaskApplication.task_id == TaskRequest.id
        ).filter(
            TaskRequest.creator_id == current_user_id,
            TaskRequest.status == 'open',
            TaskApplication.status == 'pending'
        ).count()
        
        # Count tasks awaiting confirmation (worker marked done, creator needs to confirm)
        pending_confirmation_count = TaskRequest.query.filter(
            TaskRequest.creator_id == current_user_id,
            TaskRequest.status == 'pending_confirmation'
        ).count()
        
        # Count accepted applications for tasks user applied to (good news!)
        accepted_applications_count = TaskApplication.query.filter(
            TaskApplication.applicant_id == current_user_id,
            TaskApplication.status == 'accepted'
        ).count()
        
        return jsonify({
            'pending_applications': pending_applications_count,
            'pending_confirmation': pending_confirmation_count,
            'accepted_applications': accepted_applications_count,
            'total': pending_applications_count + pending_confirmation_count
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/my', methods=['GET'])
@token_required
def get_my_tasks(current_user_id):
    """Get tasks assigned to the current user (as worker), including completed ones."""
    try:
        lang = request.args.get('lang')
        
        my_tasks = TaskRequest.query.filter(
            TaskRequest.assigned_to_id == current_user_id,
            TaskRequest.status.in_(['assigned', 'accepted', 'in_progress', 'pending_confirmation', 'completed'])
        ).order_by(TaskRequest.created_at.desc()).all()
        
        tasks_list = [translate_task_if_needed(task.to_dict(), lang) for task in my_tasks]
        
        return jsonify({
            'tasks': tasks_list,
            'total': len(my_tasks)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/created', methods=['GET'])
@token_required
def get_created_tasks(current_user_id):
    """Get tasks created by the current user (as client), with pending applications count."""
    try:
        lang = request.args.get('lang')
        
        created_tasks = TaskRequest.query.filter(
            TaskRequest.creator_id == current_user_id
        ).order_by(TaskRequest.created_at.desc()).all()
        
        results = []
        for task in created_tasks:
            task_dict = translate_task_if_needed(task.to_dict(), lang)
            # Count pending applications for each task
            pending_count = TaskApplication.query.filter_by(
                task_id=task.id,
                status='pending'
            ).count()
            task_dict['pending_applications_count'] = pending_count
            results.append(task_dict)
        
        return jsonify({
            'tasks': results,
            'total': len(results)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('', methods=['GET'])
def get_tasks():
    """Get task requests with filtering, geolocation, and optional translation.
    
    Query params:
        - lang: Language code (lv, en, ru) for auto-translation
        - latitude, longitude: User location
        - radius: Search radius in km (default 10)
        - status: Task status filter (default 'open')
        - category: Category filter
        - page, per_page: Pagination
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', 'open')
        category = request.args.get('category')
        latitude = request.args.get('latitude', type=float)
        longitude = request.args.get('longitude', type=float)
        radius = request.args.get('radius', 10, type=float)
        lang = request.args.get('lang')  # Language for translation
        
        # Build base query
        query = TaskRequest.query.filter_by(status=status)
        
        if category:
            query = query.filter_by(category=category)
        
        # If location filtering is requested, we need to:
        # 1. Get ALL matching tasks first
        # 2. Filter by distance
        # 3. Sort by distance
        # 4. Then apply pagination manually
        if latitude is not None and longitude is not None:
            # Get all tasks matching status/category (no pagination yet)
            all_tasks = query.all()
            
            # Filter by distance and calculate distance for each
            tasks_with_distance = []
            for task in all_tasks:
                # Skip tasks without valid coordinates
                if task.latitude is None or task.longitude is None:
                    continue
                    
                dist = distance(latitude, longitude, task.latitude, task.longitude)
                if dist <= radius:
                    task_dict = task.to_dict()
                    task_dict['distance'] = round(dist, 2)
                    # Add pending applications count for each task
                    task_dict['pending_applications_count'] = get_pending_applications_count(task.id)
                    # Translate if language specified
                    task_dict = translate_task_if_needed(task_dict, lang)
                    tasks_with_distance.append(task_dict)
            
            # Sort by distance (closest first)
            tasks_with_distance.sort(key=lambda x: x['distance'])
            
            # Calculate pagination manually
            total = len(tasks_with_distance)
            start = (page - 1) * per_page
            end = start + per_page
            paginated_results = tasks_with_distance[start:end]
            
            return jsonify({
                'tasks': paginated_results,
                'total': total,
                'page': page,
                'per_page': per_page,
                'has_more': end < total
            }), 200
        else:
            # No location filtering - use normal pagination
            tasks = query.order_by(TaskRequest.created_at.desc()).paginate(page=page, per_page=per_page)
            
            tasks_list = []
            for task in tasks.items:
                task_dict = translate_task_if_needed(task.to_dict(), lang)
                # Add pending applications count for each task
                task_dict['pending_applications_count'] = get_pending_applications_count(task.id)
                tasks_list.append(task_dict)
            
            return jsonify({
                'tasks': tasks_list,
                'total': tasks.total,
                'page': page,
                'per_page': per_page,
                'has_more': tasks.has_next
            }), 200
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """Get a specific task request by ID."""
    try:
        lang = request.args.get('lang')
        
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        task_dict = translate_task_if_needed(task.to_dict(), lang)
        # Add pending applications count
        task_dict['pending_applications_count'] = get_pending_applications_count(task.id)
        return jsonify(task_dict), 200
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


@tasks_bp.route('/<int:task_id>/applications/<int:application_id>', methods=['DELETE'])
@token_required
def withdraw_application(current_user_id, task_id, application_id):
    """Withdraw/delete an application (only the applicant can do this, only if pending)."""
    try:
        application = TaskApplication.query.get(application_id)
        if not application or application.task_id != task_id:
            return jsonify({'error': 'Application not found'}), 404
        
        # Only the applicant can withdraw
        if application.applicant_id != current_user_id:
            return jsonify({'error': 'Only the applicant can withdraw this application'}), 403
        
        # Can only withdraw pending applications
        if application.status != 'pending':
            return jsonify({'error': 'Only pending applications can be withdrawn'}), 400
        
        db.session.delete(application)
        db.session.commit()
        
        return jsonify({
            'message': 'Application withdrawn successfully'
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============ APPLICATION SYSTEM ENDPOINTS ============

@tasks_bp.route('/<int:task_id>/apply', methods=['POST'])
@token_required
def apply_to_task(current_user_id, task_id):
    """Apply to a task (worker submits application)."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        if task.status != 'open':
            return jsonify({'error': 'Task is no longer accepting applications'}), 400
        
        # Can't apply to your own task
        if task.creator_id == current_user_id:
            return jsonify({'error': 'You cannot apply to your own task'}), 400
        
        # Check if already applied
        existing_application = TaskApplication.query.filter_by(
            task_id=task_id,
            applicant_id=current_user_id
        ).first()
        
        if existing_application:
            return jsonify({'error': 'You have already applied to this task'}), 400
        
        data = request.get_json() or {}
        message = data.get('message', '')
        
        application = TaskApplication(
            task_id=task_id,
            applicant_id=current_user_id,
            message=message,
            status='pending'
        )
        
        db.session.add(application)
        db.session.commit()
        
        # Store values needed for notification before any potential rollback
        creator_id = task.creator_id
        task_title = task.title
        
        # Try to create notification for task creator (non-blocking)
        try:
            from app.routes.notifications import notify_new_application
            applicant = User.query.get(current_user_id)
            applicant_name = applicant.name if applicant else 'Someone'
            notify_new_application(creator_id, applicant_name, task_title, task_id)
            db.session.commit()
        except Exception as notify_error:
            db.session.rollback()
            print(f"Notification skipped (non-critical): {notify_error}")
        
        return jsonify({
            'message': 'Application submitted successfully',
            'application': application.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/<int:task_id>/applications', methods=['GET'])
@token_required
def get_task_applications(current_user_id, task_id):
    """Get all applications for a task (only task creator can view)."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Only the creator can view applications
        if task.creator_id != current_user_id:
            return jsonify({'error': 'Only the task creator can view applications'}), 403
        
        applications = TaskApplication.query.filter_by(task_id=task_id).order_by(TaskApplication.created_at.desc()).all()
        
        return jsonify({
            'applications': [app.to_dict() for app in applications],
            'total': len(applications)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/<int:task_id>/applications/<int:application_id>/accept', methods=['POST'])
@token_required
def accept_application(current_user_id, task_id, application_id):
    """Accept an application and assign task to applicant."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Only the creator can accept applications
        if task.creator_id != current_user_id:
            return jsonify({'error': 'Only the task creator can accept applications'}), 403
        
        if task.status != 'open':
            return jsonify({'error': 'Task is no longer accepting applications'}), 400
        
        application = TaskApplication.query.get(application_id)
        if not application or application.task_id != task_id:
            return jsonify({'error': 'Application not found'}), 404
        
        if application.status != 'pending':
            return jsonify({'error': 'Application has already been processed'}), 400
        
        # Accept the application
        application.status = 'accepted'
        
        # Assign task to applicant
        task.assigned_to_id = application.applicant_id
        task.status = 'assigned'
        task.updated_at = datetime.utcnow()
        
        # Reject all other pending applications for this task
        other_applications = TaskApplication.query.filter(
            TaskApplication.task_id == task_id,
            TaskApplication.id != application_id,
            TaskApplication.status == 'pending'
        ).all()
        
        # Store IDs of rejected applicants for notifications
        rejected_applicant_ids = [other_app.applicant_id for other_app in other_applications]
        
        for other_app in other_applications:
            other_app.status = 'rejected'
        
        # IMPORTANT: Commit the main operation FIRST
        db.session.commit()
        
        # Store values needed for response and notifications
        task_dict = task.to_dict()
        application_dict = application.to_dict()
        accepted_applicant_id = application.applicant_id
        task_title = task.title
        
        # Try to create notifications (non-blocking, after main commit)
        try:
            from app.routes.notifications import notify_application_accepted, notify_application_rejected
            notify_application_accepted(accepted_applicant_id, task_title, task_id)
            db.session.commit()
        except Exception as notify_error:
            db.session.rollback()
            print(f"Accepted notification skipped (non-critical): {notify_error}")
        
        # Notify rejected applicants separately
        for rejected_id in rejected_applicant_ids:
            try:
                from app.routes.notifications import notify_application_rejected
                notify_application_rejected(rejected_id, task_title, task_id)
                db.session.commit()
            except Exception as notify_error:
                db.session.rollback()
                print(f"Rejected notification skipped (non-critical): {notify_error}")
        
        return jsonify({
            'message': 'Application accepted and task assigned',
            'task': task_dict,
            'application': application_dict
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/<int:task_id>/applications/<int:application_id>/reject', methods=['POST'])
@token_required
def reject_application(current_user_id, task_id, application_id):
    """Reject an application."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Only the creator can reject applications
        if task.creator_id != current_user_id:
            return jsonify({'error': 'Only the task creator can reject applications'}), 403
        
        application = TaskApplication.query.get(application_id)
        if not application or application.task_id != task_id:
            return jsonify({'error': 'Application not found'}), 404
        
        if application.status != 'pending':
            return jsonify({'error': 'Application has already been processed'}), 400
        
        application.status = 'rejected'
        db.session.commit()
        
        # Store values for notification
        applicant_id = application.applicant_id
        task_title = task.title
        application_dict = application.to_dict()
        
        # Try to notify the rejected applicant (non-blocking)
        try:
            from app.routes.notifications import notify_application_rejected
            notify_application_rejected(applicant_id, task_title, task_id)
            db.session.commit()
        except Exception as notify_error:
            db.session.rollback()
            print(f"Notification skipped (non-critical): {notify_error}")
        
        return jsonify({
            'message': 'Application rejected',
            'application': application_dict
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/my-applications', methods=['GET'])
@token_required
def get_my_applications(current_user_id):
    """Get all applications submitted by current user."""
    try:
        lang = request.args.get('lang')
        
        applications = TaskApplication.query.filter_by(
            applicant_id=current_user_id
        ).order_by(TaskApplication.created_at.desc()).all()
        
        results = []
        for app in applications:
            app_dict = app.to_dict()
            # Include task info
            if app.task:
                app_dict['task'] = translate_task_if_needed(app.task.to_dict(), lang)
            results.append(app_dict)
        
        return jsonify({
            'applications': results,
            'total': len(results)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ END APPLICATION SYSTEM ENDPOINTS ============


@tasks_bp.route('/<int:task_id>/accept', methods=['POST'])
def accept_task(task_id):
    """DEPRECATED: Old direct accept endpoint - kept for backward compatibility."""
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
        
        # Store values for notification and response
        task_dict = task.to_dict()
        creator_id = task.creator_id
        task_title = task.title
        
        # Try to notify task creator (non-blocking)
        try:
            from app.routes.notifications import notify_task_marked_done
            worker = User.query.get(current_user_id)
            worker_name = worker.name if worker else 'Worker'
            notify_task_marked_done(creator_id, worker_name, task_title, task_id)
            db.session.commit()
        except Exception as notify_error:
            db.session.rollback()
            print(f"Notification skipped (non-critical): {notify_error}")
        
        return jsonify({
            'message': 'Task marked as done. Waiting for creator confirmation.',
            'task': task_dict
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
        
        # Store values for notification and response
        task_dict = task.to_dict()
        worker_id = task.assigned_to_id
        task_title = task.title
        
        # Try to notify the worker (non-blocking)
        try:
            from app.routes.notifications import notify_task_completed
            notify_task_completed(worker_id, task_title, task_id)
            db.session.commit()
        except Exception as notify_error:
            db.session.rollback()
            print(f"Notification skipped (non-critical): {notify_error}")
        
        return jsonify({
            'message': 'Task completed! Both parties can now leave reviews.',
            'task': task_dict
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
