"""Payment routes for Stripe escrow system."""

from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import TaskRequest, Transaction, User
from app.services.stripe_service import StripeService
from app.utils.auth import token_required
import stripe
import os

payments_bp = Blueprint('payments', __name__)


@payments_bp.route('/tasks/<int:task_id>/pay', methods=['POST'])
@token_required
def pay_for_task(current_user_id, task_id):
    """Create payment intent to pay for task upfront (escrow).
    
    Body:
        amount: float - Amount in euros
    
    Returns:
        client_secret: Stripe client secret for frontend
        transaction_id: Transaction ID
    """
    task = TaskRequest.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # Only creator can pay
    if task.creator_id != current_user_id:
        return jsonify({'error': 'Only task creator can pay'}), 403
    
    # Check if already paid
    if task.payment_status not in ['not_required', 'pending']:
        return jsonify({'error': f'Task payment is already {task.payment_status}'}), 400
    
    data = request.get_json()
    if not data or 'amount' not in data:
        return jsonify({'error': 'Amount is required'}), 400
    
    amount = float(data['amount'])
    if amount <= 0:
        return jsonify({'error': 'Amount must be greater than 0'}), 400
    
    try:
        # Create payment intent
        result = StripeService.create_payment_intent(
            task_id=task_id,
            payer_id=current_user_id,
            amount_euros=amount,
            currency=task.currency
        )
        
        # Update task
        task.payment_required = True
        task.payment_status = 'pending'
        db.session.commit()
        
        return jsonify({
            'client_secret': result['client_secret'],
            'transaction_id': result['transaction']['id'],
            'amount': amount,
            'platform_fee': result['transaction']['platform_fee'] / 100,
            'worker_amount': result['transaction']['worker_amount'] / 100,
        }), 200
        
    except Exception as e:
        current_app.logger.error(f'Payment intent creation failed: {str(e)}')
        return jsonify({'error': 'Payment processing failed', 'details': str(e)}), 500


@payments_bp.route('/tasks/<int:task_id>/release-payment', methods=['POST'])
@token_required
def release_payment(current_user_id, task_id):
    """Release payment from escrow to worker.
    
    Only task creator or admin can release.
    """
    task = TaskRequest.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # Check permissions
    user = User.query.get(current_user_id)
    is_creator = task.creator_id == current_user_id
    is_admin = user and getattr(user, 'is_admin', False)
    
    if not is_creator and not is_admin:
        return jsonify({'error': 'Only creator or admin can release payment'}), 403
    
    # Check task status
    if task.status != 'completed':
        return jsonify({'error': 'Task must be completed to release payment'}), 400
    
    # Check payment status
    if task.payment_status != 'held':
        return jsonify({'error': f'Payment cannot be released (status: {task.payment_status})'}), 400
    
    if not task.assigned_to_id:
        return jsonify({'error': 'Task has no worker assigned'}), 400
    
    transaction = Transaction.query.get(task.transaction_id)
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    
    try:
        # Release funds to worker
        updated_transaction = StripeService.release_to_worker(
            transaction_id=transaction.id,
            payee_id=task.assigned_to_id
        )
        
        return jsonify({
            'message': 'Payment released to worker',
            'transaction': updated_transaction.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f'Payment release failed: {str(e)}')
        return jsonify({'error': 'Payment release failed', 'details': str(e)}), 500


@payments_bp.route('/tasks/<int:task_id>/refund', methods=['POST'])
@token_required
def refund_payment(current_user_id, task_id):
    """Refund payment to creator.
    
    Body:
        amount: float - Amount to refund in euros (optional, defaults to full refund)
        reason: str - Refund reason (optional)
    
    Only admin can refund.
    """
    user = User.query.get(current_user_id)
    is_admin = user and getattr(user, 'is_admin', False)
    
    if not is_admin:
        return jsonify({'error': 'Only admins can process refunds'}), 403
    
    task = TaskRequest.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    if task.payment_status not in ['held', 'pending']:
        return jsonify({'error': f'Cannot refund payment with status {task.payment_status}'}), 400
    
    transaction = Transaction.query.get(task.transaction_id)
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    
    data = request.get_json() or {}
    amount_euros = data.get('amount')
    reason = data.get('reason')
    
    # Convert to cents if provided
    amount_cents = int(amount_euros * 100) if amount_euros else None
    
    try:
        updated_transaction = StripeService.refund_to_creator(
            transaction_id=transaction.id,
            amount_cents=amount_cents,
            reason=reason
        )
        
        return jsonify({
            'message': 'Refund processed',
            'transaction': updated_transaction.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f'Refund failed: {str(e)}')
        return jsonify({'error': 'Refund processing failed', 'details': str(e)}), 500


@payments_bp.route('/transactions', methods=['GET'])
@token_required
def get_transactions(current_user_id):
    """Get user's transaction history.
    
    Query params:
        status: Filter by status (optional)
    """
    status = request.args.get('status')
    
    # Get transactions where user is payer or payee
    query = Transaction.query.filter(
        db.or_(
            Transaction.payer_id == current_user_id,
            Transaction.payee_id == current_user_id
        )
    )
    
    if status:
        query = query.filter(Transaction.status == status)
    
    transactions = query.order_by(Transaction.created_at.desc()).all()
    
    return jsonify({
        'transactions': [t.to_dict() for t in transactions],
        'total': len(transactions)
    }), 200


@payments_bp.route('/transactions/<int:transaction_id>', methods=['GET'])
@token_required
def get_transaction(current_user_id, transaction_id):
    """Get transaction details."""
    transaction = Transaction.query.get(transaction_id)
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    
    # Check permissions
    user = User.query.get(current_user_id)
    is_admin = user and getattr(user, 'is_admin', False)
    is_involved = transaction.payer_id == current_user_id or transaction.payee_id == current_user_id
    
    if not is_involved and not is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({'transaction': transaction.to_dict()}), 200


@payments_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks."""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Handle the event
    result = StripeService.handle_webhook(event)
    
    return jsonify(result), 200


@payments_bp.route('/config', methods=['GET'])
def get_stripe_config():
    """Get Stripe public configuration."""
    return jsonify({
        'publishable_key': os.getenv('STRIPE_PUBLISHABLE_KEY'),
        'platform_fee_percent': os.getenv('PLATFORM_FEE_PERCENT', '10.0')
    }), 200
