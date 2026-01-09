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

@admin_bp.route('/migrate-db', methods=['GET', 'POST'])
def migrate_database():
    """Add missing columns to existing tables. Safe to run multiple times."""
    results = []
    
    try:
        # List of column migrations: (table, column, type, default)
        column_migrations = [
            # User table - last_seen for online status
            ('users', 'last_seen', 'TIMESTAMP', None),
            
            # Offerings table - boost functionality
            ('offerings', 'is_boosted', 'BOOLEAN', 'FALSE'),
            ('offerings', 'boost_expires_at', 'TIMESTAMP', None),
        ]
        
        for table, column, col_type, default in column_migrations:
            try:
                # Check if column exists
                check_sql = f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{table}' AND column_name = '{column}'
                """
                result = db.session.execute(db.text(check_sql)).fetchone()
                
                if result is None:
                    # Column doesn't exist, add it
                    if default is not None:
                        alter_sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type} DEFAULT {default}"
                    else:
                        alter_sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                    
                    db.session.execute(db.text(alter_sql))
                    db.session.commit()
                    results.append(f"Added {table}.{column}")
                else:
                    results.append(f"Column {table}.{column} already exists")
                    
            except Exception as e:
                results.append(f"Error with {table}.{column}: {str(e)}")
                db.session.rollback()
        
        # Create translation_cache table if it doesn't exist
        try:
            check_table_sql = """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name = 'translation_cache'
            """
            table_exists = db.session.execute(db.text(check_table_sql)).fetchone()
            
            if table_exists is None:
                create_table_sql = """
                    CREATE TABLE translation_cache (
                        id SERIAL PRIMARY KEY,
                        text_hash VARCHAR(64) NOT NULL,
                        source_lang VARCHAR(5) NOT NULL,
                        target_lang VARCHAR(5) NOT NULL,
                        original_text TEXT NOT NULL,
                        translated_text TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(text_hash, target_lang)
                    )
                """
                db.session.execute(db.text(create_table_sql))
                db.session.commit()
                results.append("Created translation_cache table")
            else:
                results.append("Table translation_cache already exists")
        except Exception as e:
            results.append(f"Error with translation_cache table: {str(e)}")
            db.session.rollback()
        
        return jsonify({
            'status': 'success',
            'message': 'Migration completed!',
            'details': results
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Migration failed: {str(e)}',
            'details': results
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
