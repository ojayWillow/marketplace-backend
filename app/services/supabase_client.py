"""Shared Supabase client.

Single source of truth for the Supabase client instance.
Used by storage, auth, and any other service that needs Supabase.
"""

import os
import logging

logger = logging.getLogger(__name__)

_supabase_client = None


def get_supabase_client():
    """Get or create Supabase client (lazy initialization)."""
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
            logger.info('Supabase client initialized successfully')
        except Exception as e:
            logger.error(f'Failed to initialize Supabase client: {e}')
            return None

    return _supabase_client


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
