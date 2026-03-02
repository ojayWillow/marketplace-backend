"""Revolut Merchant API client for payment processing.

Handles creating payment orders and verifying webhook signatures.
Uses sandbox or production URLs based on REVOLUT_ENVIRONMENT env var.

Required env vars:
    REVOLUT_API_KEY: Revolut Merchant API secret key
    REVOLUT_WEBHOOK_SECRET: Secret for verifying webhook signatures
    REVOLUT_ENVIRONMENT: 'sandbox' or 'production' (default: sandbox)
    PAYMENT_REDIRECT_URL: URL to redirect after payment (e.g. https://app.kolab.lv/payment/callback)
"""

import os
import hmac
import hashlib
import logging
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


def create_order(amount_cents, currency, description, order_metadata=None):
    """Create a Revolut payment order.
    
    Args:
        amount_cents: Amount in minor currency units (e.g. 200 = €2.00)
        currency: Three-letter currency code (e.g. 'EUR')
        description: Human-readable description shown on checkout
        order_metadata: Optional dict of metadata to attach to the order
    
    Returns:
        dict with 'order_id' and 'checkout_url' on success
        None on failure
    """
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
    
    Useful for polling payment status from the frontend.
    
    Returns:
        dict with order details on success, None on failure
    """
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
    
    Args:
        payload_body: Raw request body (bytes)
        signature_header: Value of the 'Revolut-Signature' header
    
    Returns:
        True if signature is valid, False otherwise
    """
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
