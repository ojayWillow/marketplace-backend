"""Dispute routes for handling task conflicts."""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from app import db
from app.models import Dispute, TaskRequest, User, Notification, NotificationType
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
    # NOTE: We store task_id in related_id (not dispute_id) so frontend can route to /task/{id}
    notification = Notification(
        user_id=filed_against_id,
        type=NotificationType.TASK_DISPUTED,
        title='Dispute Filed',
        message=f'A dispute has been filed for task "{task.title}". Please review and respond.',
        related_type='task',
        related_id=task_id
    )
    # Set data dict so frontend can render localized notification with task_title
    notification.set_data({'task_title': task.title})
    db.session.add(notification)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Dispute created successfully',
        'dispute': dispute.to_dict(),
        'support_email': SUPPORT_EMAIL
    }), 201


@disputes_bp.route('', methods=['GET'])
@token_required
def get_disputes(current_user_id):
    """Get all disputes involving the current user."""
    status = request.args.get('status')  # Optional filter
    
    # Get disputes where user is either filer or target
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
        related_type='task',
        related_id=dispute.task_id
    )
    notification.set_data({'task_title': dispute.task.title})
    db.session.add(notification)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Response submitted successfully',
        'dispute': dispute.to_dict()
    }), 200


@disputes_bp.route('/<int:dispute_id>/resolve', methods=['PUT'])
@token_required
def resolve_dispute(current_user_id, dispute_id):
    """Resolve a dispute (admin only for now).
    
    Body:
        resolution: str - 'refund', 'pay_worker', 'partial', 'cancelled'
        resolution_notes: str - Explanation of the resolution
    """
    dispute = Dispute.query.get(dispute_id)
    
    if not dispute:
        return jsonify({'error': 'Dispute not found'}), 404
    
    # Check permissions - admin or task creator can resolve
    current_user = User.query.get(current_user_id)
    is_admin = current_user and getattr(current_user, 'is_admin', False)
    is_creator = dispute.task.creator_id == current_user_id
    
    # For MVP: Allow creator to resolve, but in production should be admin only
    if not is_admin and not is_creator:
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
    
    # Update dispute
    dispute.resolution = resolution
    dispute.resolution_notes = resolution_notes
    dispute.resolved_by_id = current_user_id
    dispute.resolved_at = datetime.utcnow()
    dispute.status = 'resolved'
    
    # Update task status based on resolution
    task = dispute.task
    if resolution == 'cancelled':
        task.status = 'cancelled'
    elif resolution in ['refund', 'pay_worker', 'partial']:
        task.status = 'completed'
        task.completed_at = datetime.utcnow()
    
    # Notify both parties about the resolution
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
        notification.set_data({
            'task_title': task.title,
            'resolution': resolution,
            'resolution_notes': resolution_notes,
        })
        db.session.add(notification)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Dispute resolved successfully',
        'dispute': dispute.to_dict()
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
