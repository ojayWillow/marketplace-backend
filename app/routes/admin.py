"""Admin routes for platform management."""
from flask import Blueprint, jsonify, request
from app import db
from app.models import User, TaskRequest, Dispute, Notification, NotificationType, Offering, Review, TaskApplication
from app.utils.auth import token_required
from datetime import datetime, timedelta
from sqlalchemy import func, or_, cast, Date
import hmac
import os

admin_bp = Blueprint('admin', __name__)

# Admin secret for DB operations — MUST be set via env var, no default
ADMIN_SECRET = os.environ.get('ADMIN_SECRET')

# Admin emails whitelist
ADMIN_EMAILS = [
    'admin@tirgus.lv',
    'og.vitols@gmail.com',
]


def check_admin_secret():
    """Check if request has valid admin secret via header only.
    
    Uses hmac.compare_digest for timing-safe comparison.
    Query parameter authentication removed — secrets in URLs leak via
    server logs, browser history, and Referer headers.
    """
    if not ADMIN_SECRET:
        # If ADMIN_SECRET env var is not set, disable secret-based endpoints
        return False
    secret = request.headers.get('X-Admin-Secret', '')
    return hmac.compare_digest(secret, ADMIN_SECRET)


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
    except Exception:
        raise


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
            offerings_count = Offering.query.filter_by(creator_id=u.id).count()
            
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
    except Exception:
        raise


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
    except Exception:
        db.session.rollback()
        raise


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
    except Exception:
        db.session.rollback()
        raise


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
    except Exception:
        db.session.rollback()
        raise


# ============================================================================
# JOBS (TASKS) MANAGEMENT
# ============================================================================

@admin_bp.route('/jobs', methods=['GET'])
@admin_required
def list_jobs_admin(current_user_id):
    """List all jobs/tasks with pagination, search, and status filter."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '').strip()
        status = request.args.get('status', 'all')
        
        query = TaskRequest.query
        
        # Status filter
        if status and status != 'all':
            query = query.filter_by(status=status)
        
        # Search
        if search:
            search_term = f'%{search}%'
            query = query.filter(
                or_(
                    TaskRequest.title.ilike(search_term),
                    TaskRequest.location.ilike(search_term),
                    TaskRequest.description.ilike(search_term),
                )
            )
        
        # Order by newest first
        query = query.order_by(TaskRequest.created_at.desc())
        
        total = query.count()
        tasks = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Batch load creator info
        creator_ids = list({t.creator_id for t in tasks})
        creators = {u.id: u for u in User.query.filter(User.id.in_(creator_ids)).all()} if creator_ids else {}
        
        # Batch load application counts
        task_ids = [t.id for t in tasks]
        app_counts = {}
        if task_ids:
            counts = db.session.query(
                TaskApplication.task_id,
                func.count(TaskApplication.id)
            ).filter(
                TaskApplication.task_id.in_(task_ids)
            ).group_by(TaskApplication.task_id).all()
            app_counts = {tid: cnt for tid, cnt in counts}
        
        jobs_data = []
        for t in tasks:
            creator = creators.get(t.creator_id)
            creator_name = 'Unknown'
            if creator:
                if creator.first_name and creator.last_name:
                    creator_name = f"{creator.first_name} {creator.last_name}"
                else:
                    creator_name = creator.username
            
            jobs_data.append({
                'id': t.id,
                'title': t.title,
                'category': t.category,
                'status': t.status,
                'budget': t.budget,
                'location': t.location,
                'creator_name': creator_name,
                'creator_id': t.creator_id,
                'created_at': t.created_at.isoformat(),
                'applications_count': app_counts.get(t.id, 0),
                'is_urgent': t.is_urgent,
            })
        
        return jsonify({
            'jobs': jobs_data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'totalPages': (total + per_page - 1) // per_page,
        }), 200
    except Exception:
        raise


@admin_bp.route('/jobs/<int:job_id>', methods=['DELETE'])
@admin_required
def delete_job_admin(current_user_id, job_id):
    """Delete a job/task as admin."""
    try:
        task = TaskRequest.query.get(job_id)
        if not task:
            return jsonify({'error': 'Job not found'}), 404
        
        # Delete related applications first
        TaskApplication.query.filter_by(task_id=job_id).delete()
        
        db.session.delete(task)
        db.session.commit()
        
        return jsonify({'message': 'Job deleted successfully', 'job_id': job_id}), 200
    except Exception:
        db.session.rollback()
        raise


# ============================================================================
# OFFERINGS MANAGEMENT
# ============================================================================

@admin_bp.route('/offerings', methods=['GET'])
@admin_required
def list_offerings_admin(current_user_id):
    """List all offerings with pagination, search, and status filter."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '').strip()
        status = request.args.get('status', 'all')
        
        query = Offering.query
        
        # Status filter
        if status and status != 'all':
            query = query.filter_by(status=status)
        
        # Search
        if search:
            search_term = f'%{search}%'
            query = query.filter(
                or_(
                    Offering.title.ilike(search_term),
                    Offering.location.ilike(search_term),
                    Offering.description.ilike(search_term),
                )
            )
        
        # Order by newest first
        query = query.order_by(Offering.created_at.desc())
        
        total = query.count()
        offerings = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Batch load creator info and review stats
        creator_ids = list({o.creator_id for o in offerings})
        creators = {u.id: u for u in User.query.filter(User.id.in_(creator_ids)).all()} if creator_ids else {}
        review_stats = User.get_review_stats_batch(creator_ids) if creator_ids else {}
        
        offerings_data = []
        for o in offerings:
            creator = creators.get(o.creator_id)
            creator_name = 'Unknown'
            if creator:
                if creator.first_name and creator.last_name:
                    creator_name = f"{creator.first_name} {creator.last_name}"
                else:
                    creator_name = creator.username
            
            rating, _ = review_stats.get(o.creator_id, (0, 0))
            
            offerings_data.append({
                'id': o.id,
                'title': o.title,
                'category': o.category,
                'status': o.status,
                'price': o.price,
                'price_type': o.price_type,
                'location': o.location,
                'creator_name': creator_name,
                'creator_id': o.creator_id,
                'created_at': o.created_at.isoformat(),
                'rating': rating or 0,
            })
        
        return jsonify({
            'offerings': offerings_data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'totalPages': (total + per_page - 1) // per_page,
        }), 200
    except Exception:
        raise


@admin_bp.route('/offerings/<int:offering_id>', methods=['DELETE'])
@admin_required
def delete_offering_admin(current_user_id, offering_id):
    """Delete an offering as admin."""
    try:
        offering = Offering.query.get(offering_id)
        if not offering:
            return jsonify({'error': 'Offering not found'}), 404
        
        db.session.delete(offering)
        db.session.commit()
        
        return jsonify({'message': 'Offering deleted successfully', 'offering_id': offering_id}), 200
    except Exception:
        db.session.rollback()
        raise


# ============================================================================
# ANALYTICS
# ============================================================================

@admin_bp.route('/analytics', methods=['GET'])
@admin_required
def get_analytics(current_user_id):
    """Get real computed analytics for the admin dashboard."""
    try:
        range_param = request.args.get('range', '30d')
        
        # Determine date range
        range_days = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}.get(range_param, 30)
        start_date = datetime.utcnow() - timedelta(days=range_days)
        
        # --- Metrics ---
        total_users = User.query.count()
        new_users = User.query.filter(User.created_at >= start_date).count()
        total_jobs = TaskRequest.query.count()
        completed_jobs = TaskRequest.query.filter_by(status='completed').count()
        completion_rate = round((completed_jobs / total_jobs * 100), 1) if total_jobs > 0 else 0
        
        avg_budget = db.session.query(func.avg(TaskRequest.budget)).filter(
            TaskRequest.budget.isnot(None)
        ).scalar() or 0
        avg_budget = round(float(avg_budget), 2)
        
        total_volume = db.session.query(func.sum(TaskRequest.budget)).filter(
            TaskRequest.status == 'completed',
            TaskRequest.budget.isnot(None)
        ).scalar() or 0
        total_volume = round(float(total_volume), 2)
        
        # --- User Growth (daily new signups over the range) ---
        # Group by date
        user_growth_raw = db.session.query(
            cast(User.created_at, Date).label('date'),
            func.count(User.id)
        ).filter(
            User.created_at >= start_date
        ).group_by(
            cast(User.created_at, Date)
        ).order_by(
            cast(User.created_at, Date)
        ).all()
        
        # Build cumulative growth
        base_users = User.query.filter(User.created_at < start_date).count()
        user_growth = []
        running_total = base_users
        for date_val, count in user_growth_raw:
            running_total += count
            user_growth.append({
                'label': date_val.strftime('%b %d'),
                'value': running_total
            })
        
        # If no data points, add at least current total
        if not user_growth:
            user_growth.append({'label': datetime.utcnow().strftime('%b %d'), 'value': total_users})
        
        # --- Jobs by Category ---
        category_counts = db.session.query(
            TaskRequest.category,
            func.count(TaskRequest.id)
        ).group_by(TaskRequest.category).order_by(
            func.count(TaskRequest.id).desc()
        ).limit(10).all()
        
        jobs_by_category = [
            {'label': cat or 'Other', 'value': cnt}
            for cat, cnt in category_counts
        ]
        
        # --- Completion Data (status breakdown) ---
        status_counts = db.session.query(
            TaskRequest.status,
            func.count(TaskRequest.id)
        ).group_by(TaskRequest.status).all()
        
        status_map = {s: c for s, c in status_counts}
        completion_data = [
            {'label': 'Completed', 'value': status_map.get('completed', 0)},
            {'label': 'In Progress', 'value': status_map.get('in_progress', 0) + status_map.get('assigned', 0) + status_map.get('open', 0)},
            {'label': 'Cancelled', 'value': status_map.get('cancelled', 0)},
        ]
        
        # --- Top Locations ---
        location_counts = db.session.query(
            TaskRequest.location,
            func.count(TaskRequest.id)
        ).filter(
            TaskRequest.location.isnot(None),
            TaskRequest.location != ''
        ).group_by(TaskRequest.location).order_by(
            func.count(TaskRequest.id).desc()
        ).limit(8).all()
        
        top_locations = [
            {'label': loc, 'value': cnt}
            for loc, cnt in location_counts
        ]
        
        return jsonify({
            'metrics': {
                'totalUsers': total_users,
                'newUsers': new_users,
                'totalJobs': total_jobs,
                'completionRate': completion_rate,
                'avgJobBudget': avg_budget,
                'totalVolume': total_volume,
            },
            'userGrowth': user_growth,
            'jobsByCategory': jobs_by_category,
            'completionData': completion_data,
            'topLocations': top_locations,
        }), 200
    except Exception:
        raise


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
    except Exception:
        raise


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
    except Exception:
        db.session.rollback()
        raise


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
    except Exception:
        raise


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
                # Use parameterized query to prevent SQL injection
                check_sql = db.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = :table AND column_name = :column"
                )
                result = db.session.execute(check_sql, {'table': table, 'column': column}).fetchone()
                if result is None:
                    # Column type and default come from hardcoded list above,
                    # not from user input, so string formatting is safe here.
                    # Table/column names cannot be parameterized in DDL.
                    alter_sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                    if default is not None:
                        alter_sql += f" DEFAULT {default}"
                    db.session.execute(db.text(alter_sql))
                    db.session.commit()
                    results.append(f"Added {table}.{column}")
                else:
                    results.append(f"Column {table}.{column} already exists")
            except Exception:
                results.append(f"Error with {table}.{column}")
                db.session.rollback()
        
        return jsonify({'status': 'success', 'message': 'Migration completed!', 'details': results}), 200
    except Exception:
        raise


@admin_bp.route('/db-status', methods=['GET'])
def database_status():
    """Check database connection status."""
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({'status': 'ok', 'database': 'connected'}), 200
    except Exception:
        return jsonify({'status': 'error', 'database': 'disconnected'}), 500
