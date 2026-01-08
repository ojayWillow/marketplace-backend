"""Admin routes for database management."""
from flask import Blueprint, jsonify, request
from app import db
import os

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/init-db', methods=['GET', 'POST'])
def init_database():
    """Initialize database tables. Use with caution!"""
    try:
        # Create all tables
        db.create_all()
        
        return jsonify({
            'status': 'success',
            'message': 'Database tables created successfully! You can now use the app.'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to initialize database: {str(e)}'
        }), 500

@admin_bp.route('/db-status', methods=['GET'])
def database_status():
    """Check database connection status."""
    try:
        # Try to execute a simple query
        db.session.execute(db.text('SELECT 1'))
        return jsonify({
            'status': 'ok',
            'database': 'connected'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'database': 'disconnected',
            'message': str(e)
        }), 500
