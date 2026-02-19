"""File upload routes using Supabase Storage.

Supports uploading images for:
- User avatars (profile pictures)
- Task/job listing images
- Chat message attachments
"""

from flask import Blueprint, request, jsonify, current_app
import logging

from app.utils.auth import token_required
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

# Magic bytes for image format detection
# Maps magic byte signatures to (extension_set, mime_type)
IMAGE_SIGNATURES = [
    (b'\x89PNG\r\n\x1a\n', {'png'}, 'image/png'),
    (b'\xff\xd8\xff', {'jpg', 'jpeg'}, 'image/jpeg'),
    (b'GIF87a', {'gif'}, 'image/gif'),
    (b'GIF89a', {'gif'}, 'image/gif'),
    (b'RIFF', {'webp'}, 'image/webp'),  # WebP starts with RIFF....WEBP
]

# HEIC uses ftyp box — check bytes 4-12 for 'ftyp' marker
HEIC_FTYP_BRANDS = {b'heic', b'heix', b'mif1'}


def detect_image_type(file_data: bytes):
    """Detect image type from magic bytes.
    
    Returns:
        Tuple of (extension_set, mime_type) or (None, None) if unknown.
    """
    if len(file_data) < 12:
        return None, None
    
    for signature, exts, mime in IMAGE_SIGNATURES:
        if file_data[:len(signature)] == signature:
            # Extra check for WebP: bytes 8-12 must be 'WEBP'
            if 'webp' in exts:
                if file_data[8:12] != b'WEBP':
                    continue
            return exts, mime
    
    # HEIC/HEIF: bytes 4-8 should be 'ftyp', bytes 8-12 is the brand
    if file_data[4:8] == b'ftyp' and file_data[8:12].strip(b'\x00') in HEIC_FTYP_BRANDS:
        return {'heic'}, 'image/heic'
    
    return None, None


def allowed_image(filename):
    """Check if file has an allowed image extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in IMAGE_EXTENSIONS


def get_file_from_request(max_size: int):
    """Extract and validate file from request.
    
    Validates:
    1. File extension against whitelist
    2. File size against max_size
    3. Magic bytes match an actual image format
    4. Extension matches the detected image type
    
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
    
    # Validate magic bytes — don't trust the client's content_type
    detected_exts, detected_mime = detect_image_type(file_data)
    
    if detected_exts is None:
        return None, None, None, (jsonify({
            'error': 'File does not appear to be a valid image'
        }), 400)
    
    # Verify the file extension matches the actual content
    file_ext = file.filename.rsplit('.', 1)[1].lower()
    if file_ext not in detected_exts:
        return None, None, None, (jsonify({
            'error': f'File extension .{file_ext} does not match actual image format'
        }), 400)
    
    # Use the detected MIME type, not the client-provided one
    return file_data, file.filename, detected_mime, None


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
