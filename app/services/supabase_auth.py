"""Supabase Auth admin operations.

Uses the Supabase service-role client to perform admin auth operations:
- Creating users (for phone auth flow)
- Generating session tokens
- Looking up users by email/phone

Note: These use the SERVICE_KEY (admin access). Never expose to frontend.
"""

import logging
import os
import secrets
import threading
import time
from typing import Optional, Tuple
import requests as http_requests
from app.services.supabase_client import get_supabase_client, get_supabase_anon_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-user session cache — prevents parallel sign_in_with_password calls that
# exhaust Supabase refresh token rotation and cause "Already Used" errors.
# ---------------------------------------------------------------------------
_session_cache: dict = {}          # user_key -> {"session": dict, "expires_at": float}
_session_cache_lock = threading.Lock()
_SESSION_BUFFER_SECS = 120         # Refresh early if <2 min left


def _cached_session(cache_key: str):
    with _session_cache_lock:
        entry = _session_cache.get(cache_key)
        if entry and entry["expires_at"] > time.time() + _SESSION_BUFFER_SECS:
            logger.debug(f"Session cache HIT for key {cache_key}")
            return entry["session"]
    return None


def _store_session(cache_key: str, session: dict):
    expires_at = session.get("expires_at") or (time.time() + session.get("expires_in", 3600))
    with _session_cache_lock:
        _session_cache[cache_key] = {"session": session, "expires_at": float(expires_at)}


def create_supabase_user(
    email: Optional[str] = None,
    phone: Optional[str] = None,
    password: Optional[str] = None,
    email_confirm: bool = True,
    phone_confirm: bool = True,
    user_metadata: Optional[dict] = None,
) -> Tuple:
    """Create a new user in Supabase Auth.

    If the phone or email is already registered, returns the existing Supabase
    user instead of raising — avoids 422 loops when the same user logs in again.

    Args:
        email: User email address
        phone: User phone number (E.164 format)
        password: User password (if None, generates a random one)
        email_confirm: Skip email verification
        phone_confirm: Skip phone verification
        user_metadata: Additional metadata to store

    Returns:
        Tuple of (supabase_user, password_used)
        password_used is needed for subsequent sign_in_with_password

    Raises:
        Exception if creation fails for an unexpected reason
    """
    client = get_supabase_client()
    if not client:
        raise RuntimeError('Supabase client not available')

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

    try:
        response = client.auth.admin.create_user(attrs)
        logger.info(f'Supabase user created: {response.user.id}')
        return response.user, password

    except Exception as e:
        error_msg = str(e).lower()
        if 'already registered' in error_msg or 'already been registered' in error_msg:
            logger.info('Supabase user already exists — looking up by phone/email')
            existing = None
            if phone:
                existing = get_supabase_user_by_phone(phone)
            if not existing and email and not email.endswith('.kolab.local'):
                existing = get_supabase_user_by_email(email)
            if existing:
                # Return None for password — caller must reset it via generate_supabase_session
                return existing, None
            logger.error('Could not find existing Supabase user after duplicate error')
        raise


def generate_supabase_session(
    email: Optional[str] = None,
    phone: Optional[str] = None,
    password: Optional[str] = None,
    supabase_user_id: Optional[str] = None,
) -> Optional[dict]:
    """Generate a Supabase session (access_token + refresh_token) for a user.

    Uses a per-user in-memory cache to prevent parallel sign_in_with_password
    calls that cause "Invalid Refresh Token: Already Used" errors.

    Args:
        email: User email (used for sign-in — preferred)
        phone: User phone (fallback only if no email at all)
        password: Known password for the user
        supabase_user_id: Supabase user UUID (needed to reset password if unknown)

    Returns:
        Dict with access_token, refresh_token, expires_in, expires_at
        or None if session generation fails
    """
    cache_key = supabase_user_id or email or phone or 'unknown'

    cached = _cached_session(cache_key)
    if cached:
        return cached

    anon_client = get_supabase_anon_client()
    if not anon_client:
        logger.warning('Anon client not available — cannot generate Supabase session')
        return None

    if not password:
        if not supabase_user_id:
            logger.error('Cannot generate session: no password and no supabase_user_id')
            return None

        admin_client = get_supabase_client()
        if not admin_client:
            logger.error('Admin client not available for password reset')
            return None

        password = secrets.token_urlsafe(32)
        try:
            update_attrs = {'password': password}
            if email:
                update_attrs['email'] = email
                update_attrs['email_confirm'] = True

            admin_client.auth.admin.update_user_by_id(
                supabase_user_id,
                update_attrs
            )
            logger.debug(f'Reset password for Supabase user {supabase_user_id}')
        except Exception as e:
            logger.error(f'Failed to reset password for session generation: {e}')
            return None

    try:
        credentials = {'password': password}

        if email:
            credentials['email'] = email
        elif phone:
            credentials['phone'] = phone
        else:
            logger.error('No email or phone available for sign-in')
            return None

        response = anon_client.auth.sign_in_with_password(credentials)

        if response.session:
            logger.info('Supabase session generated successfully')
            session_data = {
                'access_token': response.session.access_token,
                'refresh_token': response.session.refresh_token,
                'expires_in': response.session.expires_in,
                'expires_at': response.session.expires_at,
            }
            _store_session(cache_key, session_data)
            return session_data
        else:
            logger.error('sign_in_with_password returned no session')
            return None

    except Exception as e:
        logger.error(f'Failed to generate Supabase session: {e}')
        return None


def get_supabase_user_by_id(user_id: str):
    """Get a Supabase Auth user by their UUID."""
    client = get_supabase_client()
    if not client:
        raise RuntimeError('Supabase client not available')

    response = client.auth.admin.get_user_by_id(user_id)
    return response.user


def _gotrue_admin_list_users_filtered(filter_value: str) -> Optional[list]:
    """Call GoTrue admin API with server-side filter.

    The GoTrue /admin/users endpoint supports a ?filter= parameter that
    does a LIKE match on email, phone, and user metadata. This avoids
    fetching all users just to find one.

    Returns a list of user dicts, or None if the request fails.
    """
    supabase_url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    if not supabase_url or not service_key:
        return None

    try:
        url = f'{supabase_url.rstrip("/")}/auth/v1/admin/users'
        resp = http_requests.get(
            url,
            params={'filter': filter_value, 'page': 1, 'per_page': 50},
            headers={
                'Authorization': f'Bearer {service_key}',
                'apikey': service_key,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                return data.get('users', [])
            if isinstance(data, list):
                return data
        logger.warning(f'GoTrue filter request returned status {resp.status_code}')
        return None
    except Exception as e:
        logger.warning(f'GoTrue filter request failed: {e}')
        return None


def _get_phone_from_user(user) -> Optional[str]:
    """Safely extract phone from a user object or dict."""
    if isinstance(user, dict):
        return user.get('phone')
    return getattr(user, 'phone', None)


def get_supabase_user_by_email(email: str):
    """Look up a Supabase Auth user by email.

    Uses the GoTrue admin API ?filter= parameter for server-side filtering.
    Falls back to iterating all users if the filtered request fails.

    Returns None if not found.
    """
    filtered_users = _gotrue_admin_list_users_filtered(email)
    if filtered_users is not None:
        for user in filtered_users:
            user_email = user.get('email') if isinstance(user, dict) else getattr(user, 'email', None)
            if user_email == email:
                return user
        return None

    client = get_supabase_client()
    if not client:
        raise RuntimeError('Supabase client not available')

    try:
        logger.info('Falling back to list_users() for email lookup')
        users = client.auth.admin.list_users()
        for user in users:
            if hasattr(user, 'email') and user.email == email:
                return user
    except Exception as e:
        logger.error(f'Error looking up user by email: {e}')
    return None


def get_supabase_user_by_phone(phone: str):
    """Look up a Supabase Auth user by phone number.

    GoTrue stores phone numbers in E.164 format (e.g. +37125953807).
    The ?filter= parameter does a text LIKE match — the '+' character can
    cause the filter to return zero results. We therefore try two filter
    values: the full E.164 string AND the digits-only variant.

    Falls back to a full list_users() scan if both filtered requests fail
    to find a match.

    Returns None if not found.
    """
    # Normalise: ensure E.164 form and digits-only form for comparison
    phone_e164 = phone if phone.startswith('+') else f'+{phone}'
    phone_digits = phone_e164.lstrip('+')

    # Try filtered requests with both variants
    for filter_val in (phone_e164, phone_digits):
        filtered_users = _gotrue_admin_list_users_filtered(filter_val)
        if filtered_users is not None:
            for user in filtered_users:
                stored = _get_phone_from_user(user)
                if stored and (stored == phone_e164 or stored.lstrip('+') == phone_digits):
                    logger.info(f'Found Supabase user by phone filter ({filter_val})')
                    return user

    # Both filtered requests came back empty — do a full scan as last resort
    logger.info('Phone filter returned no match, falling back to list_users() scan')
    client = get_supabase_client()
    if not client:
        raise RuntimeError('Supabase client not available')

    try:
        users = client.auth.admin.list_users()
        for user in users:
            stored = _get_phone_from_user(user)
            if stored and (stored == phone_e164 or stored.lstrip('+') == phone_digits):
                logger.info(f'Found Supabase user by phone in list_users scan')
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
