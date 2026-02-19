"""Task workflow/lifecycle routes (mark-done, confirm, dispute, cancel)."""

from flask import request, jsonify
from app import db
from app.models import TaskRequest, User
from app.utils import token_required, get_display_name
from app.routes.tasks import tasks_bp
from datetime import datetime


@tasks_bp.route('/<int:task_id>/mark-done', methods=['POST'])
@token_required
def mark_task_done(current_user_id, task_id):
    """Worker marks task as done - awaiting creator confirmation."""
    try:
        task = TaskRequest.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        if task.assigned_to_id != current_user_id:
            return jsonify({'error': 'Only the assigned worker can mark this task as done'}), 403
        
        if task.status not in ['assigned', 'in_progress']:
            return jsonify({'error': 'Task cannot be marked as done in current status'}), 400
        
        task.status = 'pending_confirmation'
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        task_dict = task.to_dict()
        creator_id = task.creator_id
        task_title = task.title
        
        worker = User.query.get(current_user_id)
        worker_name = get_display_name(worker)
        
        # Unified: in-app + push handled by create_notification()
        try:
            from app.routes.notifications import notify_task_marked_done as inapp_notify_done
            inapp_notify_done(creator_id, worker_name, task_title, task_id)
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
        
        if task.creator_id != current_user_id:
            return jsonify({'error': 'Only the task creator can confirm completion'}), 403
        
        if task.status != 'pending_confirmation':
            return jsonify({'error': 'Task is not pending confirmation'}), 400
        
        task.status = 'completed'
        task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        task_dict = task.to_dict()
        worker_id = task.assigned_to_id
        task_title = task.title
        
        # Unified: in-app + push handled by create_notification()
        try:
            from app.routes.notifications import (
                notify_task_completed as inapp_notify_completed,
                notify_review_reminder
            )
            
            # 1. Tell the worker the task is confirmed complete
            inapp_notify_completed(worker_id, task_title, task_id)
            
            # 2. Send review reminder to the worker (to review the creator)
            creator = User.query.get(current_user_id)
            creator_name = get_display_name(creator)
            notify_review_reminder(worker_id, creator_name, task_title, task_id)
            
            # 3. Send review reminder to the creator (to review the worker)
            worker = User.query.get(worker_id)
            worker_name = get_display_name(worker)
            notify_review_reminder(current_user_id, worker_name, task_title, task_id)
            
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
        
        if task.creator_id != current_user_id:
            return jsonify({'error': 'Only the task creator can dispute'}), 403
        
        if task.status != 'pending_confirmation':
            return jsonify({'error': 'Task is not pending confirmation'}), 400
        
        data = request.get_json() or {}
        reason = data.get('reason', '')
        
        task.status = 'disputed'
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        task_title = task.title
        worker_id = task.assigned_to_id
        
        # Unified: in-app + push handled by create_notification()
        if worker_id:
            try:
                from app.routes.notifications import notify_task_disputed as inapp_notify_disputed
                inapp_notify_disputed(worker_id, task_title, task_id, is_creator=False)
                db.session.commit()
            except Exception as notify_error:
                db.session.rollback()
                print(f"Notification skipped (non-critical): {notify_error}")
        
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
        
        if task.creator_id != current_user_id:
            return jsonify({'error': 'Only the task creator can cancel'}), 403
        
        if task.status in ['completed', 'cancelled']:
            return jsonify({'error': 'Task cannot be cancelled'}), 400
        
        worker_id = task.assigned_to_id
        task_title = task.title
        
        task.status = 'cancelled'
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Unified: in-app + push handled by create_notification()
        if worker_id:
            try:
                from app.routes.notifications import notify_task_cancelled
                notify_task_cancelled(worker_id, task_title, task_id)
                db.session.commit()
            except Exception as notify_error:
                db.session.rollback()
                print(f"Notification skipped (non-critical): {notify_error}")
        
        return jsonify({
            'message': 'Task has been cancelled.',
            'task': task.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
