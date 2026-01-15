"""Push notification subscription routes."""

from flask import Blueprint, request, jsonify
from functools import wraps
import jwt
import os

from app import db
from app.models import PushSubscription

push_bp = Blueprint('push', __name__)

SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')

# Get VAPID public key for frontend
VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY', '')


def token_required(f):
    """Decorator to require valid JWT token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            token = auth_header.split(' ')[1] if ' ' in auth_header else auth_header
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            current_user_id = payload['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except Exception as e:
            return jsonify({'error': 'Token is invalid', 'details': str(e)}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorated


@push_bp.route('/vapid-public-key', methods=['GET'])
def get_vapid_public_key():
    """
    Get the VAPID public key needed for push subscription.
    This endpoint is public - no auth required.
    """
    if not VAPID_PUBLIC_KEY:
        return jsonify({'error': 'Push notifications not configured'}), 503
    
    return jsonify({
        'publicKey': VAPID_PUBLIC_KEY
    }), 200


@push_bp.route('/subscribe', methods=['POST'])
@token_required
def subscribe(current_user_id):
    """
    Subscribe to push notifications.
    
    Request body:
    {
        "endpoint": "https://fcm.googleapis.com/...",
        "keys": {
            "p256dh": "...",
            "auth": "..."
        },
        "device_name": "iPhone 14" (optional)
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        endpoint = data.get('endpoint')
        keys = data.get('keys', {})
        p256dh = keys.get('p256dh')
        auth = keys.get('auth')
        device_name = data.get('device_name')
        
        if not endpoint or not p256dh or not auth:
            return jsonify({'error': 'Missing required subscription data'}), 400
        
        # Check if subscription already exists
        existing = PushSubscription.query.filter_by(
            endpoint=endpoint
        ).first()
        
        if existing:
            # Update existing subscription
            existing.user_id = current_user_id
            existing.p256dh_key = p256dh
            existing.auth_key = auth
            existing.device_name = device_name
            existing.is_active = True
            db.session.commit()
            
            return jsonify({
                'message': 'Subscription updated',
                'subscription_id': existing.id
            }), 200
        
        # Create new subscription
        subscription = PushSubscription(
            user_id=current_user_id,
            endpoint=endpoint,
            p256dh_key=p256dh,
            auth_key=auth,
            device_name=device_name
        )
        
        db.session.add(subscription)
        db.session.commit()
        
        return jsonify({
            'message': 'Subscribed to push notifications',
            'subscription_id': subscription.id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@push_bp.route('/unsubscribe', methods=['POST'])
@token_required
def unsubscribe(current_user_id):
    """
    Unsubscribe from push notifications.
    
    Request body:
    {
        "endpoint": "https://fcm.googleapis.com/..."
    }
    """
    try:
        data = request.get_json()
        endpoint = data.get('endpoint')
        
        if not endpoint:
            return jsonify({'error': 'Endpoint required'}), 400
        
        subscription = PushSubscription.query.filter_by(
            endpoint=endpoint,
            user_id=current_user_id
        ).first()
        
        if subscription:
            subscription.is_active = False
            db.session.commit()
            return jsonify({'message': 'Unsubscribed successfully'}), 200
        
        return jsonify({'message': 'Subscription not found'}), 404
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@push_bp.route('/subscriptions', methods=['GET'])
@token_required
def get_subscriptions(current_user_id):
    """
    Get all push subscriptions for current user.
    """
    try:
        subscriptions = PushSubscription.query.filter_by(
            user_id=current_user_id,
            is_active=True
        ).all()
        
        return jsonify({
            'subscriptions': [
                {
                    'id': s.id,
                    'device_name': s.device_name,
                    'created_at': s.created_at.isoformat() if s.created_at else None
                }
                for s in subscriptions
            ],
            'count': len(subscriptions)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@push_bp.route('/test', methods=['POST'])
@token_required
def send_test_notification(current_user_id):
    """
    Send a test push notification to the current user.
    Useful for testing if push notifications work.
    """
    from app.services.push_notifications import send_push_notification
    
    result = send_push_notification(
        user_id=current_user_id,
        title='🔔 Test Notification',
        body='Push notifications are working!',
        url='/'
    )
    
    return jsonify(result), 200
