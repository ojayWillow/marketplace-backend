"""File upload routes using Supabase Storage.

Supports uploading images for:
- User avatars (profile pictures)
- Task/job listing images
- Chat message attachments
"""

from flask import Blueprint, request, jsonify, current_app
import jwt
from functools import wraps
import logging

from app.services.storage import (
    upload_avatar,
    upload_task_image,
    upload_chat_image,
    delete_file,
    is_storage_configured
)
from app import db

uploads_bp = Blueprint('uploads', __name__)
logger = logging.getLogger(__name__)

# Allowed file extensions
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'heic'}

# File size limits
AVATAR_MAX_SIZE = 5 * 1024 * 1024  # 5MB
TASK_IMAGE_MAX_SIZE = 10 * 1024 * 1024  # 10MB
CHAT_IMAGE_MAX_SIZE = 10 * 1024 * 1024  # 10MB


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            logger.warning('Upload attempt without auth token')
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            token = token.split(' ')[1] if ' ' in token else token
            data = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
            current_user_id = data['user_id']
        except jwt.ExpiredSignatureError:
            logger.warning('Upload attempt with expired token')
            return jsonify({'error': 'Token has expired'}), 401
        except Exception as e:
            logger.warning(f'Upload attempt with invalid token: {e}')
            return jsonify({'error': 'Token is invalid'}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorated


def allowed_image(filename):
    """Check if file is an allowed image type."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in IMAGE_EXTENSIONS


def get_file_from_request(max_size: int):
    """Extract and validate file from request.
    
    Returns:
        Tuple of (file_data, filename, content_type, error_response)
        If error: (None, None, None, error_response)
    """
    if 'file' not in request.files:
        return None, None, None, (jsonify({'error': 'No file provided'}), 400)
    
    file = request.files['file']
    
    if file.filename == '':
        return None, None, None, (jsonify({'error': 'No file selected'}), 400)
    
    if not allowed_image(file.filename):
        allowed_types = ', '.join(IMAGE_EXTENSIONS)
        return None, None, None, (jsonify({
            'error': f'File type not allowed. Allowed: {allowed_types}'
        }), 400)
    
    # Read file data
    file_data = file.read()
    
    # Check file size
    if len(file_data) > max_size:
        max_mb = max_size // (1024 * 1024)
        return None, None, None, (jsonify({
            'error': f'File too large. Maximum size: {max_mb}MB'
        }), 400)
    
    return file_data, file.filename, file.content_type, None


@uploads_bp.route('/status', methods=['GET'])
def storage_status():
    """Check if storage service is configured."""
    configured = is_storage_configured()
    return jsonify({
        'configured': configured,
        'provider': 'supabase' if configured else None
    }), 200


@uploads_bp.route('/avatar', methods=['POST'])
@token_required
def upload_user_avatar(current_user_id):
    """Upload a user avatar/profile picture.
    
    Updates the user's avatar_url in the database.
    """
    logger.info(f'Avatar upload request from user {current_user_id}')
    
    # Get and validate file
    file_data, filename, content_type, error = get_file_from_request(AVATAR_MAX_SIZE)
    if error:
        return error
    
    # Upload to Supabase
    url, error_msg = upload_avatar(file_data, filename, content_type)
    
    if error_msg:
        logger.error(f'Avatar upload failed: {error_msg}')
        return jsonify({'error': f'Upload failed: {error_msg}'}), 500
    
    # Update user's avatar_url in database
    try:
        from app.models import User
        user = User.query.get(current_user_id)
        if user:
            # Delete old avatar if exists
            if user.avatar_url and 'supabase' in user.avatar_url:
                delete_file('avatars', user.avatar_url)
            
            user.avatar_url = url
            db.session.commit()
            logger.info(f'Avatar updated for user {current_user_id}')
    except Exception as e:
        logger.error(f'Failed to update user avatar_url: {e}')
        # Don't fail the request - file was uploaded successfully
    
    return jsonify({
        'message': 'Avatar uploaded successfully',
        'url': url
    }), 201


@uploads_bp.route('/task-image', methods=['POST'])
@token_required
def upload_task_listing_image(current_user_id):
    """Upload an image for a task/job listing."""
    logger.info(f'Task image upload request from user {current_user_id}')
    
    # Get and validate file
    file_data, filename, content_type, error = get_file_from_request(TASK_IMAGE_MAX_SIZE)
    if error:
        return error
    
    # Upload to Supabase
    url, error_msg = upload_task_image(file_data, filename, content_type)
    
    if error_msg:
        logger.error(f'Task image upload failed: {error_msg}')
        return jsonify({'error': f'Upload failed: {error_msg}'}), 500
    
    return jsonify({
        'message': 'Image uploaded successfully',
        'url': url
    }), 201


@uploads_bp.route('/chat-image', methods=['POST'])
@token_required
def upload_chat_message_image(current_user_id):
    """Upload an image for a chat message."""
    logger.info(f'Chat image upload request from user {current_user_id}')
    
    # Get and validate file
    file_data, filename, content_type, error = get_file_from_request(CHAT_IMAGE_MAX_SIZE)
    if error:
        return error
    
    # Upload to Supabase
    url, error_msg = upload_chat_image(file_data, filename, content_type)
    
    if error_msg:
        logger.error(f'Chat image upload failed: {error_msg}')
        return jsonify({'error': f'Upload failed: {error_msg}'}), 500
    
    return jsonify({
        'message': 'Image uploaded successfully',
        'url': url
    }), 201


# Legacy endpoint for backwards compatibility
@uploads_bp.route('', methods=['POST'])
@token_required
def upload_file_legacy(current_user_id):
    """Legacy upload endpoint - uploads to task-images bucket by default."""
    logger.info(f'Legacy upload request from user {current_user_id}')
    
    # Get and validate file
    file_data, filename, content_type, error = get_file_from_request(TASK_IMAGE_MAX_SIZE)
    if error:
        return error
    
    # Upload to task-images bucket
    url, error_msg = upload_task_image(file_data, filename, content_type)
    
    if error_msg:
        logger.error(f'Legacy upload failed: {error_msg}')
        return jsonify({'error': f'Upload failed: {error_msg}'}), 500
    
    return jsonify({
        'message': 'File uploaded successfully',
        'url': url,
        'filename': url.split('/')[-1] if url else None,
        'category': 'image',
        'size': len(file_data)
    }), 201
