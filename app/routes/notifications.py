"""Notification routes for user notifications."""

from flask import Blueprint, request, jsonify
from app import db
from app.models import Notification, NotificationType
from app.utils import token_required
from datetime import datetime

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('', methods=['GET'])
@token_required
def get_notifications(current_user_id):
    """Get all notifications for the current user.
    
    Query params:
        - unread_only: If 'true', only return unread notifications
        - page: Page number (default 1)
        - per_page: Results per page (default 20, max 100)
    """
    try:
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        query = Notification.query.filter_by(user_id=current_user_id)
        
        if unread_only:
            query = query.filter_by(is_read=False)
        
        notifications = query.order_by(Notification.created_at.desc()).paginate(
            page=page, per_page=per_page
        )
        
        return jsonify({
            'notifications': [n.to_dict() for n in notifications.items],
            'total': notifications.total,
            'page': page,
            'per_page': per_page,
            'has_more': notifications.has_next,
            'unread_count': Notification.query.filter_by(
                user_id=current_user_id, 
                is_read=False
            ).count()
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@notifications_bp.route('/unread-count', methods=['GET'])
@token_required
def get_unread_count(current_user_id):
    """Get count of unread notifications."""
    try:
        unread_count = Notification.query.filter_by(
            user_id=current_user_id,
            is_read=False
        ).count()
        
        # Also get counts by type for badges
        accepted_count = Notification.query.filter_by(
            user_id=current_user_id,
            is_read=False,
            type=NotificationType.APPLICATION_ACCEPTED
        ).count()
        
        return jsonify({
            'unread_count': unread_count,
            'accepted_applications': accepted_count
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@notifications_bp.route('/mark-read', methods=['POST'])
@token_required
def mark_notifications_by_type(current_user_id):
    """Mark notifications as read by type.
    
    Body params:
        - type: 'accepted_applications' | 'all'
    """
    try:
        data = request.get_json() or {}
        notification_type = data.get('type', 'all')
        
        now = datetime.utcnow()
        query = Notification.query.filter_by(
            user_id=current_user_id,
            is_read=False
        )
        
        # Filter by notification type if specified
        if notification_type == 'accepted_applications':
            query = query.filter_by(type=NotificationType.APPLICATION_ACCEPTED)
        elif notification_type == 'new_applications':
            query = query.filter_by(type=NotificationType.NEW_APPLICATION)
        elif notification_type == 'task_marked_done':
            query = query.filter_by(type=NotificationType.TASK_MARKED_DONE)
        elif notification_type == 'task_completed':
            query = query.filter_by(type=NotificationType.TASK_COMPLETED)
        # 'all' type marks all unread notifications
        
        updated_count = query.update({
            'is_read': True,
            'read_at': now
        })
        
        db.session.commit()
        
        return jsonify({
            'message': f'Marked {updated_count} notification(s) as read',
            'updated_count': updated_count
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@notifications_bp.route('/<int:notification_id>/read', methods=['POST'])
@token_required
def mark_as_read(current_user_id, notification_id):
    """Mark a notification as read."""
    try:
        notification = Notification.query.get(notification_id)
        
        if not notification:
            return jsonify({'error': 'Notification not found'}), 404
        
        if notification.user_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        notification.mark_as_read()
        db.session.commit()
        
        return jsonify({
            'message': 'Notification marked as read',
            'notification': notification.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@notifications_bp.route('/read-all', methods=['POST'])
@token_required
def mark_all_as_read(current_user_id):
    """Mark all notifications as read for current user."""
    try:
        now = datetime.utcnow()
        
        Notification.query.filter_by(
            user_id=current_user_id,
            is_read=False
        ).update({
            'is_read': True,
            'read_at': now
        })
        
        db.session.commit()
        
        return jsonify({
            'message': 'All notifications marked as read'
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@notifications_bp.route('/<int:notification_id>', methods=['DELETE'])
@token_required
def delete_notification(current_user_id, notification_id):
    """Delete a notification."""
    try:
        notification = Notification.query.get(notification_id)
        
        if not notification:
            return jsonify({'error': 'Notification not found'}), 404
        
        if notification.user_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        db.session.delete(notification)
        db.session.commit()
        
        return jsonify({
            'message': 'Notification deleted'
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============ HELPER FUNCTIONS FOR CREATING NOTIFICATIONS ============

def create_notification(user_id: int, notification_type: str, title: str, message: str, 
                       related_type: str = None, related_id: int = None) -> Notification:
    """Helper function to create a notification.
    
    Args:
        user_id: The ID of the user to notify
        notification_type: Type of notification (use NotificationType constants)
        title: Short title for the notification
        message: Detailed message
        related_type: Type of related entity ('task', 'application', etc.)
        related_id: ID of the related entity
    
    Returns:
        The created Notification object
    """
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        message=message,
        related_type=related_type,
        related_id=related_id
    )
    
    db.session.add(notification)
    return notification


def notify_application_accepted(applicant_id: int, task_title: str, task_id: int) -> Notification:
    """Create notification when a job application is accepted."""
    return create_notification(
        user_id=applicant_id,
        notification_type=NotificationType.APPLICATION_ACCEPTED,
        title='🎉 Application Accepted!',
        message=f'Congratulations! Your application for "{task_title}" has been accepted. You can now start working on this task.',
        related_type='task',
        related_id=task_id
    )


def notify_application_rejected(applicant_id: int, task_title: str, task_id: int) -> Notification:
    """Create notification when a job application is rejected."""
    return create_notification(
        user_id=applicant_id,
        notification_type=NotificationType.APPLICATION_REJECTED,
        title='Application Update',
        message=f'Your application for "{task_title}" was not selected. Keep applying to other tasks!',
        related_type='task',
        related_id=task_id
    )


def notify_new_application(creator_id: int, applicant_name: str, task_title: str, task_id: int) -> Notification:
    """Create notification when someone applies to a task."""
    return create_notification(
        user_id=creator_id,
        notification_type=NotificationType.NEW_APPLICATION,
        title='New Application Received',
        message=f'{applicant_name} applied for your task "{task_title}".',
        related_type='task',
        related_id=task_id
    )


def notify_task_marked_done(creator_id: int, worker_name: str, task_title: str, task_id: int) -> Notification:
    """Create notification when worker marks task as done."""
    return create_notification(
        user_id=creator_id,
        notification_type=NotificationType.TASK_MARKED_DONE,
        title='Task Marked as Done',
        message=f'{worker_name} has marked "{task_title}" as complete. Please review and confirm.',
        related_type='task',
        related_id=task_id
    )


def notify_task_completed(worker_id: int, task_title: str, task_id: int) -> Notification:
    """Create notification when task is confirmed complete."""
    return create_notification(
        user_id=worker_id,
        notification_type=NotificationType.TASK_COMPLETED,
        title='✅ Task Completed!',
        message=f'Great job! "{task_title}" has been confirmed as complete.',
        related_type='task',
        related_id=task_id
    )
