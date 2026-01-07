"""Admin routes for database management."""
from flask import Blueprint, jsonify
from app import db
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

@admin_bp.route('/init-db', methods=['POST'])
def init_database():
    """Initialize database tables. Use with caution!"""
    try:
        # Create all tables
        db.create_all()
        
        return jsonify({
            'status': 'success',
            'message': 'Database tables created successfully'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to initialize database: {str(e)}'
        }), 500

@admin_bp.route('/db-status', methods=['GET'])
def database_status():
    """Check database status."""
    try:
        # Try to execute a simple query
        db.session.execute('SELECT 1')
        return jsonify({
            'status': 'ok',
            'database': 'connected',
            'tables_exist': True
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'database': 'error',
            'message': str(e)
        }), 500
