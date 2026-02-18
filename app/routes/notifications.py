"""Notification routes for user notifications."""

import traceback
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
        print(f'[NOTIFICATIONS ERROR] get_notifications: {e}')
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@notifications_bp.route('/unread-count', methods=['GET'])
@token_required
def get_unread_count(current_user_id):
    """Get count of unread notifications."""
    try:
        print(f'[NOTIFICATIONS] unread-count called for user_id={current_user_id}')
        
        unread_count = Notification.query.filter_by(
            user_id=current_user_id,
            is_read=False
        ).count()
        
        print(f'[NOTIFICATIONS] unread_count={unread_count}, checking accepted...')
        
        # Also get counts by type for badges
        accepted_count = Notification.query.filter_by(
            user_id=current_user_id,
            is_read=False,
            type=NotificationType.APPLICATION_ACCEPTED
        ).count()
        
        print(f'[NOTIFICATIONS] accepted_count={accepted_count}, returning 200')
        
        return jsonify({
            'unread_count': unread_count,
            'accepted_applications': accepted_count
        }), 200
    except Exception as e:
        print(f'[NOTIFICATIONS ERROR] unread-count: {type(e).__name__}: {e}')
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@notifications_bp.route('/mark-read', methods=['POST'])
@token_required
def mark_notifications_by_type(current_user_id):
    """Mark notifications as read by type.
    
    Body params:
        - type: 'accepted_applications' | 'new_applications' | 'task_marked_done' |
                'task_completed' | 'review_reminder' | 'task_disputed' |
                'task_cancelled' | 'new_review' | 'new_task_nearby' | 'all'
    """
    try:
        data = request.get_json() or {}
        notification_type = data.get('type', 'all')
        
        now = datetime.utcnow()
        query = Notification.query.filter_by(
            user_id=current_user_id,
            is_read=False
        )
        
        # Map request type names to NotificationType constants
        type_map = {
            'accepted_applications': NotificationType.APPLICATION_ACCEPTED,
            'new_applications': NotificationType.NEW_APPLICATION,
            'task_marked_done': NotificationType.TASK_MARKED_DONE,
            'task_completed': NotificationType.TASK_COMPLETED,
            'review_reminder': NotificationType.REVIEW_REMINDER,
            'task_disputed': NotificationType.TASK_DISPUTED,
            'task_cancelled': NotificationType.TASK_CANCELLED,
            'new_review': NotificationType.NEW_REVIEW,
            'application_rejected': NotificationType.APPLICATION_REJECTED,
            'new_task_nearby': NotificationType.NEW_TASK_NEARBY,
        }
        
        if notification_type in type_map:
            query = query.filter_by(type=type_map[notification_type])
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
        print(f'[NOTIFICATIONS ERROR] mark-read: {e}')
        traceback.print_exc()
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


# ============ JOB ALERT PREFERENCES ============

@notifications_bp.route('/job-alerts', methods=['GET'])
@token_required
def get_job_alert_preferences(current_user_id):
    """Get the current user's job alert preferences."""
    try:
        from app.models import User
        user = User.query.get(current_user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'preferences': user.get_job_alert_prefs()
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@notifications_bp.route('/job-alerts', methods=['PUT'])
@token_required
def update_job_alert_preferences(current_user_id):
    """Update the current user's job alert preferences.
    
    Body:
    {
        "enabled": true,
        "radius_km": 10,
        "categories": ["cleaning", "delivery"]
    }
    
    - enabled: Whether to receive job alerts (bool)
    - radius_km: Search radius in km, 1-50 (number)
    - categories: List of category keys to filter by. Empty list = all categories.
    """
    try:
        from app.models import User
        user = User.query.get(current_user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        # Validate
        prefs = user.get_job_alert_prefs()
        
        if 'enabled' in data:
            prefs['enabled'] = bool(data['enabled'])
        
        if 'radius_km' in data:
            radius = data['radius_km']
            if not isinstance(radius, (int, float)) or radius < 1 or radius > 50:
                return jsonify({'error': 'radius_km must be a number between 1 and 50'}), 400
            prefs['radius_km'] = radius
        
        if 'categories' in data:
            cats = data['categories']
            if not isinstance(cats, list):
                return jsonify({'error': 'categories must be a list'}), 400
            if len(cats) > 10:
                return jsonify({'error': 'Maximum 10 categories allowed'}), 400
            prefs['categories'] = cats
        
        # Check location requirement when enabling
        if prefs['enabled'] and (user.latitude is None or user.longitude is None):
            return jsonify({
                'error': 'Location required. Set your location in profile settings to receive job alerts.'
            }), 400
        
        user.set_job_alert_prefs(prefs)
        db.session.commit()
        
        return jsonify({
            'message': 'Job alert preferences updated',
            'preferences': prefs
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============ HELPER FUNCTIONS FOR CREATING NOTIFICATIONS ============

def create_notification(user_id: int, notification_type: str, title: str, message: str, 
                       related_type: str = None, related_id: int = None,
                       data: dict = None) -> Notification:
    """Helper function to create a notification.
    
    Args:
        user_id: The ID of the user to notify
        notification_type: Type of notification (use NotificationType constants)
        title: Short title for the notification (English fallback)
        message: Detailed message (English fallback)
        related_type: Type of related entity ('task', 'application', etc.)
        related_id: ID of the related entity
        data: Dictionary with dynamic values for i18n (task_title, applicant_name, etc.)
    
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
    
    if data:
        notification.set_data(data)
    
    db.session.add(notification)
    return notification


def notify_application_accepted(applicant_id: int, task_title: str, task_id: int) -> Notification:
    """Create notification when a job application is accepted."""
    return create_notification(
        user_id=applicant_id,
        notification_type=NotificationType.APPLICATION_ACCEPTED,
        title='\U0001f389 Application Accepted!',
        message=f'Congratulations! Your application for "{task_title}" has been accepted. You can now start working on this task.',
        related_type='task',
        related_id=task_id,
        data={'task_title': task_title}
    )


def notify_application_rejected(applicant_id: int, task_title: str, task_id: int) -> Notification:
    """Create notification when a job application is rejected."""
    return create_notification(
        user_id=applicant_id,
        notification_type=NotificationType.APPLICATION_REJECTED,
        title='Application Update',
        message=f'Your application for "{task_title}" was not selected. Keep applying to other tasks!',
        related_type='task',
        related_id=task_id,
        data={'task_title': task_title}
    )


def notify_new_application(creator_id: int, applicant_name: str, task_title: str, task_id: int) -> Notification:
    """Create notification when someone applies to a task."""
    return create_notification(
        user_id=creator_id,
        notification_type=NotificationType.NEW_APPLICATION,
        title='New Application Received',
        message=f'{applicant_name} applied for your task "{task_title}".',
        related_type='task',
        related_id=task_id,
        data={'applicant_name': applicant_name, 'task_title': task_title}
    )


def notify_task_marked_done(creator_id: int, worker_name: str, task_title: str, task_id: int) -> Notification:
    """Create notification when worker marks task as done."""
    return create_notification(
        user_id=creator_id,
        notification_type=NotificationType.TASK_MARKED_DONE,
        title='Task Marked as Done',
        message=f'{worker_name} has marked "{task_title}" as complete. Please review and confirm.',
        related_type='task',
        related_id=task_id,
        data={'worker_name': worker_name, 'task_title': task_title}
    )


def notify_task_completed(worker_id: int, task_title: str, task_id: int) -> Notification:
    """Create notification when task is confirmed complete."""
    return create_notification(
        user_id=worker_id,
        notification_type=NotificationType.TASK_COMPLETED,
        title='\u2705 Task Completed!',
        message=f'Great job! "{task_title}" has been confirmed as complete.',
        related_type='task',
        related_id=task_id,
        data={'task_title': task_title}
    )


def notify_review_reminder(user_id: int, other_party_name: str, task_title: str, task_id: int) -> Notification:
    """Create notification prompting user to leave a review after task completion."""
    return create_notification(
        user_id=user_id,
        notification_type=NotificationType.REVIEW_REMINDER,
        title='\u2b50 Leave a Review',
        message=f'"{task_title}" is complete! Take a moment to leave a review for {other_party_name}.',
        related_type='task',
        related_id=task_id,
        data={'task_title': task_title, 'other_party_name': other_party_name}
    )


def notify_task_disputed(user_id: int, task_title: str, task_id: int, is_creator: bool = False) -> Notification:
    """Create notification when a task is disputed."""
    if is_creator:
        message = f'A dispute has been raised for your task "{task_title}". Our team will review it shortly.'
    else:
        message = f'The task "{task_title}" has been disputed. Our team will review it shortly.'
    
    return create_notification(
        user_id=user_id,
        notification_type=NotificationType.TASK_DISPUTED,
        title='\u26a0\ufe0f Task Disputed',
        message=message,
        related_type='task',
        related_id=task_id,
        data={'task_title': task_title, 'is_creator': is_creator}
    )


def notify_task_cancelled(user_id: int, task_title: str, task_id: int) -> Notification:
    """Create notification when a task the user is involved in gets cancelled."""
    return create_notification(
        user_id=user_id,
        notification_type=NotificationType.TASK_CANCELLED,
        title='\u274c Task Cancelled',
        message=f'The task "{task_title}" has been cancelled by the creator.',
        related_type='task',
        related_id=task_id,
        data={'task_title': task_title}
    )


def notify_new_review(user_id: int, reviewer_name: str, task_title: str, task_id: int, rating: int) -> Notification:
    """Create notification when someone leaves a review for you."""
    stars = '\u2b50' * min(rating, 5)
    return create_notification(
        user_id=user_id,
        notification_type=NotificationType.NEW_REVIEW,
        title=f'{stars} New Review!',
        message=f'{reviewer_name} left a {rating}-star review for "{task_title}".',
        related_type='task',
        related_id=task_id,
        data={'reviewer_name': reviewer_name, 'task_title': task_title, 'rating': rating}
    )


def notify_new_task_nearby(user_id: int, task_title: str, task_id: int,
                           category_key: str, distance_km: float,
                           budget: str = None, location: str = None) -> Notification:
    """Create notification when a new task is posted near a user with job alerts on.
    
    Args:
        user_id: The user to notify
        task_title: Title of the new task
        task_id: ID of the new task
        category_key: Raw category key (e.g. 'cleaning') — frontend translates
        distance_km: Distance in km from user to task
        budget: Optional budget string (e.g. '€25' or '€15/hr')
        location: Optional location name
    """
    dist_display = f'{distance_km:.1f} km'
    return create_notification(
        user_id=user_id,
        notification_type=NotificationType.NEW_TASK_NEARBY,
        title=f'\U0001f4cd New {category_key} task nearby',
        message=f'New task "{task_title}" posted {dist_display} away.',
        related_type='task',
        related_id=task_id,
        data={
            'task_title': task_title,
            'category_key': category_key,
            'distance': dist_display,
            'budget': budget,
            'location': location,
        }
    )
