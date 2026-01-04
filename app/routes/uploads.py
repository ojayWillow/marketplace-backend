"""Image upload routes for listings and profiles."""

from flask import Blueprint, request, jsonify, current_app, send_from_directory, make_response
import os
import uuid
from werkzeug.utils import secure_filename
import jwt
from functools import wraps

uploads_bp = Blueprint('uploads', __name__)

# Use the same key as Flask-JWT-Extended configuration
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            token = token.split(' ')[1]
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            current_user_id = data['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except Exception as e:
            return jsonify({'error': 'Token is invalid'}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorated

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

@uploads_bp.route('', methods=['POST', 'OPTIONS'])
def upload_file_route():
    """Upload an image file."""
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response, 200
    
    # Require token for POST
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'error': 'Token is missing'}), 401
    
    try:
        token_value = token.split(' ')[1]
        data = jwt.decode(token_value, SECRET_KEY, algorithms=['HS256'])
        current_user_id = data['user_id']
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token has expired'}), 401
    except Exception as e:
        return jsonify({'error': 'Token is invalid', 'details': str(e)}), 401
    
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Check if file is selected
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check file extension
        if not allowed_file(file.filename):
            return jsonify({'error': f'File type not allowed. Allowed types: {ALLOWED_EXTENSIONS}'}), 400
        
        # Check file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Seek back to start
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({'error': f'File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB'}), 400
        
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{extension}"
        
        # Save file
        upload_folder = get_upload_folder()
        filepath = os.path.join(upload_folder, unique_filename)
        file.save(filepath)
        
        # Return URL
        # In production, this would be a CDN URL
        file_url = f"/api/uploads/{unique_filename}"
        
        return jsonify({
            'message': 'File uploaded successfully',
            'url': file_url,
            'filename': unique_filename
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@uploads_bp.route('/<filename>', methods=['GET'])
def get_file(filename):
    """Serve an uploaded file."""
    try:
        upload_folder = get_upload_folder()
        return send_from_directory(upload_folder, filename)
    except Exception as e:
        return jsonify({'error': 'File not found'}), 404

@uploads_bp.route('/<filename>', methods=['DELETE', 'OPTIONS'])
def delete_file_route(filename):
    """Delete an uploaded file."""
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response, 200
    
    # Require token for DELETE
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'error': 'Token is missing'}), 401
    
    try:
        token_value = token.split(' ')[1]
        data = jwt.decode(token_value, SECRET_KEY, algorithms=['HS256'])
        current_user_id = data['user_id']
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token has expired'}), 401
    except Exception as e:
        return jsonify({'error': 'Token is invalid'}), 401
    
    try:
        upload_folder = get_upload_folder()
        filepath = os.path.join(upload_folder, filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({'message': 'File deleted successfully'}), 200
        else:
            return jsonify({'error': 'File not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
