"""Dispute routes for handling task conflicts."""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from app import db
from app.models import Dispute, TaskRequest, User, Notification, NotificationType, Review
from app.utils.auth import token_required

disputes_bp = Blueprint('disputes', __name__)

# Support email for disputes
SUPPORT_EMAIL = 'support@marketplace.com'

# Statuses where disputes are allowed
# Workers can dispute from 'assigned' onwards (creator might ghost after accepting)
# Creators can dispute from 'in_progress' onwards (work has started)
WORKER_DISPUTABLE_STATUSES = ['assigned', 'in_progress', 'completed', 'pending_confirmation']
CREATOR_DISPUTABLE_STATUSES = ['in_progress', 'completed', 'pending_confirmation']


@disputes_bp.route('/reasons', methods=['GET'])
@token_required
def get_dispute_reasons(current_user_id):
    """Get list of valid dispute reasons."""
    reasons = [
        {'value': reason, 'label': Dispute.REASON_LABELS.get(reason, reason)}
        for reason in Dispute.VALID_REASONS
    ]
    return jsonify({'reasons': reasons}), 200


@disputes_bp.route('', methods=['POST'])
@token_required
def create_dispute(current_user_id):
    """Create a new dispute for a task.
    
    Body:
        task_id: int - The task to dispute
        reason: str - One of the valid reasons
        description: str - Detailed description of the issue
        evidence_images: list[str] - Optional array of image URLs
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    task_id = data.get('task_id')
    reason = data.get('reason')
    description = data.get('description')
    evidence_images = data.get('evidence_images', [])
    
    # Validation
    if not task_id:
        return jsonify({'error': 'Task ID is required'}), 400
    
    if not reason:
        return jsonify({'error': 'Reason is required'}), 400
    
    if reason not in Dispute.VALID_REASONS:
        return jsonify({'error': f'Invalid reason. Must be one of: {Dispute.VALID_REASONS}'}), 400
    
    if not description or len(description.strip()) < 20:
        return jsonify({'error': 'Description must be at least 20 characters'}), 400
    
    # Get the task
    task = TaskRequest.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # Check if user is involved in the task
    is_creator = task.creator_id == current_user_id
    is_worker = task.assigned_to_id == current_user_id
    
    if not is_creator and not is_worker:
        return jsonify({'error': 'You are not involved in this task'}), 403
    
    # Check task status based on user role
    # Workers can dispute earlier (from 'assigned') because creator might ghost them
    # Creators can only dispute once work has started ('in_progress')
    if is_worker:
        allowed_statuses = WORKER_DISPUTABLE_STATUSES
        status_message = 'assigned, in progress, or completed'
    else:
        allowed_statuses = CREATOR_DISPUTABLE_STATUSES
        status_message = 'in progress or completed'
    
    if task.status not in allowed_statuses:
        return jsonify({
            'error': f'Cannot dispute a task with status "{task.status}". Task must be {status_message}.'
        }), 400
    
    # Check if there's already an open dispute for this task by this user
    existing_dispute = Dispute.query.filter_by(
        task_id=task_id,
        filed_by_id=current_user_id,
        status='open'
    ).first()
    
    if existing_dispute:
        return jsonify({'error': 'You already have an open dispute for this task'}), 400
    
    # Determine who the dispute is against
    if is_creator:
        filed_against_id = task.assigned_to_id
    else:
        filed_against_id = task.creator_id
    
    if not filed_against_id:
        return jsonify({'error': 'No other party to dispute against'}), 400
    
    # Create the dispute
    dispute = Dispute(
        task_id=task_id,
        filed_by_id=current_user_id,
        filed_against_id=filed_against_id,
        reason=reason,
        description=description.strip(),
        evidence_images=evidence_images if evidence_images else None,
        status='open'
    )
    
    db.session.add(dispute)
    
    # Update task status to disputed
    task.status = 'disputed'
    
    # Create notification for the other party
    notification = Notification(
        user_id=filed_against_id,
        type=NotificationType.TASK_DISPUTED,
        title='Dispute Filed',
        message=f'A dispute has been filed for task "{task.title}". Please review and respond.',
        related_type='dispute',
        related_id=None  # Will update after commit
    )
    db.session.add(notification)
    
    db.session.commit()
    
    # Update notification with dispute ID
    notification.related_id = dispute.id
    db.session.commit()
    
    return jsonify({
        'message': 'Dispute created successfully',
        'dispute': dispute.to_dict(),
        'support_email': SUPPORT_EMAIL
    }), 201


@disputes_bp.route('', methods=['GET'])
@token_required
def get_disputes(current_user_id):
    """Get disputes involving the current user, or all disputes if admin.
    
    Query params:
        status: optional filter by status
        all: if true and user is admin, return all disputes systemwide
    """
    status = request.args.get('status')  # Optional filter
    show_all = request.args.get('all', 'false').lower() == 'true'
    
    # Check if user is admin
    current_user = User.query.get(current_user_id)
    is_admin = current_user and getattr(current_user, 'is_admin', False)
    
    # Build query
    if show_all and is_admin:
        # Admin: get all disputes
        query = Dispute.query
    else:
        # Regular user: only disputes they're involved in
        query = Dispute.query.filter(
            db.or_(
                Dispute.filed_by_id == current_user_id,
                Dispute.filed_against_id == current_user_id
            )
        )
    
    if status:
        query = query.filter(Dispute.status == status)
    
    disputes = query.order_by(Dispute.created_at.desc()).all()
    
    return jsonify({
        'disputes': [d.to_dict() for d in disputes],
        'total': len(disputes)
    }), 200


@disputes_bp.route('/<int:dispute_id>', methods=['GET'])
@token_required
def get_dispute(current_user_id, dispute_id):
    """Get details of a specific dispute."""
    dispute = Dispute.query.get(dispute_id)
    
    if not dispute:
        return jsonify({'error': 'Dispute not found'}), 404
    
    # Check if user is involved
    if dispute.filed_by_id != current_user_id and dispute.filed_against_id != current_user_id:
        # Allow admins to view any dispute
        current_user = User.query.get(current_user_id)
        if not current_user or not getattr(current_user, 'is_admin', False):
            return jsonify({'error': 'You do not have access to this dispute'}), 403
    
    return jsonify({
        'dispute': dispute.to_dict(),
        'support_email': SUPPORT_EMAIL
    }), 200


@disputes_bp.route('/<int:dispute_id>/respond', methods=['POST'])
@token_required
def respond_to_dispute(current_user_id, dispute_id):
    """Allow the other party to respond to a dispute.
    
    Body:
        description: str - Response description
        evidence_images: list[str] - Optional evidence images
    """
    dispute = Dispute.query.get(dispute_id)
    
    if not dispute:
        return jsonify({'error': 'Dispute not found'}), 404
    
    # Only the person the dispute is filed against can respond
    if dispute.filed_against_id != current_user_id:
        return jsonify({'error': 'Only the other party can respond to this dispute'}), 403
    
    # Can only respond to open disputes
    if dispute.status != 'open':
        return jsonify({'error': 'Cannot respond to a dispute that is not open'}), 400
    
    # Check if already responded
    if dispute.response_description:
        return jsonify({'error': 'You have already responded to this dispute'}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    description = data.get('description')
    evidence_images = data.get('evidence_images', [])
    
    if not description or len(description.strip()) < 20:
        return jsonify({'error': 'Response must be at least 20 characters'}), 400
    
    # Update dispute with response
    dispute.response_description = description.strip()
    dispute.response_images = evidence_images if evidence_images else None
    dispute.responded_at = datetime.utcnow()
    dispute.status = 'under_review'
    
    # Notify the filer that a response was received
    notification = Notification(
        user_id=dispute.filed_by_id,
        type=NotificationType.TASK_DISPUTED,
        title='Dispute Response Received',
        message=f'The other party has responded to your dispute for task "{dispute.task.title}".',
        related_type='dispute',
        related_id=dispute.id
    )
    db.session.add(notification)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Response submitted successfully',
        'dispute': dispute.to_dict()
    }), 200


def _create_dispute_review(task, guilty_user_id, reviewer_id, review_type, resolution_notes):
    """Create a 1-star review for the guilty party after dispute resolution.
    
    Args:
        task: The TaskRequest object
        guilty_user_id: ID of the user who was found at fault
        reviewer_id: ID of the admin/resolver creating the review
        review_type: 'client_review' or 'worker_review'
        resolution_notes: Notes explaining the resolution
    """
    # Check if there's already a review for this task from this type
    existing_review = Review.query.filter_by(
        task_id=task.id,
        reviewed_user_id=guilty_user_id
    ).first()
    
    if existing_review:
        # Update existing review to 1 star
        existing_review.rating = 1.0
        existing_review.content = f"[Dispute Resolution] {resolution_notes or 'Resolved against this user.'}"
        existing_review.updated_at = datetime.utcnow()
    else:
        # Create new 1-star review
        review = Review(
            rating=1.0,
            content=f"[Dispute Resolution] {resolution_notes or 'Resolved against this user.'}",
            reviewer_id=reviewer_id,
            reviewed_user_id=guilty_user_id,
            task_id=task.id,
            review_type=review_type
        )
        db.session.add(review)


def _reactivate_task(task):
    """Reactivate a task post so creator can find a new worker.
    
    Args:
        task: The TaskRequest object to reactivate
    """
    # Reset task to open status
    task.status = 'open'
    task.assigned_to_id = None
    task.completed_at = None
    
    # Note: You may also want to clear any applications from the old worker
    # or handle other cleanup


@disputes_bp.route('/<int:dispute_id>/resolve', methods=['PUT'])
@token_required
def resolve_dispute(current_user_id, dispute_id):
    """Resolve a dispute (admin only for now).
    
    Resolution consequences:
    - refund: Worker is at fault -> Worker gets 1★ review, task cancelled
    - pay_worker: Creator is at fault -> Creator gets 1★ review, task completed
    - partial: Shared fault or compromise -> No auto-review, task completed
    - cancelled: Nobody at fault -> No review, task reactivated for new worker
    
    Body:
        resolution: str - 'refund', 'pay_worker', 'partial', 'cancelled'
        resolution_notes: str - Explanation of the resolution
    """
    dispute = Dispute.query.get(dispute_id)
    
    if not dispute:
        return jsonify({'error': 'Dispute not found'}), 404
    
    # Check permissions - admin only (removed creator permission for production)
    current_user = User.query.get(current_user_id)
    is_admin = current_user and getattr(current_user, 'is_admin', False)
    
    if not is_admin:
        return jsonify({'error': 'Only administrators can resolve disputes'}), 403
    
    if dispute.status == 'resolved':
        return jsonify({'error': 'Dispute is already resolved'}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    resolution = data.get('resolution')
    resolution_notes = data.get('resolution_notes', '')
    
    valid_resolutions = ['refund', 'pay_worker', 'partial', 'cancelled']
    if resolution not in valid_resolutions:
        return jsonify({'error': f'Invalid resolution. Must be one of: {valid_resolutions}'}), 400
    
    task = dispute.task
    
    # Apply resolution consequences
    if resolution == 'refund':
        # Worker is at fault - give worker 1★ review
        _create_dispute_review(
            task=task,
            guilty_user_id=task.assigned_to_id,
            reviewer_id=current_user_id,
            review_type='client_review',  # Creator reviewing worker
            resolution_notes=resolution_notes
        )
        task.status = 'cancelled'
        
    elif resolution == 'pay_worker':
        # Creator is at fault - give creator 1★ review
        _create_dispute_review(
            task=task,
            guilty_user_id=task.creator_id,
            reviewer_id=current_user_id,
            review_type='worker_review',  # Worker reviewing creator
            resolution_notes=resolution_notes
        )
        task.status = 'completed'
        task.completed_at = datetime.utcnow()
        
    elif resolution == 'partial':
        # Shared fault or compromise - no automatic review
        task.status = 'completed'
        task.completed_at = datetime.utcnow()
        
    elif resolution == 'cancelled':
        # Nobody at fault - reactivate task for new worker
        _reactivate_task(task)
    
    # Update dispute
    dispute.resolution = resolution
    dispute.resolution_notes = resolution_notes
    dispute.resolved_by_id = current_user_id
    dispute.resolved_at = datetime.utcnow()
    dispute.status = 'resolved'
    
    # Notify both parties
    resolution_messages = {
        'refund': 'The dispute has been resolved with a full refund. The worker has received a 1-star review.',
        'pay_worker': 'The dispute has been resolved in favor of the worker. The task creator has received a 1-star review.',
        'partial': 'The dispute has been resolved with a partial/compromise solution.',
        'cancelled': 'The dispute has been resolved. The task has been reactivated and you can find a new worker.'
    }
    
    # Different messages for each party
    for user_id in [dispute.filed_by_id, dispute.filed_against_id]:
        # Determine if this user is the "guilty" party for personalized messaging
        is_creator = user_id == task.creator_id
        
        if resolution == 'refund' and not is_creator:
            # Worker receiving bad news
            message = 'The dispute has been resolved against you. A 1-star review has been added to your profile.'
        elif resolution == 'pay_worker' and is_creator:
            # Creator receiving bad news
            message = 'The dispute has been resolved against you. A 1-star review has been added to your profile.'
        else:
            message = resolution_messages.get(resolution, 'Your dispute has been resolved.')
        
        notification = Notification(
            user_id=user_id,
            type=NotificationType.TASK_DISPUTED,
            title='Dispute Resolved',
            message=message,
            related_type='dispute',
            related_id=dispute.id
        )
        db.session.add(notification)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Dispute resolved successfully',
        'dispute': dispute.to_dict(),
        'consequences': {
            'review_added': resolution in ['refund', 'pay_worker'],
            'task_reactivated': resolution == 'cancelled',
            'task_status': task.status
        }
    }), 200


@disputes_bp.route('/task/<int:task_id>', methods=['GET'])
@token_required
def get_task_disputes(current_user_id, task_id):
    """Get all disputes for a specific task."""
    task = TaskRequest.query.get(task_id)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # Check if user is involved in the task
    if task.creator_id != current_user_id and task.assigned_to_id != current_user_id:
        current_user = User.query.get(current_user_id)
        if not current_user or not getattr(current_user, 'is_admin', False):
            return jsonify({'error': 'You do not have access to this task'}), 403
    
    disputes = Dispute.query.filter_by(task_id=task_id).order_by(Dispute.created_at.desc()).all()
    
    return jsonify({
        'disputes': [d.to_dict() for d in disputes],
        'total': len(disputes)
    }), 200
