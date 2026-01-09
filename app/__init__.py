from flask import Flask, jsonify, request, g
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, get_jwt_identity, verify_jwt_in_request
from flask_cors import CORS
import os
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

def create_app(config_name=None):
    app = Flask(__name__)
    
    # Determine environment
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    # Get database URL from environment
    database_url = (
        os.environ.get('DATABASE_URL') 
        or os.environ.get('SQLALCHEMY_DATABASE_URI')
    )
    
    # Handle Render's postgres:// vs postgresql:// issue
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    # Configuration based on environment
    if config_name == 'testing':
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['TESTING'] = True
    elif database_url:
        # Production/Render - use the environment database URL
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        # Local development fallback
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///marketplace.db'
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # JWT Configuration
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-here')
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    
    # CORS configuration - allow frontend origins
    CORS(app, 
         origins=[
             "http://localhost:3000",
             "http://127.0.0.1:3000",
             "http://localhost:5173",
             "http://127.0.0.1:5173",
             "https://marketplace-frontend-tau-seven.vercel.app",
             os.environ.get('FRONTEND_URL', ''),  # Allow custom frontend URL
         ],
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization", "Accept"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"])
    
    # Middleware to update user's last_seen on authenticated requests
    @app.before_request
    def update_last_seen():
        """Update user's last_seen timestamp on every authenticated request."""
        # Skip for OPTIONS requests (CORS preflight)
        if request.method == 'OPTIONS':
            return
        
        # Skip for public endpoints
        public_paths = ['/health', '/api/auth/login', '/api/auth/register']
        if any(request.path.startswith(path) for path in public_paths):
            return
        
        # Try to get authenticated user and update last_seen
        try:
            verify_jwt_in_request(optional=True)
            user_id = get_jwt_identity()
            if user_id:
                from app.models import User
                user = User.query.get(user_id)
                if user:
                    user.update_last_seen()
                    db.session.commit()
        except Exception:
            # Silently ignore errors - don't break the request
            pass
    
    # Health check route with debug info
    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({
            'status': 'ok',
            'environment': config_name,
            'database_configured': bool(app.config.get('SQLALCHEMY_DATABASE_URI')),
        }), 200
    
    # Register blueprints
    try:
        from app.routes import register_routes
        register_routes(app)
    except Exception as e:
        print(f"ERROR registering routes: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    return app
