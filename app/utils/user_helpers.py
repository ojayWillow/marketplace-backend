"""Shared user-related helper functions.

This module provides utility functions for working with User objects
that are commonly needed across multiple route files.
"""


def get_display_name(user):
    """
    Get the best display name for a user.
    
    Priority:
    1. first_name (if available)
    2. username (if available)
    3. 'Someone' (fallback)
    
    Args:
        user: User model instance or None
        
    Returns:
        str: The best available display name
        
    Usage:
        user = User.query.get(user_id)
        name = get_display_name(user)
    """
    if not user:
        return 'Someone'
    if user.first_name:
        return user.first_name
    return user.username or 'Someone'


def send_push_safe(push_func, *args, **kwargs):
    """
    Safely send a push notification, handling errors gracefully.
    
    Push notification failures should never cause the main request to fail.
    This wrapper catches any exceptions and logs them without re-raising.
    
    Args:
        push_func: The push notification function to call
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Usage:
        send_push_safe(
            notify_new_message,
            recipient_id=user_id,
            sender_name='John',
            message_preview='Hello!'
        )
    """
    try:
        push_func(*args, **kwargs)
    except Exception as e:
        print(f"Push notification error (non-critical): {e}")
