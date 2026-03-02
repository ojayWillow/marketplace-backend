"""Payment routes for Revolut integration.

Endpoints:
    POST /api/payments/create-order  — Create a Revolut order for a paid feature
    POST /api/payments/webhook       — Receive Revolut webhook (ORDER_COMPLETED)
    GET  /api/payments/status/<id>   — Poll payment status after redirect
"""

from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
import logging

from app import db
from app.models import Payment, TaskRequest, Offering
from app.utils.auth import token_required
from app.services import revolut

logger = logging.getLogger(__name__)

payments_bp = Blueprint('payments', __name__)

# Duration for paid features
FEATURE_DURATION = timedelta(hours=24)


@payments_bp.route('/create-order', methods=['POST'])
@token_required
def create_order(current_user_id):
    """Create a Revolut payment order for a paid feature.
    
    Body:
        type: str — 'urgent_task', 'promote_task', 'promote_offering', 'boost_offering'
        entity_id: int — task_request.id or offering.id
    
    Returns:
        { checkout_url: str, order_id: str }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400
    
    payment_type = data.get('type')
    entity_id = data.get('entity_id')
    
    # Validate payment type
    if not Payment.is_valid_type(payment_type):
        return jsonify({'error': f'Invalid payment type. Must be one of: {list(Payment.PRICES.keys())}'}), 400
    
    if not entity_id:
        return jsonify({'error': 'entity_id is required'}), 400
    
    # Validate entity exists and user owns it
    entity_model = Payment.ENTITY_TYPES[payment_type]
    
    if entity_model == 'task_request':
        entity = TaskRequest.query.get(entity_id)
        if not entity:
            return jsonify({'error': 'Task not found'}), 404
        if entity.creator_id != current_user_id:
            return jsonify({'error': 'You can only boost your own tasks'}), 403
    elif entity_model == 'offering':
        entity = Offering.query.get(entity_id)
        if not entity:
            return jsonify({'error': 'Offering not found'}), 404
        if entity.creator_id != current_user_id:
            return jsonify({'error': 'You can only boost your own offerings'}), 403
    
    # Check if feature is already active (don't allow duplicate payments)
    if payment_type == 'urgent_task':
        if entity.is_urgent and hasattr(entity, 'urgent_expires_at') and entity.urgent_expires_at:
            if datetime.utcnow() < entity.urgent_expires_at:
                return jsonify({'error': 'This task is already urgent'}), 409
    elif payment_type == 'promote_task' or payment_type == 'promote_offering':
        if hasattr(entity, 'is_promoted') and entity.is_promoted:
            if hasattr(entity, 'promoted_expires_at') and entity.promoted_expires_at:
                if datetime.utcnow() < entity.promoted_expires_at:
                    return jsonify({'error': 'This item is already promoted'}), 409
    elif payment_type == 'boost_offering':
        if entity.is_boost_active():
            return jsonify({'error': 'This offering is already boosted'}), 409
    
    # Get price
    amount_cents = Payment.get_price(payment_type)
    
    # Build description for checkout page
    descriptions = {
        'urgent_task': f'Urgent Task: {entity.title}',
        'promote_task': f'Promote Task: {entity.title}',
        'promote_offering': f'Promote Offering: {entity.title}',
        'boost_offering': f'Map Boost: {entity.title}',
    }
    description = descriptions[payment_type]
    
    # Create Revolut order
    order = revolut.create_order(
        amount_cents=amount_cents,
        currency='EUR',
        description=description,
        order_metadata={
            'type': payment_type,
            'entity_id': str(entity_id),
            'user_id': str(current_user_id),
        }
    )
    
    if not order:
        return jsonify({'error': 'Failed to create payment order. Please try again.'}), 502
    
    # Save payment record
    payment = Payment(
        user_id=current_user_id,
        revolut_order_id=order['order_id'],
        type=payment_type,
        entity_id=entity_id,
        amount=amount_cents,
        currency='EUR',
        status='pending',
    )
    db.session.add(payment)
    db.session.commit()
    
    logger.info(f"Payment order created: {payment.id} ({payment_type} for entity {entity_id})")
    
    return jsonify({
        'checkout_url': order['checkout_url'],
        'order_id': order['order_id'],
    }), 201


@payments_bp.route('/webhook', methods=['POST'])
def revolut_webhook():
    """Handle Revolut webhook events.
    
    Revolut sends ORDER_COMPLETED when payment is successful.
    This endpoint verifies the signature and activates the paid feature.
    """
    # Verify webhook signature
    signature = request.headers.get('Revolut-Signature', '')
    payload_body = request.get_data()
    
    if not revolut.verify_webhook_signature(payload_body, signature):
        logger.warning('Webhook signature verification failed')
        return jsonify({'error': 'Invalid signature'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Empty payload'}), 400
    
    event = data.get('event')
    order_data = data.get('order', {})
    order_id = order_data.get('id') or data.get('order_id')
    
    logger.info(f"Webhook received: event={event}, order_id={order_id}")
    
    if event != 'ORDER_COMPLETED':
        # Acknowledge non-completion events without processing
        return jsonify({'status': 'ignored'}), 200
    
    if not order_id:
        logger.error('Webhook ORDER_COMPLETED but no order_id')
        return jsonify({'error': 'Missing order_id'}), 400
    
    # Find payment record
    payment = Payment.query.filter_by(revolut_order_id=order_id).first()
    if not payment:
        logger.error(f'Payment not found for order_id: {order_id}')
        return jsonify({'error': 'Payment not found'}), 404
    
    if payment.status == 'completed':
        # Idempotent — already processed
        return jsonify({'status': 'already_processed'}), 200
    
    # Activate the feature
    success = _activate_feature(payment)
    
    if success:
        payment.status = 'completed'
        payment.completed_at = datetime.utcnow()
        db.session.commit()
        logger.info(f"Payment {payment.id} completed: {payment.type} for entity {payment.entity_id}")
        return jsonify({'status': 'activated'}), 200
    else:
        payment.status = 'failed'
        db.session.commit()
        logger.error(f"Payment {payment.id} activation failed")
        return jsonify({'error': 'Feature activation failed'}), 500


@payments_bp.route('/status/<order_id>', methods=['GET'])
@token_required
def get_payment_status(current_user_id, order_id):
    """Get the status of a payment order.
    
    The frontend polls this endpoint after redirecting back from Revolut checkout.
    """
    payment = Payment.query.filter_by(revolut_order_id=order_id).first()
    
    if not payment:
        return jsonify({'error': 'Payment not found'}), 404
    
    # Only allow the owner to check their payment status
    if payment.user_id != current_user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # If still pending, optionally check with Revolut directly
    if payment.status == 'pending':
        revolut_order = revolut.get_order(order_id)
        if revolut_order and revolut_order.get('state') == 'completed':
            # Webhook may not have arrived yet — activate now
            success = _activate_feature(payment)
            if success:
                payment.status = 'completed'
                payment.completed_at = datetime.utcnow()
                db.session.commit()
                logger.info(f"Payment {payment.id} completed via polling")
    
    return jsonify({
        'status': payment.status,
        'type': payment.type,
        'entity_id': payment.entity_id,
        'completed_at': payment.completed_at.isoformat() + 'Z' if payment.completed_at else None,
    }), 200


def _activate_feature(payment):
    """Activate the paid feature for a payment.
    
    Sets the appropriate flags and expiration on the entity.
    
    Returns:
        True on success, False on failure
    """
    now = datetime.utcnow()
    expires_at = now + FEATURE_DURATION
    
    try:
        if payment.type == 'urgent_task':
            task = TaskRequest.query.get(payment.entity_id)
            if not task:
                logger.error(f'Task {payment.entity_id} not found for activation')
                return False
            task.is_urgent = True
            task.urgent_expires_at = expires_at
            
        elif payment.type == 'promote_task':
            task = TaskRequest.query.get(payment.entity_id)
            if not task:
                logger.error(f'Task {payment.entity_id} not found for activation')
                return False
            task.is_promoted = True
            task.promoted_expires_at = expires_at
            
        elif payment.type == 'promote_offering':
            offering = Offering.query.get(payment.entity_id)
            if not offering:
                logger.error(f'Offering {payment.entity_id} not found for activation')
                return False
            offering.is_promoted = True
            offering.promoted_expires_at = expires_at
            
        elif payment.type == 'boost_offering':
            offering = Offering.query.get(payment.entity_id)
            if not offering:
                logger.error(f'Offering {payment.entity_id} not found for activation')
                return False
            offering.is_boosted = True
            offering.boost_expires_at = expires_at
            
        else:
            logger.error(f'Unknown payment type: {payment.type}')
            return False
        
        db.session.flush()
        return True
        
    except Exception as e:
        logger.error(f'Feature activation error: {e}')
        db.session.rollback()
        return False
