from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()

def create_app(config_name='development'):
    app = Flask(__name__)
    
    # Configuration
    if config_name == 'development':
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
            'DATABASE_URL',
            'sqlite:///marketplace.db'
        )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db.init_app(app)
    CORS(app)
    
    # Health check route
    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'ok'}), 200
    
    # Register blueprints
    try:
        from app.routes import register_routes
        register_routes(app)
    except Exception as e:
        print(f"Warning: Could not register routes - {e}")
    
    return app
