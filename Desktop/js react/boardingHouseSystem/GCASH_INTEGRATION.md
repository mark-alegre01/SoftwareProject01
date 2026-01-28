# GCash Payment Integration Guide

This document explains how the GCash payment integration works in your Boarding House System.

## Overview

The system now supports real GCash payment integration through a webhook-based architecture that handles:
- Payment initiation with automatic link generation
- Real-time payment status updates via webhooks
- Secure signature verification
- Refund processing
- Transaction tracking and reconciliation

## Architecture

### Files Structure

```
server/
  ├── services/
  │   └── gcashService.js          # GCash API wrapper & utilities
  ├── routes/
  │   ├── gcashPayments.js         # GCash payment endpoints
  │   └── webhooks.js              # GCash webhook handler
  └── index.js                      # Updated with new routes

client/
  └── src/pages/
      └── MakePaymentPage.jsx      # Updated payment UI with GCash integration
```

## Setup Instructions

### 1. Get GCash Merchant Credentials

1. Register a merchant account at [GCash Merchant](https://merchant.gcash.com)
2. Complete KYC verification
3. Obtain these credentials:
   - API Key
   - Secret Key
   - Merchant ID
   - Webhook Secret

### 2. Configure Environment Variables

Create a `.env` file in the root directory (copy from `.env.example`):

```bash
# GCash Configuration
GCASH_API_KEY=your_actual_api_key
GCASH_SECRET_KEY=your_actual_secret_key
GCASH_MERCHANT_ID=your_merchant_id
GCASH_API_ENDPOINT=https://api.gcash.com/v1  # or sandbox for testing
GCASH_WEBHOOK_SECRET=your_webhook_secret

# Application URLs
FRONTEND_URL=http://localhost:5173
BACKEND_URL=http://localhost:5000
```

### 3. Configure Webhook in GCash Dashboard

1. Log in to [GCash Merchant Dashboard](https://merchant.gcash.com)
2. Go to **Settings → Webhooks**
3. Add webhook endpoint:
   ```
   URL: https://yourdomain.com/api/webhooks/gcash
   Events: payment.completed, payment.failed, payment.cancelled
   Secret: (use GCASH_WEBHOOK_SECRET)
   ```

### 4. Testing with Sandbox

For development, use the sandbox environment:

```env
GCASH_API_ENDPOINT=https://sandbox-api.gcash.com/v1
```

## API Endpoints

### Payment Initiation

**POST** `/api/gcash/initiate-gcash`

Initiates a GCash payment and returns a payment link.

**Request Body:**
```json
{
  "paymentId": "payment_123",
  "amount": 5000,
  "tenantId": "tenant_456"
}
```

**Response:**
```json
{
  "success": true,
  "transactionId": "GCASH-1234567890",
  "paymentLink": "https://gcash.com/pay/...",
  "qrCode": "data:image/png;base64,...",
  "referenceNumber": "ORD-20250112-ABC123",
  "expiresAt": "2025-01-12T10:30:00Z",
  "amount": 5000,
  "tenantName": "John Doe"
}
```

### Check Payment Status

**GET** `/api/gcash/gcash-status/:referenceNumber`

Check the current status of a payment.

**Response:**
```json
{
  "success": true,
  "status": "completed|pending|failed",
  "referenceNumber": "ORD-20250112-ABC123",
  "amount": 5000,
  "tenantName": "John Doe",
  "month": "January 2025",
  "completedAt": "2025-01-12T10:25:00Z"
}
```

### Webhook Endpoint

**POST** `/api/webhooks/gcash`

Receives payment status updates from GCash. The webhook automatically updates payment records.

**Expected Webhook Payload:**
```json
{
  "event": "payment.completed",
  "data": {
    "id": "GCASH-1234567890",
    "status": "completed",
    "referenceNumber": "ORD-20250112-ABC123",
    "amount": 500000,
    "currency": "PHP",
    "completedAt": "2025-01-12T10:25:00Z"
  }
}
```

### Request Refund

**POST** `/api/payments/:id/refund`

Request a refund for a completed payment.

**Request Body:**
```json
{
  "amount": 5000,
  "reason": "Customer requested refund"
}
```

## Payment Flow

### 1. Boarder Initiates Payment

```
Boarder clicks "Pay with GCash" on MakePaymentPage
         ↓
Frontend calls POST /api/gcash/initiate-gcash
         ↓
Backend generates reference number
         ↓
Backend calls GCash API to create payment request
         ↓
GCash returns payment link & QR code
         ↓
Frontend redirects to GCash payment link
```

### 2. Boarder Completes Payment

```
Boarder in GCash app
         ↓
Confirms payment details
         ↓
Enters PIN
         ↓
Payment processed by GCash
```

### 3. Webhook Notification

```
GCash sends POST to /api/webhooks/gcash
         ↓
Backend verifies webhook signature
         ↓
Backend updates payment status to "paid"
         ↓
Stores GCash transaction ID
         ↓
Returns 200 OK to GCash
         ↓
(Optional) Send email confirmation to boarder
```

### 4. Confirmation Page

```
Frontend redirects to payment success page
         ↓
Checks payment status via GET /api/gcash/gcash-status
         ↓
Displays success message
         ↓
Shows transaction details
```

## Security Features

### 1. Webhook Signature Verification

Every webhook from GCash includes an `X-Signature` header containing an HMAC-SHA256 signature.

The backend verifies:
```javascript
const signature = crypto
  .createHmac('sha256', GCASH_SECRET_KEY)
  .update(JSON.stringify(payload))
  .digest('hex');

const isValid = signature === headerSignature;
```

### 2. HTTPS Enforcement

Always use HTTPS in production:
- Webhook endpoints must be HTTPS
- API keys should never be transmitted over HTTP
- Store keys in environment variables, never in code

### 3. Idempotency

Webhook handlers check if payment is already processed to prevent duplicate updates.

## Database Schema Update

Payments now include GCash-specific fields:

```javascript
{
  id: "payment_123",
  tenantId: "tenant_456",
  amount: 5000,
  month: "January 2025",
  status: "paid",                    // pending, paid, failed, cancelled, refunded
  paymentMethod: "gcash",
  
  // GCash fields
  referenceNumber: "ORD-20250112-ABC123",  // Your reference
  transactionId: "GCASH-1234567890",       // GCash reference
  gcashAmount: 5000,
  gcashInitiated: true,
  gcashInitiatedAt: "2025-01-12T10:20:00Z",
  
  // Webhook fields
  webhookReceived: true,
  webhookReceivedAt: "2025-01-12T10:25:00Z",
  
  // Dates
  paidDate: "2025-01-12",
  createdAt: "2025-01-12T10:10:00Z",
  
  // Refund fields
  refundId: "REFUND-123",
  refundAmount: 5000,
  refundReason: "Customer request",
  refundedAt: "2025-01-13T14:30:00Z"
}
```

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Invalid signature` | Webhook secret mismatch | Verify GCASH_WEBHOOK_SECRET matches GCash dashboard |
| `API key invalid` | Expired or incorrect key | Check GCASH_API_KEY in .env |
| `Payment not found` | Reference number doesn't exist | Ensure payment record created before GCash call |
| `Payment link expired` | User took too long | Link expires after 1 hour, reinitiate payment |

### Retry Logic

The system automatically retries failed webhook deliveries. GCash will retry webhooks:
- First retry: 30 seconds after initial attempt
- Second retry: 5 minutes later
- Third retry: 30 minutes later
- Final retry: 24 hours later

## Testing

### Test with Sandbox

1. Update `.env`:
```env
GCASH_API_ENDPOINT=https://sandbox-api.gcash.com/v1
```

2. Use sandbox GCash credentials

3. Test payment flow:
   - Initiate payment
   - Receive test payment link
   - Simulate payment completion in sandbox

### Webhook Testing with ngrok

For local webhook testing:

```bash
# Install ngrok (if not already)
# https://ngrok.com/download

# Start ngrok
ngrok http 5000

# Note the forwarding URL: https://xxxx-xx-xxx-xx.ngrok-free.app

# Update GCash webhook URL to:
https://xxxx-xx-xxx-xx.ngrok-free.app/api/webhooks/gcash

# Run your app
npm run dev

# Trigger test webhook from GCash sandbox dashboard
```

## Monitoring

### Check Webhook Logs

View webhook delivery history in GCash Merchant Dashboard:
- **Settings → Webhooks → Delivery History**
- Filter by status (success, failed, pending)
- View request/response details
- Manually retry failed deliveries

### Monitor Payments

Check payment records in database (`server/db/db.json`):

```javascript
// Find pending payments
db.data.payments.filter(p => p.status === 'pending')

// Find failed webhooks
db.data.payments.filter(p => !p.webhookReceived && p.gcashInitiated)

// Find refunded payments
db.data.payments.filter(p => p.status === 'refunded')
```

## Production Checklist

- [ ] Move from sandbox to production API endpoint
- [ ] Update GCASH_* credentials with production values
- [ ] Configure HTTPS certificate for webhook endpoint
- [ ] Set up SSL/TLS on your domain
- [ ] Configure production URLs in .env
- [ ] Test full payment flow in production
- [ ] Set up email notifications for confirmations
- [ ] Configure automated reconciliation reports
- [ ] Monitor webhook delivery in dashboard
- [ ] Set up alerting for failed payments
- [ ] Document refund process for support team
- [ ] Create user documentation
- [ ] Set up payment reconciliation schedule

## Support & Resources

- **GCash Merchant API Docs**: https://merchant.gcash.com/docs
- **Webhook Security**: https://merchant.gcash.com/docs/webhooks
- **Testing Guide**: https://merchant.gcash.com/docs/sandbox
- **Support Email**: support@gcash.com

## Troubleshooting

### Webhook Not Received

1. Check GCash dashboard for webhook delivery history
2. Verify webhook URL is correct and publicly accessible
3. Ensure HTTPS is enabled
4. Check firewall/security group allows GCash IPs
5. Review error logs in delivery history
6. Manually retry webhook from dashboard

### Payment Status Not Updating

1. Verify webhook signature verification passing
2. Check if webhook event was received (check logs)
3. Confirm reference number exists in database
4. Check payment status in GCash dashboard
5. Manually call GET status endpoint to refresh

### Reference Number Collision

The system generates unique reference numbers using:
```javascript
`ORD-${YYYYMMDD}-${RANDOM}`
```

This provides ~4 billion combinations per day. If collision occurs:
1. Catch in signature verification
2. Reject duplicate reference
3. Generate new reference
4. Retry payment initiation

## Version History

- **v1.0** (Jan 2025) - Initial GCash webhook integration
  - Payment initiation
  - Webhook handling
  - Signature verification
  - Refund support
