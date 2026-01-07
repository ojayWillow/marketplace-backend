from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
import os
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

def create_app(config_name='development'):
    app = Flask(__name__)
    
    # Configuration - prioritize environment variables for cloud deployment
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        os.environ.get('SQLALCHEMY_DATABASE_URI')
        or os.environ.get('DATABASE_URL')
        or ('sqlite:///:memory:' if config_name == 'testing' else 'sqlite:///marketplace.db')
    )
    
    if config_name == 'testing':
        app.config['TESTING'] = True
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # JWT Configuration
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')
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
             "http://localhost:5173",  # Vite default port
             "http://127.0.0.1:5173",  # Vite default port
             "https://marketplace-frontend-tau-seven.vercel.app",  # Production frontend
         ],
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization", "Accept"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"])
    
    # Health check route
    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'ok'}), 200
    
    # Register blueprints
    try:
        from app.routes import register_routes
        register_routes(app)
    except Exception as e:
        print(f"ERROR registering routes: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    return app
