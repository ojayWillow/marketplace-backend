"""Stripe payment service for escrow handling."""

import stripe
import os
from datetime import datetime
from app import db
from app.models import Transaction, TaskRequest

# Initialize Stripe with secret key from environment
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Platform fee percentage (10% default)
PLATFORM_FEE_PERCENT = float(os.getenv('PLATFORM_FEE_PERCENT', '10.0'))


class StripeService:
    """Service for handling Stripe payments with escrow."""
    
    @staticmethod
    def calculate_fees(amount_cents):
        """Calculate platform fee and worker amount.
        
        Args:
            amount_cents: Total amount in cents
            
        Returns:
            tuple: (platform_fee_cents, worker_amount_cents)
        """
        platform_fee = int(amount_cents * (PLATFORM_FEE_PERCENT / 100))
        worker_amount = amount_cents - platform_fee
        return platform_fee, worker_amount
    
    @staticmethod
    def create_payment_intent(task_id, payer_id, amount_euros, currency='eur'):
        """Create a Stripe PaymentIntent to hold funds in escrow.
        
        Args:
            task_id: Task ID
            payer_id: User ID of payer (creator)
            amount_euros: Amount in euros (float)
            currency: Currency code (default 'eur')
            
        Returns:
            dict: {
                'transaction': Transaction object,
                'client_secret': Stripe client secret for frontend,
                'payment_intent_id': Stripe PaymentIntent ID
            }
            
        Raises:
            Exception: If Stripe API fails
        """
        # Convert euros to cents
        amount_cents = int(amount_euros * 100)
        
        # Calculate fees
        platform_fee, worker_amount = StripeService.calculate_fees(amount_cents)
        
        # Create PaymentIntent with manual capture (escrow)
        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency.lower(),
            capture_method='manual',  # Don't capture immediately - hold for escrow
            metadata={
                'task_id': task_id,
                'payer_id': payer_id,
                'platform_fee': platform_fee,
            }
        )
        
        # Create transaction record
        transaction = Transaction(
            task_id=task_id,
            payer_id=payer_id,
            amount=amount_cents,
            platform_fee=platform_fee,
            worker_amount=worker_amount,
            currency=currency.upper(),
            stripe_payment_intent_id=payment_intent.id,
            status='pending'
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return {
            'transaction': transaction,
            'client_secret': payment_intent.client_secret,
            'payment_intent_id': payment_intent.id
        }
    
    @staticmethod
    def capture_payment(transaction_id):
        """Capture payment and hold in escrow.
        
        Called after payment authorization succeeds.
        
        Args:
            transaction_id: Transaction ID
            
        Returns:
            Transaction: Updated transaction
            
        Raises:
            Exception: If capture fails
        """
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            raise ValueError('Transaction not found')
        
        if transaction.status != 'pending':
            raise ValueError(f'Cannot capture payment with status {transaction.status}')
        
        # Capture the payment intent
        payment_intent = stripe.PaymentIntent.capture(transaction.stripe_payment_intent_id)
        
        # Update transaction
        transaction.status = 'held'
        transaction.held_at = datetime.utcnow()
        
        # Update task payment status
        task = TaskRequest.query.get(transaction.task_id)
        if task:
            task.payment_status = 'held'
            task.transaction_id = transaction.id
        
        db.session.commit()
        
        return transaction
    
    @staticmethod
    def release_to_worker(transaction_id, payee_id):
        """Release funds from escrow to worker.
        
        Args:
            transaction_id: Transaction ID
            payee_id: Worker user ID
            
        Returns:
            Transaction: Updated transaction
            
        Raises:
            Exception: If release fails
        """
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            raise ValueError('Transaction not found')
        
        if transaction.status != 'held':
            raise ValueError(f'Cannot release payment with status {transaction.status}')
        
        # Update payee if not set
        if not transaction.payee_id:
            transaction.payee_id = payee_id
        
        # For now, we mark as released
        # In production, you'd transfer to worker's Stripe Connect account:
        # transfer = stripe.Transfer.create(
        #     amount=transaction.worker_amount,
        #     currency=transaction.currency.lower(),
        #     destination=worker.stripe_account_id,
        # )
        # transaction.stripe_transfer_id = transfer.id
        
        transaction.status = 'released'
        transaction.released_at = datetime.utcnow()
        
        # Update task payment status
        task = TaskRequest.query.get(transaction.task_id)
        if task:
            task.payment_status = 'released'
        
        db.session.commit()
        
        return transaction
    
    @staticmethod
    def refund_to_creator(transaction_id, amount_cents=None, reason=None):
        """Refund payment to creator.
        
        Args:
            transaction_id: Transaction ID
            amount_cents: Amount to refund in cents (None = full refund)
            reason: Refund reason
            
        Returns:
            Transaction: Updated transaction
            
        Raises:
            Exception: If refund fails
        """
        transaction = Transaction.query.get(transaction_id)
        if not transaction:
            raise ValueError('Transaction not found')
        
        if transaction.status not in ['held', 'pending']:
            raise ValueError(f'Cannot refund payment with status {transaction.status}')
        
        # Default to full refund
        if amount_cents is None:
            amount_cents = transaction.amount
        
        # Create Stripe refund
        refund = stripe.Refund.create(
            payment_intent=transaction.stripe_payment_intent_id,
            amount=amount_cents,
            reason=reason or 'requested_by_customer',
        )
        
        transaction.stripe_refund_id = refund.id
        transaction.refunded_at = datetime.utcnow()
        
        # Update status
        if amount_cents >= transaction.amount:
            transaction.status = 'refunded'
        else:
            transaction.status = 'partially_refunded'
        
        # Update task payment status
        task = TaskRequest.query.get(transaction.task_id)
        if task:
            task.payment_status = transaction.status
        
        db.session.commit()
        
        return transaction
    
    @staticmethod
    def handle_webhook(event):
        """Handle Stripe webhook events.
        
        Args:
            event: Stripe event object
            
        Returns:
            dict: Result of handling
        """
        event_type = event['type']
        
        if event_type == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            # Find transaction and capture
            transaction = Transaction.query.filter_by(
                stripe_payment_intent_id=payment_intent['id']
            ).first()
            
            if transaction and transaction.status == 'pending':
                StripeService.capture_payment(transaction.id)
                return {'status': 'captured'}
        
        elif event_type == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            transaction = Transaction.query.filter_by(
                stripe_payment_intent_id=payment_intent['id']
            ).first()
            
            if transaction:
                transaction.status = 'failed'
                transaction.failure_reason = payment_intent.get('last_payment_error', {}).get('message')
                db.session.commit()
                return {'status': 'failed'}
        
        return {'status': 'ignored'}
