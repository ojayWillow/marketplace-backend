"""User-specific task query routes (my tasks, created tasks, notifications)."""

from flask import request, jsonify
from sqlalchemy.orm import joinedload
from app import db
from app.models import TaskRequest, User, TaskApplication
from app.utils import token_required
from app.routes.tasks import tasks_bp
from app.routes.tasks.helpers import translate_task_if_needed


@tasks_bp.route('/notifications', methods=['GET'])
@token_required
def get_task_notifications(current_user_id):
    """Get notification counts for the current user (pending applications on their tasks)."""
    try:
        pending_applications_count = db.session.query(TaskApplication).join(
            TaskRequest, TaskApplication.task_id == TaskRequest.id
        ).filter(
            TaskRequest.creator_id == current_user_id,
            TaskRequest.status == 'open',
            TaskApplication.status == 'pending'
        ).count()
        
        pending_confirmation_count = TaskRequest.query.filter(
            TaskRequest.creator_id == current_user_id,
            TaskRequest.status == 'pending_confirmation'
        ).count()
        
        accepted_applications_count = TaskApplication.query.filter(
            TaskApplication.applicant_id == current_user_id,
            TaskApplication.status == 'accepted'
        ).count()
        
        # Count disputed tasks (for both creator and worker)
        disputed_count = TaskRequest.query.filter(
            db.or_(
                TaskRequest.creator_id == current_user_id,
                TaskRequest.assigned_to_id == current_user_id
            ),
            TaskRequest.status == 'disputed'
        ).count()
        
        return jsonify({
            'pending_applications': pending_applications_count,
            'pending_confirmation': pending_confirmation_count,
            'accepted_applications': accepted_applications_count,
            'disputed': disputed_count,
            'total': pending_applications_count + pending_confirmation_count + disputed_count
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/my', methods=['GET'])
@token_required
def get_my_tasks(current_user_id):
    """Get tasks assigned to the current user (as worker), including completed and disputed ones."""
    try:
        lang = request.args.get('lang')
        
        # Include all statuses where the worker is involved:
        # - assigned: accepted but not started
        # - accepted: legacy status (same as assigned)
        # - in_progress: worker is working on it
        # - pending_confirmation: worker marked done, waiting for creator
        # - completed: task is done
        # - disputed: task has an active dispute
        my_tasks = TaskRequest.query.options(
            joinedload(TaskRequest.creator),
            joinedload(TaskRequest.assigned_user)
        ).filter(
            TaskRequest.assigned_to_id == current_user_id,
            TaskRequest.status.in_(['assigned', 'accepted', 'in_progress', 'pending_confirmation', 'completed', 'disputed'])
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
        
        created_tasks = TaskRequest.query.options(
            joinedload(TaskRequest.creator),
            joinedload(TaskRequest.assigned_user)
        ).filter(
            TaskRequest.creator_id == current_user_id
        ).order_by(TaskRequest.created_at.desc()).all()
        
        results = []
        for task in created_tasks:
            task_dict = translate_task_if_needed(task.to_dict(), lang)
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


@tasks_bp.route('/user/<int:user_id>', methods=['GET'])
def get_user_tasks(user_id):
    """Get open tasks by a specific user (public endpoint for profile view)."""
    try:
        lang = request.args.get('lang')
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        tasks = TaskRequest.query.options(
            joinedload(TaskRequest.creator),
            joinedload(TaskRequest.assigned_user)
        ).filter_by(
            creator_id=user_id,
            status='open'
        ).order_by(TaskRequest.created_at.desc()).all()
        
        tasks_list = [translate_task_if_needed(task.to_dict(), lang) for task in tasks]
        
        return jsonify({
            'tasks': tasks_list,
            'total': len(tasks),
            'page': 1
        }), 200
        
    except Exception as e:
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
            if app.task:
                app_dict['task'] = translate_task_if_needed(app.task.to_dict(), lang)
            results.append(app_dict)
        
        return jsonify({
            'applications': results,
            'total': len(results)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
