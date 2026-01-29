"""Admin routes for database management."""
from flask import Blueprint, jsonify, request
from app import db
from app.models import User, TaskRequest
from datetime import datetime, timedelta
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
# SEED DATA ENDPOINT
# ============================================================================

@admin_bp.route('/seed-test-data', methods=['POST', 'GET'])
def seed_test_data():
    """Create sample tasks for testing.
    
    Requires admin secret in header or query param.
    
    Example:
        POST /api/admin/seed-test-data?secret=tirgus-admin-2026
        
    Creates tasks distributed among users with these emails:
        - dajsis@me.com
        - win10keypro@gmail.com
        - og.vitols@gmail.com
    """
    if not check_admin_secret():
        return jsonify({'error': 'Unauthorized. Provide secret as query param or X-Admin-Secret header'}), 401
    
    try:
        # Find users by email
        test_emails = ['dajsis@me.com', 'win10keypro@gmail.com', 'og.vitols@gmail.com']
        users = User.query.filter(User.email.in_(test_emails)).all()
        
        if not users:
            return jsonify({
                'status': 'error',
                'message': 'No test users found! Register users with these emails first: ' + ', '.join(test_emails)
            }), 404
        
        user_map = {u.email: u for u in users}
        found_emails = list(user_map.keys())
        
        # Riga coordinates (center)
        riga_lat = 56.9496
        riga_lng = 24.1052
        
        # Sample tasks data - distributed across categories
        sample_tasks = [
            # Delivery tasks
            {
                'title': 'Grocery pickup from Rimi',
                'description': 'Need someone to pick up groceries from Rimi Olimpia and deliver to Purvciems. List will be provided. About 10-15 items.',
                'category': 'delivery',
                'budget': 15.00,
                'location': 'Rīga, Purvciems',
                'latitude': 56.9550,
                'longitude': 24.1680,
                'priority': 'normal',
                'is_urgent': False,
                'deadline_days': 2,
            },
            {
                'title': 'URGENT: Document delivery to Jugla',
                'description': 'Need to deliver important documents from city center to Jugla business park. Time sensitive - must arrive by 5 PM today!',
                'category': 'delivery',
                'budget': 25.00,
                'location': 'Rīga, Centrs → Jugla',
                'latitude': 56.9680,
                'longitude': 24.1890,
                'priority': 'urgent',
                'is_urgent': True,
                'deadline_days': 0,
            },
            
            # Cleaning tasks
            {
                'title': 'Apartment deep cleaning before moving out',
                'description': '2-room apartment needs thorough cleaning including windows, kitchen appliances, and bathroom. Approx 55 sqm. Cleaning supplies provided.',
                'category': 'cleaning',
                'budget': 80.00,
                'location': 'Rīga, Āgenskalns',
                'latitude': 56.9380,
                'longitude': 24.0720,
                'priority': 'high',
                'is_urgent': False,
                'deadline_days': 5,
            },
            {
                'title': 'Office cleaning - weekly service',
                'description': 'Looking for someone to clean small office space (40 sqm) once a week. Vacuuming, dusting, trash removal. Every Friday afternoon preferred.',
                'category': 'cleaning',
                'budget': 35.00,
                'location': 'Rīga, Quiet Center',
                'latitude': 56.9560,
                'longitude': 24.1150,
                'priority': 'normal',
                'is_urgent': False,
                'deadline_days': 7,
            },
            
            # Repair tasks
            {
                'title': 'Fix leaking kitchen faucet',
                'description': 'Kitchen faucet is dripping constantly. Need someone with plumbing experience to repair or replace it. I have a replacement faucet if needed.',
                'category': 'repair',
                'budget': 40.00,
                'location': 'Rīga, Imanta',
                'latitude': 56.9420,
                'longitude': 23.9580,
                'priority': 'high',
                'is_urgent': False,
                'deadline_days': 3,
            },
            {
                'title': 'Assemble IKEA wardrobe',
                'description': 'Need help assembling PAX wardrobe system. 3 frames with sliding doors. All parts and tools available. Should take 3-4 hours.',
                'category': 'repair',
                'budget': 50.00,
                'location': 'Rīga, Teika',
                'latitude': 56.9650,
                'longitude': 24.1520,
                'priority': 'normal',
                'is_urgent': False,
                'deadline_days': 7,
            },
            
            # Moving tasks
            {
                'title': 'Help moving furniture - 2 people needed',
                'description': 'Moving from 3rd floor apartment (no elevator) to ground floor nearby. Sofa, bed, wardrobe, and boxes. Need 2 strong people for about 3 hours.',
                'category': 'moving',
                'budget': 120.00,
                'location': 'Rīga, Ziepniekkalns',
                'latitude': 56.9180,
                'longitude': 24.0650,
                'priority': 'high',
                'is_urgent': False,
                'deadline_days': 4,
            },
            
            # Tutoring tasks
            {
                'title': 'Math tutoring for 9th grader',
                'description': 'Looking for math tutor for my son preparing for exams. Need help with algebra and geometry. 2 sessions per week, 1.5 hours each.',
                'category': 'tutoring',
                'budget': 20.00,
                'location': 'Rīga, Mežciems',
                'latitude': 56.9720,
                'longitude': 24.2050,
                'priority': 'normal',
                'is_urgent': False,
                'deadline_days': 14,
            },
            
            # Other tasks
            {
                'title': 'Dog walking - 2 weeks while on vacation',
                'description': 'Need someone to walk my friendly Labrador twice daily (morning and evening) while I am away. He is well-trained and loves people. Keys will be provided.',
                'category': 'other',
                'budget': 150.00,
                'location': 'Rīga, Mežaparks',
                'latitude': 56.9850,
                'longitude': 24.1350,
                'priority': 'normal',
                'is_urgent': False,
                'deadline_days': 10,
            },
        ]
        
        created_tasks = []
        
        for i, task_data in enumerate(sample_tasks):
            # Distribute tasks among available users (round-robin)
            creator = users[i % len(users)]
            
            # Calculate deadline
            deadline = None
            if task_data.get('deadline_days') is not None:
                deadline = datetime.utcnow() + timedelta(days=task_data['deadline_days'])
            
            task = TaskRequest(
                title=task_data['title'],
                description=task_data['description'],
                category=task_data['category'],
                budget=task_data['budget'],
                location=task_data['location'],
                latitude=task_data['latitude'],
                longitude=task_data['longitude'],
                creator_id=creator.id,
                priority=task_data['priority'],
                is_urgent=task_data['is_urgent'],
                deadline=deadline,
                status='open'
            )
            
            db.session.add(task)
            created_tasks.append({
                'title': task_data['title'],
                'category': task_data['category'],
                'creator': creator.email,
                'budget': task_data['budget']
            })
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Created {len(created_tasks)} sample tasks',
            'users_found': found_emails,
            'users_missing': [e for e in test_emails if e not in found_emails],
            'tasks_created': created_tasks
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Failed to seed data: {str(e)}'
        }), 500


@admin_bp.route('/clear-tasks', methods=['DELETE', 'POST'])
def clear_all_tasks():
    """Delete ALL tasks from the database.
    
    ⚠️  CAUTION: This will permanently delete all tasks!
    
    Requires admin secret in header or query param.
    """
    if not check_admin_secret():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        task_count = TaskRequest.query.count()
        
        if task_count == 0:
            return jsonify({
                'status': 'success',
                'message': 'No tasks to delete',
                'deleted_count': 0
            }), 200
        
        TaskRequest.query.delete()
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully deleted all {task_count} tasks',
            'deleted_count': task_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Failed to delete tasks: {str(e)}'
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


@admin_bp.route('/users', methods=['GET'])
def list_all_users():
    """List all users in the database.
    
    Requires admin secret in header or query param.
    """
    if not check_admin_secret():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        users = User.query.all()
        
        return jsonify({
            'status': 'success',
            'count': len(users),
            'users': [{
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'phone': u.phone,
                'is_verified': u.is_verified,
                'created_at': u.created_at.isoformat() if u.created_at else None
            } for u in users]
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
