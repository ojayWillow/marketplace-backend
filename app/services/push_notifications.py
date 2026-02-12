"""Push notification service for sending web push notifications."""

import os
import json
import logging
from pywebpush import webpush, WebPushException
from app import db
from app.models import PushSubscription, User

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# VAPID keys - these should be set in environment variables
VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY', '')
VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY', '')
VAPID_CLAIMS = {
    'sub': os.getenv('VAPID_SUBJECT', 'mailto:support@tirgus.lv')
}

# Log VAPID configuration status on module load
logger.info(f'[PUSH] VAPID_PUBLIC_KEY configured: {bool(VAPID_PUBLIC_KEY)} (length: {len(VAPID_PUBLIC_KEY)})')
logger.info(f'[PUSH] VAPID_PRIVATE_KEY configured: {bool(VAPID_PRIVATE_KEY)} (length: {len(VAPID_PRIVATE_KEY)})')
logger.info(f'[PUSH] VAPID_CLAIMS: {VAPID_CLAIMS}')


def send_push_notification(user_id: int, title: str, body: str, 
                           url: str = None, tag: str = None, 
                           icon: str = None) -> dict:
    """
    Send push notification to all devices registered for a user.
    
    Args:
        user_id: The user to send notification to
        title: Notification title
        body: Notification body text
        url: URL to open when notification is clicked (optional)
        tag: Tag for grouping/replacing notifications (optional)
        icon: Icon URL (optional)
    
    Returns:
        dict with 'sent' count and 'failed' count
    """
    logger.info(f'[PUSH] === Starting push notification ===')
    logger.info(f'[PUSH] Recipient user_id: {user_id}')
    logger.info(f'[PUSH] Title: {title}')
    logger.info(f'[PUSH] Body: {body[:50]}...' if len(body) > 50 else f'[PUSH] Body: {body}')
    
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        logger.error('[PUSH] VAPID keys not configured - skipping push notification')
        return {'sent': 0, 'failed': 0, 'error': 'VAPID keys not configured'}
    
    # Get all active subscriptions for this user
    subscriptions = PushSubscription.query.filter_by(
        user_id=user_id,
        is_active=True
    ).all()
    
    logger.info(f'[PUSH] Found {len(subscriptions)} active subscription(s) for user {user_id}')
    
    if not subscriptions:
        logger.warning(f'[PUSH] No active subscriptions for user {user_id}')
        return {'sent': 0, 'failed': 0, 'error': 'No active subscriptions'}
    
    # Build notification payload - ensure all values are JSON-serializable primitives
    payload = {
        'title': str(title) if title else '',
        'body': str(body) if body else '',
        'icon': str(icon) if icon else '/icons/icon-192x192.png',
        'badge': '/icons/badge-72x72.png',
        'tag': str(tag) if tag else 'notification',
        'data': {
            'url': str(url) if url else '/'
        }
    }
    
    # Try to serialize payload to catch any circular reference issues
    try:
        payload_json = json.dumps(payload)
        logger.info(f'[PUSH] Payload: {payload_json}')
    except (TypeError, ValueError, RecursionError) as e:
        logger.error(f'[PUSH] Failed to serialize payload: {type(e).__name__}: {e}')
        return {'sent': 0, 'failed': len(subscriptions), 'error': f'Payload serialization error: {e}'}
    
    sent_count = 0
    failed_count = 0
    
    for subscription in subscriptions:
        logger.info(f'[PUSH] Sending to subscription {subscription.id} (device: {subscription.device_name})')
        logger.info(f'[PUSH] Endpoint: {subscription.endpoint[:80]}...')
        
        try:
            subscription_info = {
                'endpoint': subscription.endpoint,
                'keys': {
                    'p256dh': subscription.p256dh_key,
                    'auth': subscription.auth_key
                }
            }
            
            response = webpush(
                subscription_info=subscription_info,
                data=payload_json,  # Use pre-serialized payload
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS
            )
            
            logger.info(f'[PUSH] SUCCESS - Notification sent to subscription {subscription.id}')
            sent_count += 1
            
        except WebPushException as e:
            failed_count += 1
            logger.error(f'[PUSH] WebPushException for subscription {subscription.id}: {e}')
            if e.response:
                logger.error(f'[PUSH] Response status: {e.response.status_code}')
                logger.error(f'[PUSH] Response body: {e.response.text[:500] if e.response.text else "empty"}')
            
            # If subscription is invalid/expired, deactivate it
            if e.response and e.response.status_code in [404, 410]:
                logger.warning(f'[PUSH] Deactivating invalid subscription {subscription.id}')
                subscription.is_active = False
                try:
                    db.session.commit()
                except Exception as commit_error:
                    logger.error(f'[PUSH] Failed to deactivate subscription: {commit_error}')
                    db.session.rollback()
                
        except (RecursionError, TypeError, ValueError) as e:
            failed_count += 1
            logger.error(f'[PUSH] Serialization error for subscription {subscription.id}: {type(e).__name__}: {e}')
            
        except Exception as e:
            failed_count += 1
            logger.error(f'[PUSH] Unexpected error for subscription {subscription.id}: {type(e).__name__}: {e}')
            import traceback
            logger.error(traceback.format_exc())
    
    result = {'sent': sent_count, 'failed': failed_count}
    logger.info(f'[PUSH] === Completed: {result} ===')
    return result


# ============ NOTIFICATION HELPER FUNCTIONS ============

def notify_new_message(recipient_id: int, sender_name: str, message_preview: str, 
                       conversation_id: int):
    """
    Send push notification for new message.
    """
    logger.info(f'[PUSH] notify_new_message called - recipient: {recipient_id}, sender: {sender_name}')
    return send_push_notification(
        user_id=recipient_id,
        title=f'💬 {sender_name}',
        body=message_preview[:100] + ('...' if len(message_preview) > 100 else ''),
        url=f'/messages/{conversation_id}',
        tag=f'message-{conversation_id}'  # Replace previous messages from same conversation
    )


def notify_application_received(task_owner_id: int, applicant_name: str, 
                                 task_title: str, task_id: int):
    """
    Send push notification when someone applies to a task.
    """
    logger.info(f'[PUSH] notify_application_received called - owner: {task_owner_id}')
    return send_push_notification(
        user_id=task_owner_id,
        title='👋 New Application!',
        body=f'{applicant_name} applied for "{task_title}"',
        url=f'/tasks/{task_id}',
        tag=f'application-{task_id}'
    )


def notify_application_accepted(applicant_id: int, task_title: str, task_id: int):
    """
    Send push notification when application is accepted.
    """
    logger.info(f'[PUSH] notify_application_accepted called - applicant: {applicant_id}')
    return send_push_notification(
        user_id=applicant_id,
        title='🎉 Application Accepted!',
        body=f'You got the job! "{task_title}"',
        url=f'/tasks/{task_id}',
        tag=f'accepted-{task_id}'
    )


def notify_application_rejected(applicant_id: int, task_title: str):
    """
    Send push notification when application is rejected.
    """
    logger.info(f'[PUSH] notify_application_rejected called - applicant: {applicant_id}')
    return send_push_notification(
        user_id=applicant_id,
        title='Application Update',
        body=f'Your application for "{task_title}" was not selected.',
        url='/tasks',
        tag='application-rejected'
    )


def notify_task_marked_done(task_owner_id: int, worker_name: str, 
                            task_title: str, task_id: int):
    """
    Send push notification when worker marks task as done.
    """
    logger.info(f'[PUSH] notify_task_marked_done called - owner: {task_owner_id}')
    return send_push_notification(
        user_id=task_owner_id,
        title='✅ Task Completed',
        body=f'{worker_name} finished "{task_title}". Please review.',
        url=f'/tasks/{task_id}',
        tag=f'done-{task_id}'
    )


def notify_task_confirmed(worker_id: int, task_title: str, task_id: int):
    """
    Send push notification when task owner confirms completion.
    """
    logger.info(f'[PUSH] notify_task_confirmed called - worker: {worker_id}')
    return send_push_notification(
        user_id=worker_id,
        title='🌟 Great job!',
        body=f'"{task_title}" has been confirmed complete.',
        url=f'/tasks/{task_id}',
        tag=f'confirmed-{task_id}'
    )


def notify_task_disputed(user_id: int, task_title: str, task_id: int):
    """
    Send push notification when a task is disputed.
    """
    logger.info(f'[PUSH] notify_task_disputed called - user: {user_id}')
    return send_push_notification(
        user_id=user_id,
        title='⚠️ Task Disputed',
        body=f'A dispute has been raised for "{task_title}". Please check.',
        url=f'/tasks/{task_id}',
        tag=f'disputed-{task_id}'
    )


def notify_task_cancelled(user_id: int, task_title: str, task_id: int):
    """
    Send push notification when a task is cancelled by the creator.
    """
    logger.info(f'[PUSH] notify_task_cancelled called - user: {user_id}')
    return send_push_notification(
        user_id=user_id,
        title='❌ Task Cancelled',
        body=f'The task "{task_title}" has been cancelled.',
        url=f'/tasks/{task_id}',
        tag=f'cancelled-{task_id}'
    )


def notify_new_review(user_id: int, reviewer_name: str, task_title: str,
                      task_id: int, rating: int):
    """
    Send push notification when someone leaves a review for you.
    """
    logger.info(f'[PUSH] notify_new_review called - user: {user_id}')
    stars = '⭐' * min(rating, 5)
    return send_push_notification(
        user_id=user_id,
        title=f'{stars} New Review!',
        body=f'{reviewer_name} left a review for "{task_title}".',
        url=f'/tasks/{task_id}',
        tag=f'review-{task_id}'
    )


def notify_new_job_nearby(user_id: int, task_title: str, task_id: int, 
                          distance_km: float):
    """
    Send push notification for new job posted nearby (optional feature).
    """
    logger.info(f'[PUSH] notify_new_job_nearby called - user: {user_id}')
    return send_push_notification(
        user_id=user_id,
        title='💼 New Job Nearby!',
        body=f'"{task_title}" - {distance_km:.1f}km away',
        url=f'/tasks/{task_id}',
        tag='new-job-nearby'
    )
