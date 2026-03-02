"""Shared Supabase clients.

Provides two clients:
1. Service-role client (admin) — for user management, storage, etc.
2. Anon client — for generating user sessions via sign_in_with_password

The service-role client has admin privileges and should never be exposed.
The anon client uses the public anon key and is safe for session operations.
"""

import os
import logging

logger = logging.getLogger(__name__)

_supabase_client = None
_supabase_anon_client = None


def get_supabase_client():
    """Get or create Supabase admin client (service role key)."""
    global _supabase_client

    if _supabase_client is None:
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_KEY')

        if not url or not key:
            logger.warning('Supabase credentials not configured.')
            return None

        try:
            from supabase import create_client
            _supabase_client = create_client(url, key)
            logger.info('Supabase admin client initialized successfully')
        except Exception as e:
            logger.error(f'Failed to initialize Supabase admin client: {e}')
            return None

    return _supabase_client


def get_supabase_anon_client():
    """Get or create Supabase anon client (public anon key).

    Used for operations that need a user session, such as
    sign_in_with_password() to generate access/refresh tokens.

    The anon key is the public key from Supabase Dashboard > Settings > API.
    """
    global _supabase_anon_client

    if _supabase_anon_client is None:
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_ANON_KEY')

        if not url or not key:
            logger.warning('SUPABASE_ANON_KEY not configured — session generation unavailable.')
            return None

        try:
            from supabase import create_client
            _supabase_anon_client = create_client(url, key)
            logger.info('Supabase anon client initialized successfully')
        except Exception as e:
            logger.error(f'Failed to initialize Supabase anon client: {e}')
            return None

    return _supabase_anon_client


def get_supabase_jwt_secret() -> str:
    """Get the Supabase JWT secret for token verification.

    This is the JWT secret from Supabase Dashboard > Settings > API.
    Used by auth decorators to decode Supabase-issued JWTs.
    """
    secret = os.getenv('SUPABASE_JWT_SECRET')
    if not secret:
        logger.error('SUPABASE_JWT_SECRET not configured!')
        raise ValueError('SUPABASE_JWT_SECRET environment variable is required')
    return secret
