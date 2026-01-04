from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
import os
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
jwt = JWTManager()

def create_app(config_name='development'):
    app = Flask(__name__)
    
    # Configuration
    if config_name == 'development':
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///marketplace.db'
    elif config_name == 'testing':
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['TESTING'] = True
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # JWT Configuration
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    
    # Simple permissive CORS for development - allow all origins
    CORS(app, supports_credentials=True)
    
    # Health check route
    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'ok'}), 200
    
    # Add CORS headers to all responses (backup)
    @app.after_request
    def after_request(response):
        origin = response.headers.get('Origin', '*')
        response.headers.add('Access-Control-Allow-Origin', origin if origin else '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, Accept')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS, PATCH')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response
    
    # Register blueprints
    try:
        from app.routes import register_routes
        register_routes(app)
    except Exception as e:
        print(f"ERROR registering routes: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    return app
