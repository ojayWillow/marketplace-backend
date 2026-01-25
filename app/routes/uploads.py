"""File upload routes for images, videos, documents, and audio."""

from flask import Blueprint, request, jsonify, current_app, send_from_directory
import os
import uuid
from werkzeug.utils import secure_filename
import jwt
from functools import wraps
import logging

uploads_bp = Blueprint('uploads', __name__)
logger = logging.getLogger(__name__)

# Use the same key as Flask-JWT-Extended configuration
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')

# Allowed file extensions by category
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'heic'}
VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm'}
AUDIO_EXTENSIONS = {'mp3', 'wav', 'm4a', 'aac', 'ogg'}
DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'xls', 'xlsx'}

ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | DOCUMENT_EXTENSIONS

# File size limits by category
IMAGE_MAX_SIZE = 5 * 1024 * 1024  # 5MB
VIDEO_MAX_SIZE = 50 * 1024 * 1024  # 50MB
AUDIO_MAX_SIZE = 10 * 1024 * 1024  # 10MB
DOCUMENT_MAX_SIZE = 10 * 1024 * 1024  # 10MB

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            logger.warning('Upload attempt without auth token')
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            token = token.split(' ')[1]
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            current_user_id = data['user_id']
        except jwt.ExpiredSignatureError:
            logger.warning('Upload attempt with expired token')
            return jsonify({'error': 'Token has expired'}), 401
        except Exception as e:
            logger.warning(f'Upload attempt with invalid token: {e}')
            return jsonify({'error': 'Token is invalid'}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorated

def get_file_category(extension):
    """Determine file category from extension."""
    extension = extension.lower()
    if extension in IMAGE_EXTENSIONS:
        return 'image'
    elif extension in VIDEO_EXTENSIONS:
        return 'video'
    elif extension in AUDIO_EXTENSIONS:
        return 'audio'
    elif extension in DOCUMENT_EXTENSIONS:
        return 'document'
    return None

def get_max_file_size(category):
    """Get maximum file size for category."""
    sizes = {
        'image': IMAGE_MAX_SIZE,
        'video': VIDEO_MAX_SIZE,
        'audio': AUDIO_MAX_SIZE,
        'document': DOCUMENT_MAX_SIZE
    }
    return sizes.get(category, IMAGE_MAX_SIZE)

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_upload_folder():
    """Get or create uploads folder."""
    upload_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    return upload_folder

@uploads_bp.route('', methods=['POST'])
@token_required
def upload_file(current_user_id):
    """Upload a file (image, video, audio, or document)."""
    try:
        # Log request details for debugging
        logger.info(f'Upload request from user {current_user_id}')
        logger.info(f'Content-Type: {request.content_type}')
        logger.info(f'Files in request: {list(request.files.keys())}')
        logger.info(f'Form data: {list(request.form.keys())}')
        
        # Check if file is in request
        if 'file' not in request.files:
            logger.error(f'No file field in request. Available fields: {list(request.files.keys())}')
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Check if file is selected
        if file.filename == '':
            logger.error('File field is empty')
            return jsonify({'error': 'No file selected'}), 400
        
        logger.info(f'Received file: {file.filename}, content_type: {file.content_type}')
        
        # Check file extension
        if not allowed_file(file.filename):
            logger.error(f'File type not allowed: {file.filename}')
            return jsonify({'error': f'File type not allowed. Allowed types: images, videos, audio, documents'}), 400
        
        # Get file category and max size
        extension = file.filename.rsplit('.', 1)[1].lower()
        category = get_file_category(extension)
        max_size = get_max_file_size(category)
        
        # Check file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Seek back to start
        
        logger.info(f'File size: {file_size} bytes ({file_size / (1024*1024):.2f}MB), category: {category}')
        
        if file_size > max_size:
            logger.error(f'File too large: {file_size} bytes (max: {max_size})')
            return jsonify({'error': f'File too large. Maximum size for {category}: {max_size // (1024*1024)}MB'}), 400
        
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{extension}"
        
        # Save file
        upload_folder = get_upload_folder()
        filepath = os.path.join(upload_folder, unique_filename)
        file.save(filepath)
        
        logger.info(f'File saved successfully: {unique_filename}')
        
        # Return URL and metadata
        file_url = f"/api/uploads/{unique_filename}"
        
        return jsonify({
            'message': 'File uploaded successfully',
            'url': file_url,
            'filename': unique_filename,
            'category': category,
            'size': file_size
        }), 201
        
    except Exception as e:
        logger.error(f'Upload error: {str(e)}', exc_info=True)
        return jsonify({'error': str(e)}), 500

@uploads_bp.route('/<filename>', methods=['GET'])
def get_file(filename):
    """Serve an uploaded file."""
    try:
        upload_folder = get_upload_folder()
        return send_from_directory(upload_folder, filename)
    except Exception as e:
        logger.error(f'File retrieval error: {str(e)}')
        return jsonify({'error': 'File not found'}), 404

@uploads_bp.route('/<filename>', methods=['DELETE'])
@token_required
def delete_file(current_user_id, filename):
    """Delete an uploaded file."""
    try:
        upload_folder = get_upload_folder()
        filepath = os.path.join(upload_folder, filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f'File deleted by user {current_user_id}: {filename}')
            return jsonify({'message': 'File deleted successfully'}), 200
        else:
            logger.warning(f'Delete attempt for non-existent file: {filename}')
            return jsonify({'error': 'File not found'}), 404
            
    except Exception as e:
        logger.error(f'Delete error: {str(e)}', exc_info=True)
        return jsonify({'error': str(e)}), 500
