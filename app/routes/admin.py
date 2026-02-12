"""Admin routes for platform management."""
from flask import Blueprint, jsonify, request
from app import db
from app.models import User, TaskRequest, Dispute, Notification, NotificationType, Offering, Review
from app.utils.auth import token_required
from datetime import datetime, timedelta
from sqlalchemy import func, or_
import os

admin_bp = Blueprint('admin', __name__)

# Simple admin secret for DB operations
ADMIN_SECRET = os.environ.get('ADMIN_SECRET', 'tirgus-admin-2026')

# Admin emails whitelist
ADMIN_EMAILS = [
    'admin@tirgus.lv',
    'og.vitols@gmail.com',
]


def check_admin_secret():
    """Check if request has valid admin secret."""
    secret = request.headers.get('X-Admin-Secret') or request.args.get('secret')
    return secret == ADMIN_SECRET


def check_admin_user(current_user_id):
    """Check if user is admin (by field or email whitelist)."""
    user = User.query.get(current_user_id)
    if not user:
        return False
    if getattr(user, 'is_admin', False):
        return True
    if user.email in ADMIN_EMAILS:
        return True
    return False


def admin_required(f):
    """Decorator that combines token_required + admin check."""
    from functools import wraps
    @wraps(f)
    @token_required
    def decorated(current_user_id, *args, **kwargs):
        if not check_admin_user(current_user_id):
            return jsonify({'error': 'Admin access required'}), 403
        return f(current_user_id, *args, **kwargs)
    return decorated


# ============================================================================
# DASHBOARD STATS
# ============================================================================

@admin_bp.route('/stats', methods=['GET'])
@admin_required
def get_stats(current_user_id):
    """Get overview stats for admin dashboard."""
    try:
        total_users = User.query.count()
        total_tasks = TaskRequest.query.count()
        total_offerings = Offering.query.count()
        total_disputes = Dispute.query.count()
        open_disputes = Dispute.query.filter(Dispute.status.in_(['open', 'under_review'])).count()
        
        # Users in last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        new_users_week = User.query.filter(User.created_at >= week_ago).count()
        
        # Tasks by status
        active_tasks = TaskRequest.query.filter(TaskRequest.status.in_(['open', 'assigned', 'in_progress'])).count()
        completed_tasks = TaskRequest.query.filter_by(status='completed').count()
        disputed_tasks = TaskRequest.query.filter_by(status='disputed').count()
        
        return jsonify({
            'total_users': total_users,
            'new_users_week': new_users_week,
            'total_tasks': total_tasks,
            'active_tasks': active_tasks,
            'completed_tasks': completed_tasks,
            'disputed_tasks': disputed_tasks,
            'total_offerings': total_offerings,
            'total_disputes': total_disputes,
            'open_disputes': open_disputes,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# USER MANAGEMENT
# ============================================================================

@admin_bp.route('/users', methods=['GET'])
@admin_required
def list_users_admin(current_user_id):
    """List all users with pagination and search."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '').strip()
        filter_type = request.args.get('filter', 'all')
        
        query = User.query
        
        # Search
        if search:
            search_term = f'%{search}%'
            query = query.filter(
                or_(
                    User.username.ilike(search_term),
                    User.email.ilike(search_term),
                    User.phone.ilike(search_term),
                    User.first_name.ilike(search_term),
                    User.last_name.ilike(search_term),
                )
            )
        
        # Filter
        if filter_type == 'active':
            query = query.filter_by(is_active=True)
        elif filter_type == 'banned':
            query = query.filter_by(is_active=False)
        
        # Order by newest first
        query = query.order_by(User.created_at.desc())
        
        # Paginate
        total = query.count()
        users = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Get review stats and task counts in batch
        user_ids = [u.id for u in users]
        review_stats = User.get_review_stats_batch(user_ids)
        task_counts = User.get_completed_tasks_batch(user_ids)
        
        users_data = []
        for u in users:
            rating, review_count = review_stats.get(u.id, (None, 0))
            completed = task_counts.get(u.id, 0)
            
            # Count jobs (tasks created) and offerings
            jobs_count = TaskRequest.query.filter_by(creator_id=u.id).count()
            offerings_count = Offering.query.filter_by(user_id=u.id).count()
            
            users_data.append({
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'phone': u.phone,
                'first_name': u.first_name,
                'last_name': u.last_name,
                'avatar_url': u.avatar_url,
                'profile_picture_url': u.profile_picture_url,
                'is_active': u.is_active,
                'is_banned': not u.is_active,
                'is_verified': u.is_verified,
                'created_at': u.created_at.isoformat(),
                'last_seen': u.last_seen.isoformat() if u.last_seen else None,
                'rating': rating or 0,
                'review_count': review_count,
                'jobs_count': jobs_count,
                'offerings_count': offerings_count,
                'completed_tasks': completed,
            })
        
        return jsonify({
            'users': users_data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'totalPages': (total + per_page - 1) // per_page,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/users/<int:user_id>/ban', methods=['POST'])
@admin_required
def ban_user(current_user_id, user_id):
    """Ban a user."""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user.is_active = False
        db.session.commit()
        
        return jsonify({'message': f'User {user.username} banned', 'user_id': user_id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/users/<int:user_id>/unban', methods=['POST'])
@admin_required
def unban_user(current_user_id, user_id):
    """Unban a user."""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user.is_active = True
        db.session.commit()
        
        return jsonify({'message': f'User {user.username} unbanned', 'user_id': user_id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/users/<int:user_id>/verify', methods=['POST'])
@admin_required
def verify_user(current_user_id, user_id):
    """Verify a user."""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user.is_verified = True
        db.session.commit()
        
        return jsonify({'message': f'User {user.username} verified', 'user_id': user_id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# DISPUTES (ADMIN)
# ============================================================================

@admin_bp.route('/disputes', methods=['GET'])
@admin_required
def list_all_disputes(current_user_id):
    """List ALL disputes for admin review."""
    try:
        status = request.args.get('status')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        query = Dispute.query
        
        if status and status != 'all':
            query = query.filter_by(status=status)
        
        query = query.order_by(Dispute.created_at.desc())
        
        total = query.count()
        disputes = query.offset((page - 1) * per_page).limit(per_page).all()
        
        disputes_data = []
        for d in disputes:
            data = d.to_dict()
            # Add extra info for admin
            data['filed_by_email'] = d.filed_by.email if d.filed_by else None
            data['filed_by_username'] = d.filed_by.username if d.filed_by else None
            data['filed_against_email'] = d.filed_against.email if d.filed_against else None
            data['filed_against_username'] = d.filed_against.username if d.filed_against else None
            data['task_status'] = d.task.status if d.task else None
            data['task_budget'] = d.task.budget if d.task else None
            disputes_data.append(data)
        
        return jsonify({
            'disputes': disputes_data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'totalPages': (total + per_page - 1) // per_page,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/disputes/<int:dispute_id>/resolve', methods=['PUT'])
@admin_required
def admin_resolve_dispute(current_user_id, dispute_id):
    """Resolve a dispute as admin."""
    try:
        dispute = Dispute.query.get(dispute_id)
        if not dispute:
            return jsonify({'error': 'Dispute not found'}), 404
        
        if dispute.status == 'resolved':
            return jsonify({'error': 'Dispute already resolved'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        resolution = data.get('resolution')
        resolution_notes = data.get('resolution_notes', '')
        
        valid_resolutions = ['refund', 'pay_worker', 'partial', 'cancelled']
        if resolution not in valid_resolutions:
            return jsonify({'error': f'Invalid resolution. Must be one of: {valid_resolutions}'}), 400
        
        # Update dispute
        dispute.resolution = resolution
        dispute.resolution_notes = resolution_notes
        dispute.resolved_by_id = current_user_id
        dispute.resolved_at = datetime.utcnow()
        dispute.status = 'resolved'
        
        # Update task status
        task = dispute.task
        if task:
            if resolution == 'cancelled':
                task.status = 'cancelled'
            elif resolution in ['refund', 'pay_worker', 'partial']:
                task.status = 'completed'
                task.completed_at = datetime.utcnow()
        
        # Notify both parties
        resolution_messages = {
            'refund': 'The dispute has been resolved with a full refund to the task creator.',
            'pay_worker': 'The dispute has been resolved in favor of the worker.',
            'partial': 'The dispute has been resolved with a partial resolution.',
            'cancelled': 'The dispute has been resolved and the task has been cancelled.'
        }
        
        for user_id in [dispute.filed_by_id, dispute.filed_against_id]:
            notification = Notification(
                user_id=user_id,
                type=NotificationType.TASK_DISPUTED,
                title='Dispute Resolved',
                message=resolution_messages.get(resolution, 'Your dispute has been resolved.'),
                related_type='task',
                related_id=dispute.task_id
            )
            db.session.add(notification)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Dispute resolved successfully',
            'dispute': dispute.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# DATABASE MANAGEMENT (secret-protected, not token-based)
# ============================================================================

@admin_bp.route('/init-db', methods=['GET', 'POST'])
def init_database():
    """Initialize database tables."""
    if not check_admin_secret():
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        db.create_all()
        return jsonify({'status': 'success', 'message': 'Database tables created successfully!'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed: {str(e)}'}), 500


@admin_bp.route('/migrate-db', methods=['GET', 'POST'])
def migrate_database():
    """Add missing columns to existing tables."""
    if not check_admin_secret():
        return jsonify({'error': 'Unauthorized'}), 401
    
    results = []
    try:
        column_migrations = [
            ('users', 'last_seen', 'TIMESTAMP', None),
            ('offerings', 'is_boosted', 'BOOLEAN', 'FALSE'),
            ('offerings', 'boost_expires_at', 'TIMESTAMP', None),
        ]
        
        for table, column, col_type, default in column_migrations:
            try:
                check_sql = f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}' AND column_name = '{column}'"
                result = db.session.execute(db.text(check_sql)).fetchone()
                if result is None:
                    alter_sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                    if default is not None:
                        alter_sql += f" DEFAULT {default}"
                    db.session.execute(db.text(alter_sql))
                    db.session.commit()
                    results.append(f"Added {table}.{column}")
                else:
                    results.append(f"Column {table}.{column} already exists")
            except Exception as e:
                results.append(f"Error with {table}.{column}: {str(e)}")
                db.session.rollback()
        
        return jsonify({'status': 'success', 'message': 'Migration completed!', 'details': results}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Migration failed: {str(e)}', 'details': results}), 500


@admin_bp.route('/db-status', methods=['GET'])
def database_status():
    """Check database connection status."""
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({'status': 'ok', 'database': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'database': 'disconnected', 'message': str(e)}), 500
