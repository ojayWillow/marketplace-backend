"""Push notification service for sending web push notifications."""

import os
import json
from pywebpush import webpush, WebPushException
from app import db
from app.models import PushSubscription, User

# VAPID keys - these should be set in environment variables
VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY', '')
VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY', '')
VAPID_CLAIMS = {
    'sub': os.getenv('VAPID_SUBJECT', 'mailto:support@tirgus.lv')
}


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
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        print('VAPID keys not configured - skipping push notification')
        return {'sent': 0, 'failed': 0, 'error': 'VAPID keys not configured'}
    
    # Get all active subscriptions for this user
    subscriptions = PushSubscription.query.filter_by(
        user_id=user_id,
        is_active=True
    ).all()
    
    if not subscriptions:
        return {'sent': 0, 'failed': 0, 'error': 'No active subscriptions'}
    
    # Build notification payload
    payload = {
        'title': title,
        'body': body,
        'icon': icon or '/icons/icon-192x192.png',
        'badge': '/icons/badge-72x72.png',
        'tag': tag,
        'data': {
            'url': url or '/'
        }
    }
    
    sent_count = 0
    failed_count = 0
    
    for subscription in subscriptions:
        try:
            subscription_info = {
                'endpoint': subscription.endpoint,
                'keys': {
                    'p256dh': subscription.p256dh_key,
                    'auth': subscription.auth_key
                }
            }
            
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS
            )
            sent_count += 1
            
        except WebPushException as e:
            failed_count += 1
            # If subscription is invalid/expired, deactivate it
            if e.response and e.response.status_code in [404, 410]:
                subscription.is_active = False
                db.session.commit()
            print(f'Push notification failed for subscription {subscription.id}: {e}')
        except Exception as e:
            failed_count += 1
            print(f'Unexpected error sending push: {e}')
    
    return {'sent': sent_count, 'failed': failed_count}


# ============ NOTIFICATION HELPER FUNCTIONS ============

def notify_new_message(recipient_id: int, sender_name: str, message_preview: str, 
                       conversation_id: int):
    """
    Send push notification for new message.
    """
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
    return send_push_notification(
        user_id=worker_id,
        title='🌟 Great job!',
        body=f'"{task_title}" has been confirmed complete.',
        url=f'/tasks/{task_id}',
        tag=f'confirmed-{task_id}'
    )


def notify_new_job_nearby(user_id: int, task_title: str, task_id: int, 
                          distance_km: float):
    """
    Send push notification for new job posted nearby (optional feature).
    """
    return send_push_notification(
        user_id=user_id,
        title='💼 New Job Nearby!',
        body=f'"{task_title}" - {distance_km:.1f}km away',
        url=f'/tasks/{task_id}',
        tag='new-job-nearby'
    )
