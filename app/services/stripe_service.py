"""Stripe Checkout Sessions client for payment processing.

Handles creating checkout sessions, retrieving session status,
and verifying webhook signatures.

Required env vars:
    STRIPE_SECRET_KEY: Stripe secret API key (sk_test_... or sk_live_...)
    STRIPE_WEBHOOK_SECRET: Webhook endpoint signing secret (whsec_...)
    STRIPE_ENVIRONMENT: 'dev', 'test', or 'live' (default: test)
        - 'dev': skips real Stripe API, uses fake sessions for local testing
    PAYMENT_REDIRECT_URL: URL to redirect after payment (e.g. https://app.kolab.lv/payment/callback)
"""

import os
import uuid
import logging
import stripe

logger = logging.getLogger(__name__)


def _configure_stripe():
    """Set the Stripe API key from environment."""
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')


def _is_dev_mode():
    """Check if running in dev mode (no real Stripe calls)."""
    return os.getenv('STRIPE_ENVIRONMENT', 'test') == 'dev'


def create_checkout_session(amount_cents, currency, description, metadata=None):
    """Create a Stripe Checkout Session.

    In dev mode, returns a fake session immediately without calling Stripe.
    The fake checkout_url points to the local payment callback with auto-complete.

    Args:
        amount_cents: Amount in minor currency units (e.g. 200 = €2.00)
        currency: Three-letter currency code (e.g. 'eur')
        description: Human-readable description shown on checkout
        metadata: Optional dict of metadata to attach to the session

    Returns:
        dict with 'session_id' and 'checkout_url' on success
        None on failure
    """
    # Dev mode: return fake session for local testing
    if _is_dev_mode():
        fake_session_id = f"dev_cs_{uuid.uuid4().hex[:16]}"
        redirect_url = os.getenv('PAYMENT_REDIRECT_URL', 'http://localhost:5173/payment/callback')
        checkout_url = f"{redirect_url}?session_id={fake_session_id}"
        logger.info(f"[DEV MODE] Fake checkout session created: {fake_session_id} ({amount_cents} {currency})")
        return {
            'session_id': fake_session_id,
            'checkout_url': checkout_url,
        }

    _configure_stripe()

    if not stripe.api_key:
        logger.error('STRIPE_SECRET_KEY is not configured')
        return None

    redirect_url = os.getenv('PAYMENT_REDIRECT_URL', '')

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': currency.lower(),
                    'product_data': {
                        'name': description,
                    },
                    'unit_amount': amount_cents,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{redirect_url}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{redirect_url}?session_id={{CHECKOUT_SESSION_ID}}&cancelled=true",
            metadata=metadata or {},
        )

        logger.info(f"Stripe checkout session created: {session.id}")

        return {
            'session_id': session.id,
            'checkout_url': session.url,
        }

    except stripe.error.StripeError as e:
        logger.error(f'Stripe API error: {e}')
        return None


def get_session(session_id):
    """Retrieve a Stripe Checkout Session by ID.

    In dev mode, returns a fake completed session so polling auto-activates the feature.

    Returns:
        dict with session details on success, None on failure
    """
    # Dev mode: fake sessions are always "complete"
    if _is_dev_mode():
        logger.info(f"[DEV MODE] get_session({session_id}) -> complete")
        return {
            'id': session_id,
            'status': 'complete',
            'payment_status': 'paid',
        }

    _configure_stripe()

    if not stripe.api_key:
        logger.error('STRIPE_SECRET_KEY is not configured')
        return None

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        return {
            'id': session.id,
            'status': session.status,
            'payment_status': session.payment_status,
        }
    except stripe.error.StripeError as e:
        logger.error(f'Stripe get session error: {e}')
        return None


def verify_webhook_signature(payload_body, signature_header):
    """Verify Stripe webhook signature and parse the event.

    In dev mode, parses the JSON payload directly without verification.

    Args:
        payload_body: Raw request body (bytes)
        signature_header: Value of the 'Stripe-Signature' header

    Returns:
        Parsed stripe.Event on success, None on failure
    """
    import json

    # Dev mode: skip signature verification
    if _is_dev_mode():
        logger.info("[DEV MODE] Webhook signature check bypassed")
        try:
            return json.loads(payload_body)
        except Exception:
            return None

    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    if not webhook_secret:
        logger.error('STRIPE_WEBHOOK_SECRET is not configured')
        return None

    if not signature_header:
        logger.warning('Missing Stripe-Signature header')
        return None

    try:
        event = stripe.Webhook.construct_event(
            payload_body, signature_header, webhook_secret
        )
        return event
    except stripe.error.SignatureVerificationError as e:
        logger.error(f'Webhook signature verification failed: {e}')
        return None
    except Exception as e:
        logger.error(f'Webhook parsing error: {e}')
        return None
