"""Admin routes for database management."""
from flask import Blueprint, jsonify, request
from app import db
from app.models import User
import os

admin_bp = Blueprint('admin', __name__)

# Simple admin secret for protected operations
# In production, use environment variable: ADMIN_SECRET
ADMIN_SECRET = os.environ.get('ADMIN_SECRET', 'tirgus-admin-2026')


def check_admin_secret():
    """Check if request has valid admin secret."""
    secret = request.headers.get('X-Admin-Secret') or request.args.get('secret')
    return secret == ADMIN_SECRET


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


# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================

@admin_bp.route('/users/delete-all', methods=['DELETE', 'POST'])
def delete_all_users():
    """Delete ALL users from the database.
    
    ⚠️  CAUTION: This will permanently delete all user accounts!
    
    Requires admin secret in header or query param.
    
    Example:
        DELETE /api/admin/users/delete-all?secret=tirgus-admin-2026
        
        or with header:
        DELETE /api/admin/users/delete-all
        X-Admin-Secret: tirgus-admin-2026
    """
    if not check_admin_secret():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Count users before deletion
        user_count = User.query.count()
        
        if user_count == 0:
            return jsonify({
                'status': 'success',
                'message': 'No users to delete',
                'deleted_count': 0
            }), 200
        
        # Get some info about users for logging
        users_info = []
        for user in User.query.limit(10).all():
            users_info.append({
                'id': user.id,
                'username': user.username,
                'phone': user.phone
            })
        
        # Delete all users
        User.query.delete()
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully deleted all {user_count} users',
            'deleted_count': user_count,
            'sample_deleted_users': users_info  # Show first 10 for confirmation
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Failed to delete users: {str(e)}'
        }), 500


@admin_bp.route('/user/by-phone/<phone>', methods=['GET'])
def get_user_by_phone(phone):
    """Get user details by phone number.
    
    Requires admin secret in header or query param.
    """
    if not check_admin_secret():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Normalize phone - ensure it has + prefix
        normalized_phone = phone if phone.startswith('+') else f'+{phone}'
        
        user = User.query.filter_by(phone=normalized_phone).first()
        
        if not user:
            return jsonify({
                'status': 'not_found',
                'message': f'No user found with phone: {normalized_phone}'
            }), 404
        
        return jsonify({
            'status': 'found',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'phone': user.phone,
                'phone_verified': user.phone_verified,
                'is_verified': user.is_verified,
                'created_at': user.created_at.isoformat() if user.created_at else None
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@admin_bp.route('/user/by-phone/<phone>', methods=['DELETE'])
def delete_user_by_phone(phone):
    """Delete a user by their phone number.
    
    Requires admin secret in header or query param.
    
    Example:
        DELETE /api/admin/user/by-phone/+37125953807?secret=your-secret
        
        or with header:
        DELETE /api/admin/user/by-phone/+37125953807
        X-Admin-Secret: your-secret
    """
    if not check_admin_secret():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Normalize phone - ensure it has + prefix
        normalized_phone = phone if phone.startswith('+') else f'+{phone}'
        
        user = User.query.filter_by(phone=normalized_phone).first()
        
        if not user:
            return jsonify({
                'status': 'not_found',
                'message': f'No user found with phone: {normalized_phone}'
            }), 404
        
        # Store user info for response
        user_info = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'phone': user.phone
        }
        
        # Delete the user
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'User deleted successfully',
            'deleted_user': user_info
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@admin_bp.route('/user/<int:user_id>', methods=['DELETE'])
def delete_user_by_id(user_id):
    """Delete a user by their ID.
    
    Requires admin secret in header or query param.
    """
    if not check_admin_secret():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'status': 'not_found',
                'message': f'No user found with ID: {user_id}'
            }), 404
        
        # Store user info for response
        user_info = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'phone': user.phone
        }
        
        # Delete the user
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'User deleted successfully',
            'deleted_user': user_info
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
