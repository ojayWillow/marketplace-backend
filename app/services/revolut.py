"""Revolut Merchant API client for payment processing.

Handles creating payment orders and verifying webhook signatures.
Uses sandbox or production URLs based on REVOLUT_ENVIRONMENT env var.

Required env vars:
    REVOLUT_API_KEY: Revolut Merchant API secret key
    REVOLUT_WEBHOOK_SECRET: Secret for verifying webhook signatures
    REVOLUT_ENVIRONMENT: 'dev', 'sandbox', or 'production' (default: sandbox)
        - 'dev': skips real Revolut API, uses fake orders for local testing
    PAYMENT_REDIRECT_URL: URL to redirect after payment (e.g. https://app.kolab.lv/payment/callback)
"""

import os
import hmac
import hashlib
import logging
import uuid
import requests

logger = logging.getLogger(__name__)

# Revolut API base URLs
REVOLUT_URLS = {
    'sandbox': 'https://sandbox-merchant.revolut.com/api',
    'production': 'https://merchant.revolut.com/api',
}


def _get_config():
    """Get Revolut configuration from environment."""
    env = os.getenv('REVOLUT_ENVIRONMENT', 'sandbox')
    base_url = REVOLUT_URLS.get(env, REVOLUT_URLS['sandbox'])
    api_key = os.getenv('REVOLUT_API_KEY')
    redirect_url = os.getenv('PAYMENT_REDIRECT_URL', '')
    
    return {
        'base_url': base_url,
        'api_key': api_key,
        'environment': env,
        'redirect_url': redirect_url,
    }


def _is_dev_mode():
    """Check if running in dev mode (no real Revolut calls)."""
    return os.getenv('REVOLUT_ENVIRONMENT', 'sandbox') == 'dev'


def create_order(amount_cents, currency, description, order_metadata=None):
    """Create a Revolut payment order.
    
    In dev mode, returns a fake order immediately without calling Revolut.
    The fake checkout_url points to the local payment callback with auto-complete.
    
    Args:
        amount_cents: Amount in minor currency units (e.g. 200 = \u20ac2.00)
        currency: Three-letter currency code (e.g. 'EUR')
        description: Human-readable description shown on checkout
        order_metadata: Optional dict of metadata to attach to the order
    
    Returns:
        dict with 'order_id' and 'checkout_url' on success
        None on failure
    """
    # Dev mode: return fake order for local testing
    if _is_dev_mode():
        fake_order_id = f"dev_{uuid.uuid4().hex[:16]}"
        redirect_url = os.getenv('PAYMENT_REDIRECT_URL', 'http://localhost:5173/payment/callback')
        checkout_url = f"{redirect_url}?order_id={fake_order_id}"
        logger.info(f"[DEV MODE] Fake order created: {fake_order_id} ({amount_cents} {currency})")
        return {
            'order_id': fake_order_id,
            'checkout_url': checkout_url,
        }
    
    config = _get_config()
    
    if not config['api_key']:
        logger.error('REVOLUT_API_KEY is not configured')
        return None
    
    headers = {
        'Authorization': f"Bearer {config['api_key']}",
        'Content-Type': 'application/json',
    }
    
    payload = {
        'amount': amount_cents,
        'currency': currency,
        'description': description,
    }
    
    # Add redirect URL so Revolut sends user back after payment
    if config['redirect_url']:
        payload['checkout_url'] = config['redirect_url']
    
    if order_metadata:
        payload['metadata'] = order_metadata
    
    try:
        url = f"{config['base_url']}/orders"
        logger.info(f"Creating Revolut order: {amount_cents} {currency} - {description}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        order_id = data.get('id')
        checkout_url = data.get('checkout_url')
        
        if not order_id:
            logger.error(f'Revolut order response missing id: {data}')
            return None
        
        logger.info(f"Revolut order created: {order_id}")
        
        return {
            'order_id': order_id,
            'checkout_url': checkout_url,
        }
        
    except requests.exceptions.HTTPError as e:
        logger.error(f'Revolut API HTTP error: {e.response.status_code} - {e.response.text}')
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f'Revolut API request error: {e}')
        return None


def get_order(order_id):
    """Retrieve a Revolut order by ID.
    
    In dev mode, returns a fake completed order so polling auto-activates the feature.
    
    Returns:
        dict with order details on success, None on failure
    """
    # Dev mode: fake orders are always "completed"
    if _is_dev_mode():
        logger.info(f"[DEV MODE] get_order({order_id}) -> completed")
        return {
            'id': order_id,
            'state': 'completed',
        }
    
    config = _get_config()
    
    if not config['api_key']:
        logger.error('REVOLUT_API_KEY is not configured')
        return None
    
    headers = {
        'Authorization': f"Bearer {config['api_key']}",
    }
    
    try:
        url = f"{config['base_url']}/orders/{order_id}"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f'Revolut get order error: {e}')
        return None


def verify_webhook_signature(payload_body, signature_header):
    """Verify Revolut webhook signature.
    
    In dev mode, always returns True (no signature verification).
    
    Args:
        payload_body: Raw request body (bytes)
        signature_header: Value of the 'Revolut-Signature' header
    
    Returns:
        True if signature is valid, False otherwise
    """
    # Dev mode: skip signature verification
    if _is_dev_mode():
        logger.info("[DEV MODE] Webhook signature check bypassed")
        return True
    
    webhook_secret = os.getenv('REVOLUT_WEBHOOK_SECRET')
    
    if not webhook_secret:
        logger.error('REVOLUT_WEBHOOK_SECRET is not configured')
        return False
    
    if not signature_header:
        logger.warning('Missing webhook signature header')
        return False
    
    try:
        # Revolut signs webhooks with HMAC-SHA256
        expected = hmac.new(
            webhook_secret.encode('utf-8'),
            payload_body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature_header)
    except Exception as e:
        logger.error(f'Webhook signature verification error: {e}')
        return False
