# 💳 Stripe Escrow Payment System

## Overview
This marketplace uses Stripe with **escrow functionality** to protect both creators and workers.

## How It Works

### Payment Flow
```
1. Creator posts task with budget
2. Creator pays upfront → Funds held in escrow (not captured yet)
3. Worker accepts and completes task
4. Creator confirms completion
5. Funds released to worker (platform takes 10% fee)
```

### Dispute Flow
```
Dispute filed → Admin resolves:
  - Refund: Money back to creator
  - Pay Worker: Money to worker
  - Partial: Split the amount
```

---

## Setup Instructions

### 1. Install Stripe Python SDK
```bash
pip install stripe
```

### 2. Set Environment Variables
Add to your `.env` file:
```bash
# Stripe Keys (get from https://dashboard.stripe.com/apikeys)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...  # Get from webhook setup

# Platform Fee (percentage)
PLATFORM_FEE_PERCENT=10.0
```

### 3. Register Payment Blueprint
In `app/__init__.py`, add:
```python
from app.routes.payments import payments_bp
app.register_blueprint(payments_bp, url_prefix='/api/payments')
```

### 4. Update Models Import
In `app/models/__init__.py`, add:
```python
from app.models.transaction import Transaction
```

### 5. Run Database Migration
```bash
flask db migrate -m "Add payment tables"
flask db upgrade
```

### 6. Setup Stripe Webhook
1. Go to https://dashboard.stripe.com/webhooks
2. Add endpoint: `https://your-domain.com/api/payments/webhook`
3. Select events:
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
4. Copy webhook signing secret to `.env`

---

## API Endpoints

### Create Payment (Escrow)
```http
POST /api/payments/tasks/{task_id}/pay
Authorization: Bearer {token}
Content-Type: application/json

{
  "amount": 50.00
}

Response:
{
  "client_secret": "pi_xxx_secret_xxx",
  "transaction_id": 1,
  "amount": 50.00,
  "platform_fee": 5.00,
  "worker_amount": 45.00
}
```

### Release Payment to Worker
```http
POST /api/payments/tasks/{task_id}/release-payment
Authorization: Bearer {token}

Response:
{
  "message": "Payment released to worker",
  "transaction": {...}
}
```

### Refund to Creator (Admin Only)
```http
POST /api/payments/tasks/{task_id}/refund
Authorization: Bearer {token}
Content-Type: application/json

{
  "amount": 25.00,  // Optional, defaults to full refund
  "reason": "Task cancelled"
}

Response:
{
  "message": "Refund processed",
  "transaction": {...}
}
```

### Get Transactions
```http
GET /api/payments/transactions?status=held
Authorization: Bearer {token}

Response:
{
  "transactions": [...],
  "total": 10
}
```

### Get Transaction Details
```http
GET /api/payments/transactions/{id}
Authorization: Bearer {token}

Response:
{
  "transaction": {...}
}
```

### Get Stripe Config (Public)
```http
GET /api/payments/config

Response:
{
  "publishable_key": "pk_test_...",
  "platform_fee_percent": "10.0"
}
```

---

## Database Schema

### Transaction Model
```python
id: int
task_id: int (FK)
payer_id: int (FK)  # Creator
payee_id: int (FK)  # Worker
amount: int  # In cents
platform_fee: int  # In cents
worker_amount: int  # In cents
currency: str
stripe_payment_intent_id: str
stripe_transfer_id: str
stripe_refund_id: str
status: str  # pending, held, released, refunded, partially_refunded, failed
created_at: datetime
held_at: datetime
released_at: datetime
refunded_at: datetime
```

### TaskRequest Updates
```python
payment_required: bool
payment_status: str  # not_required, pending, held, released, refunded
transaction_id: int (FK)
```

---

## Payment Statuses

### Transaction Status
- `pending` - Payment being processed by Stripe
- `held` - Funds captured and held in escrow
- `released` - Funds transferred to worker
- `refunded` - Full refund to creator
- `partially_refunded` - Partial refund processed
- `failed` - Payment failed

### Task Payment Status
- `not_required` - Task doesn't require upfront payment
- `pending` - Waiting for payment authorization
- `held` - Payment in escrow
- `released` - Payment sent to worker
- `refunded` - Payment returned to creator

---

## Integration with Disputes

In `app/routes/disputes.py`, when admin resolves:

```python
from app.services.stripe_service import StripeService

if resolution == 'refund':
    if task.transaction_id:
        StripeService.refund_to_creator(task.transaction_id)

elif resolution == 'pay_worker':
    if task.transaction_id:
        StripeService.release_to_worker(task.transaction_id, task.assigned_to_id)

elif resolution == 'partial':
    if task.transaction_id:
        transaction = Transaction.query.get(task.transaction_id)
        half_amount = transaction.amount // 2
        StripeService.refund_to_creator(task.transaction_id, amount_cents=half_amount)
        # Worker gets the other half automatically (already captured)
```

---

## Testing

### Test Card Numbers
Stripe provides test cards:
- Success: `4242 4242 4242 4242`
- Declined: `4000 0000 0000 0002`
- Requires authentication: `4000 0025 0000 3155`

### Test Webhook Locally
Use Stripe CLI:
```bash
stripe listen --forward-to localhost:5000/api/payments/webhook
stripe trigger payment_intent.succeeded
```

---

## Production Checklist

- [ ] Replace test keys with live keys
- [ ] Setup Stripe Connect for worker payouts
- [ ] Configure webhook for production domain
- [ ] Enable 3D Secure authentication
- [ ] Setup proper error monitoring
- [ ] Test refund flows
- [ ] Verify platform fee calculation
- [ ] Add transaction receipts/invoices

---

## Security Notes

1. **Never expose `STRIPE_SECRET_KEY`** in frontend
2. **Always validate webhook signatures** (already implemented)
3. **Store amounts in cents** to avoid float errors
4. **Use PaymentIntent** (not Charges) for best practices
5. **Manual capture** enables escrow functionality

---

## Support

For Stripe questions:
- Docs: https://stripe.com/docs
- Support: https://support.stripe.com
