"""Service for sending job alert notifications to nearby users.

Called after a new task is created. Finds users who:
1. Have job alerts enabled
2. Have a stored location (latitude/longitude)
3. Are within their configured radius of the new task
4. Match category preferences (or have no category filter = all)
5. Are NOT the task creator

Creates a new_task_nearby notification for each matching user.
"""

import logging
from app import db
from app.models import User
from app.routes.tasks.helpers import distance

logger = logging.getLogger(__name__)

# Maximum users to notify per task (safety limit)
MAX_NOTIFY_PER_TASK = 50


def send_job_alerts_for_task(task) -> int:
    """Find nearby users with job alerts on and notify them.
    
    Args:
        task: A TaskRequest object (must have id, title, category,
              latitude, longitude, budget, location, creator_id)
    
    Returns:
        Number of notifications created
    """
    from app.routes.notifications import notify_new_task_nearby
    
    # Task must have coordinates
    if task.latitude is None or task.longitude is None:
        logger.debug(f'Task {task.id} has no coordinates, skipping job alerts')
        return 0
    
    # Find all users with job alerts enabled + location set.
    # We filter in Python because job_alert_preferences is a JSON text field.
    candidates = User.query.filter(
        User.latitude.isnot(None),
        User.longitude.isnot(None),
        User.job_alert_preferences.isnot(None),
        User.id != task.creator_id,  # Don't notify the creator
        User.is_active == True,
    ).all()
    
    notified = 0
    
    for user in candidates:
        if notified >= MAX_NOTIFY_PER_TASK:
            logger.info(f'Hit MAX_NOTIFY_PER_TASK ({MAX_NOTIFY_PER_TASK}) for task {task.id}')
            break
        
        prefs = user.get_job_alert_prefs()
        
        # Must be enabled
        if not prefs.get('enabled', False):
            continue
        
        # Category filter
        allowed_categories = prefs.get('categories', [])
        if allowed_categories and task.category not in allowed_categories:
            continue
        
        # Distance check
        radius_km = prefs.get('radius_km', 5)
        dist = distance(user.latitude, user.longitude, task.latitude, task.longitude)
        
        if dist > radius_km:
            continue
        
        # Format budget display
        budget_display = None
        if task.budget:
            budget_display = f'\u20ac{task.budget}'
        
        # Create notification
        try:
            notify_new_task_nearby(
                user_id=user.id,
                task_title=task.title,
                task_id=task.id,
                category_key=task.category,
                distance_km=round(dist, 1),
                budget=budget_display,
                location=task.location,
            )
            notified += 1
        except Exception as e:
            logger.error(f'Error creating job alert for user {user.id}: {e}')
            continue
    
    if notified > 0:
        try:
            db.session.commit()
            logger.info(f'Sent {notified} job alert(s) for task {task.id} "{task.title}"')
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error committing job alerts for task {task.id}: {e}')
            return 0
    
    return notified
