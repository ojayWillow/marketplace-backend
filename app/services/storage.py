"""Supabase Storage Service for file uploads.

This service handles all file uploads to Supabase Storage buckets.
Buckets:
- avatars: User profile pictures (public)
- task-images: Task/job listing images (public)
- chat-images: Chat message attachments (authenticated)
"""

import os
import logging
from uuid import uuid4
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Supabase client (lazy initialization)
_supabase_client = None

def get_supabase_client():
    """Get or create Supabase client (lazy initialization)."""
    global _supabase_client
    
    if _supabase_client is None:
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_KEY')
        
        if not url or not key:
            logger.warning('Supabase credentials not configured. Storage will not work.')
            return None
        
        try:
            from supabase import create_client
            _supabase_client = create_client(url, key)
            logger.info('Supabase client initialized successfully')
        except Exception as e:
            logger.error(f'Failed to initialize Supabase client: {e}')
            return None
    
    return _supabase_client


def is_storage_configured() -> bool:
    """Check if Supabase storage is properly configured."""
    return get_supabase_client() is not None


def upload_file(
    bucket: str,
    file_data: bytes,
    file_name: str,
    content_type: str = 'image/jpeg'
) -> Tuple[Optional[str], Optional[str]]:
    """Upload a file to Supabase Storage.
    
    Args:
        bucket: Storage bucket name ('avatars', 'task-images', 'chat-images')
        file_data: Raw file bytes
        file_name: Original filename (used to get extension)
        content_type: MIME type of the file
    
    Returns:
        Tuple of (public_url, error_message)
        If successful: (url, None)
        If failed: (None, error_message)
    """
    client = get_supabase_client()
    
    if client is None:
        return None, 'Storage service not configured'
    
    try:
        # Generate unique filename
        ext = file_name.rsplit('.', 1)[-1].lower() if '.' in file_name else 'jpg'
        unique_name = f"{uuid4().hex}.{ext}"
        
        logger.info(f'Uploading file to {bucket}/{unique_name} ({content_type})')
        
        # Upload to Supabase
        result = client.storage.from_(bucket).upload(
            path=unique_name,
            file=file_data,
            file_options={"content-type": content_type}
        )
        
        # Get public URL
        public_url = client.storage.from_(bucket).get_public_url(unique_name)
        
        logger.info(f'File uploaded successfully: {public_url}')
        return public_url, None
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f'Upload failed: {error_msg}')
        return None, error_msg


def delete_file(bucket: str, file_url: str) -> Tuple[bool, Optional[str]]:
    """Delete a file from Supabase Storage.
    
    Args:
        bucket: Storage bucket name
        file_url: Full public URL or just the filename
    
    Returns:
        Tuple of (success, error_message)
    """
    client = get_supabase_client()
    
    if client is None:
        return False, 'Storage service not configured'
    
    try:
        # Extract filename from URL if full URL provided
        if '/' in file_url:
            file_name = file_url.split('/')[-1]
        else:
            file_name = file_url
        
        logger.info(f'Deleting file from {bucket}/{file_name}')
        
        client.storage.from_(bucket).remove([file_name])
        
        logger.info(f'File deleted successfully: {file_name}')
        return True, None
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f'Delete failed: {error_msg}')
        return False, error_msg


def upload_avatar(file_data: bytes, file_name: str, content_type: str = 'image/jpeg') -> Tuple[Optional[str], Optional[str]]:
    """Upload a user avatar image."""
    return upload_file('avatars', file_data, file_name, content_type)


def upload_task_image(file_data: bytes, file_name: str, content_type: str = 'image/jpeg') -> Tuple[Optional[str], Optional[str]]:
    """Upload a task/job listing image."""
    return upload_file('task-images', file_data, file_name, content_type)


def upload_chat_image(file_data: bytes, file_name: str, content_type: str = 'image/jpeg') -> Tuple[Optional[str], Optional[str]]:
    """Upload a chat message image."""
    return upload_file('chat-images', file_data, file_name, content_type)
