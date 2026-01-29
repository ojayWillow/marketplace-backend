"""Redis client for shared state management across workers."""

import os
import redis
import logging

logger = logging.getLogger(__name__)

# Redis connection (lazy initialization)
_redis_client = None

def get_redis():
    """Get or create Redis connection."""
    global _redis_client
    
    if _redis_client is not None:
        return _redis_client
    
    redis_url = os.environ.get('REDIS_URL')
    
    if not redis_url:
        logger.warning("REDIS_URL not set - online status tracking will be limited")
        return None
    
    try:
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        # Test connection
        _redis_client.ping()
        logger.info("Redis connected successfully")
        return _redis_client
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return None


# Online status keys
ONLINE_PREFIX = "user:online:"
SOCKET_PREFIX = "socket:user:"
ONLINE_TTL = 120  # 2 minutes - refreshed on each activity


def set_user_online(user_id: int, socket_id: str) -> bool:
    """Mark user as online with socket ID."""
    r = get_redis()
    if not r:
        return False
    
    try:
        pipe = r.pipeline()
        # Store online status with TTL
        pipe.setex(f"{ONLINE_PREFIX}{user_id}", ONLINE_TTL, "1")
        # Map socket to user
        pipe.setex(f"{SOCKET_PREFIX}{socket_id}", ONLINE_TTL, str(user_id))
        pipe.execute()
        return True
    except Exception as e:
        logger.error(f"Redis set_user_online error: {e}")
        return False


def set_user_offline(user_id: int = None, socket_id: str = None) -> int:
    """Mark user as offline. Returns user_id if found."""
    r = get_redis()
    if not r:
        return None
    
    try:
        # If we have socket_id, look up user_id
        if socket_id and not user_id:
            user_id_str = r.get(f"{SOCKET_PREFIX}{socket_id}")
            if user_id_str:
                user_id = int(user_id_str)
        
        if user_id:
            r.delete(f"{ONLINE_PREFIX}{user_id}")
        
        if socket_id:
            r.delete(f"{SOCKET_PREFIX}{socket_id}")
        
        return user_id
    except Exception as e:
        logger.error(f"Redis set_user_offline error: {e}")
        return None


def is_user_online(user_id: int) -> bool:
    """Check if user is online."""
    r = get_redis()
    if not r:
        return False
    
    try:
        return r.exists(f"{ONLINE_PREFIX}{user_id}") > 0
    except Exception as e:
        logger.error(f"Redis is_user_online error: {e}")
        return False


def refresh_user_online(user_id: int) -> bool:
    """Refresh user's online TTL (call on activity)."""
    r = get_redis()
    if not r:
        return False
    
    try:
        key = f"{ONLINE_PREFIX}{user_id}"
        if r.exists(key):
            r.expire(key, ONLINE_TTL)
            return True
        return False
    except Exception as e:
        logger.error(f"Redis refresh_user_online error: {e}")
        return False


def get_online_users() -> list:
    """Get list of all online user IDs."""
    r = get_redis()
    if not r:
        return []
    
    try:
        keys = r.keys(f"{ONLINE_PREFIX}*")
        return [int(k.replace(ONLINE_PREFIX, "")) for k in keys]
    except Exception as e:
        logger.error(f"Redis get_online_users error: {e}")
        return []
