"""Task application system routes."""

from flask import request, jsonify
from app import db
from app.models import TaskRequest, User, TaskApplication
from app.services.push_notifications import (
    notify_application_received,
    notify_application_accepted,
    notify_application_rejected
)
from app.utils import token_required, get_display_name, send_push_safe
from app.routes.tasks import tasks_bp
from app.routes.tasks.helpers import translate_task_if_needed
from datetime import datetime


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
        
        if task.creator_id == current_user_id:
            return jsonify({'error': 'You cannot apply to your own task'}), 400
        
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
        
        creator_id = task.creator_id
        task_title = task.title
        
        applicant = User.query.get(current_user_id)
        applicant_name = get_display_name(applicant)
        send_push_safe(
            notify_application_received,
            task_owner_id=creator_id,
            applicant_name=applicant_name,
            task_title=task_title,
            task_id=task_id
        )
        
        try:
            from app.routes.notifications import notify_new_application
            notify_new_application(creator_id, applicant_name, task_title, task_id)
            db.session.commit()
        except Exception as notify_error:
            db.session.rollback()
            print(f"In-app notification skipped (non-critical): {notify_error}")
        
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
        
        if task.creator_id != current_user_id:
            return jsonify({'error': 'Only the task creator can accept applications'}), 403
        
        if task.status != 'open':
            return jsonify({'error': 'Task is no longer accepting applications'}), 400
        
        application = TaskApplication.query.get(application_id)
        if not application or application.task_id != task_id:
            return jsonify({'error': 'Application not found'}), 404
        
        if application.status != 'pending':
            return jsonify({'error': 'Application has already been processed'}), 400
        
        application.status = 'accepted'
        task.assigned_to_id = application.applicant_id
        task.status = 'assigned'
        task.updated_at = datetime.utcnow()
        
        other_applications = TaskApplication.query.filter(
            TaskApplication.task_id == task_id,
            TaskApplication.id != application_id,
            TaskApplication.status == 'pending'
        ).all()
        
        rejected_applicant_ids = [other_app.applicant_id for other_app in other_applications]
        
        for other_app in other_applications:
            other_app.status = 'rejected'
        
        db.session.commit()
        
        task_dict = task.to_dict()
        application_dict = application.to_dict()
        accepted_applicant_id = application.applicant_id
        task_title = task.title
        
        send_push_safe(
            notify_application_accepted,
            applicant_id=accepted_applicant_id,
            task_title=task_title,
            task_id=task_id
        )
        
        for rejected_id in rejected_applicant_ids:
            send_push_safe(
                notify_application_rejected,
                applicant_id=rejected_id,
                task_title=task_title
            )
        
        try:
            from app.routes.notifications import notify_application_accepted as inapp_notify_accepted
            inapp_notify_accepted(accepted_applicant_id, task_title, task_id)
            db.session.commit()
        except Exception as notify_error:
            db.session.rollback()
            print(f"In-app accepted notification skipped (non-critical): {notify_error}")
        
        for rejected_id in rejected_applicant_ids:
            try:
                from app.routes.notifications import notify_application_rejected as inapp_notify_rejected
                inapp_notify_rejected(rejected_id, task_title, task_id)
                db.session.commit()
            except Exception as notify_error:
                db.session.rollback()
                print(f"In-app rejected notification skipped (non-critical): {notify_error}")
        
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
        
        if task.creator_id != current_user_id:
            return jsonify({'error': 'Only the task creator can reject applications'}), 403
        
        application = TaskApplication.query.get(application_id)
        if not application or application.task_id != task_id:
            return jsonify({'error': 'Application not found'}), 404
        
        if application.status != 'pending':
            return jsonify({'error': 'Application has already been processed'}), 400
        
        application.status = 'rejected'
        db.session.commit()
        
        applicant_id = application.applicant_id
        task_title = task.title
        application_dict = application.to_dict()
        
        send_push_safe(
            notify_application_rejected,
            applicant_id=applicant_id,
            task_title=task_title
        )
        
        try:
            from app.routes.notifications import notify_application_rejected as inapp_notify_rejected
            inapp_notify_rejected(applicant_id, task_title, task_id)
            db.session.commit()
        except Exception as notify_error:
            db.session.rollback()
            print(f"In-app notification skipped (non-critical): {notify_error}")
        
        return jsonify({
            'message': 'Application rejected',
            'application': application_dict
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
        
        if application.applicant_id != current_user_id:
            return jsonify({'error': 'Only the applicant can withdraw this application'}), 403
        
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
