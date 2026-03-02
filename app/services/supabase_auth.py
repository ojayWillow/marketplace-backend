"""Supabase Auth admin operations.

Uses the Supabase service-role client to perform admin auth operations:
- Creating users (for phone auth flow)
- Generating session tokens
- Looking up users by email/phone

Note: These use the SERVICE_KEY (admin access). Never expose to frontend.
"""

import logging
from typing import Optional
from app.services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


def create_supabase_user(
    email: Optional[str] = None,
    phone: Optional[str] = None,
    password: Optional[str] = None,
    email_confirm: bool = True,
    phone_confirm: bool = True,
    user_metadata: Optional[dict] = None,
) -> dict:
    """Create a new user in Supabase Auth.

    Args:
        email: User email address
        phone: User phone number (E.164 format)
        password: User password (if None, generates a random one)
        email_confirm: Skip email verification
        phone_confirm: Skip phone verification
        user_metadata: Additional metadata to store

    Returns:
        Supabase user object dict

    Raises:
        Exception if creation fails
    """
    client = get_supabase_client()
    if not client:
        raise RuntimeError('Supabase client not available')

    import secrets
    if not password:
        password = secrets.token_urlsafe(32)

    attrs = {'password': password}
    if email:
        attrs['email'] = email
        attrs['email_confirm'] = email_confirm
    if phone:
        attrs['phone'] = phone
        attrs['phone_confirm'] = phone_confirm
    if user_metadata:
        attrs['user_metadata'] = user_metadata

    response = client.auth.admin.create_user(attrs)
    logger.info(f'Supabase user created: {response.user.id}')
    return response.user


def get_supabase_user_by_id(user_id: str):
    """Get a Supabase Auth user by their UUID."""
    client = get_supabase_client()
    if not client:
        raise RuntimeError('Supabase client not available')

    response = client.auth.admin.get_user_by_id(user_id)
    return response.user


def get_supabase_user_by_email(email: str):
    """Look up a Supabase Auth user by email.

    Returns None if not found.
    """
    client = get_supabase_client()
    if not client:
        raise RuntimeError('Supabase client not available')

    try:
        users = client.auth.admin.list_users()
        for user in users:
            if hasattr(user, 'email') and user.email == email:
                return user
    except Exception as e:
        logger.error(f'Error looking up user by email: {e}')
    return None


def get_supabase_user_by_phone(phone: str):
    """Look up a Supabase Auth user by phone number.

    Returns None if not found.
    """
    client = get_supabase_client()
    if not client:
        raise RuntimeError('Supabase client not available')

    try:
        users = client.auth.admin.list_users()
        for user in users:
            if hasattr(user, 'phone') and user.phone == phone:
                return user
    except Exception as e:
        logger.error(f'Error looking up user by phone: {e}')
    return None


def generate_link_for_user(
    user_id: str,
    link_type: str = 'magiclink',
) -> dict:
    """Generate an auth link for a user (e.g., magic link, recovery).

    Args:
        user_id: Supabase user UUID
        link_type: Type of link ('magiclink', 'recovery', 'invite')

    Returns:
        Link properties dict
    """
    client = get_supabase_client()
    if not client:
        raise RuntimeError('Supabase client not available')

    user = get_supabase_user_by_id(user_id)
    if not user:
        raise ValueError(f'User {user_id} not found')

    attrs = {'type': link_type, 'email': user.email}
    response = client.auth.admin.generate_link(attrs)
    return response


def delete_supabase_user(user_id: str) -> bool:
    """Delete a user from Supabase Auth."""
    client = get_supabase_client()
    if not client:
        raise RuntimeError('Supabase client not available')

    try:
        client.auth.admin.delete_user(user_id)
        logger.info(f'Supabase user deleted: {user_id}')
        return True
    except Exception as e:
        logger.error(f'Failed to delete Supabase user {user_id}: {e}')
        return False
