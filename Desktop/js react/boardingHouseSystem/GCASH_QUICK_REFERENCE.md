# GCash Integration - Quick Reference Guide

## 🚀 Quick Start Checklist

```
[ ] 1. Get GCash Merchant Account
[ ] 2. Obtain API credentials from GCash Dashboard
[ ] 3. Run: node setup-gcash.js
[ ] 4. Configure webhook in GCash Dashboard
[ ] 5. Test with sandbox environment
[ ] 6. Deploy to production
[ ] 7. Update webhook URL in GCash for production
```

---

## 📱 User Journey - Making a Payment

### 1️⃣ Boarder Opens Payment Page
```
URL: http://localhost:5173/make-payment
```

### 2️⃣ Sees Payment Details
- Amount: ₱5,000
- Month: January 2025
- Due Date: 2025-01-05
- Status: Pending

### 3️⃣ Clicks "Pay with GCash"
```
POST /api/gcash/initiate-gcash
{
  "paymentId": "1234567890",
  "amount": 5000,
  "tenantId": "tenant_123"
}
```

### 4️⃣ Receives Payment Link
```json
{
  "paymentLink": "https://gcash.com/pay/abc123...",
  "referenceNumber": "ORD-20250112-ABC123",
  "qrCode": "data:image/png;base64...",
  "expiresAt": "2025-01-12T11:20:00Z"
}
```

### 5️⃣ Redirected to GCash
```
Browser redirects to: https://gcash.com/pay/abc123...
```

### 6️⃣ Completes Payment in GCash App
- Opens GCash app
- Confirms transaction
- Enters PIN
- Payment successful ✅

### 7️⃣ Webhook Notification Received
```json
POST /api/webhooks/gcash
{
  "event": "payment.completed",
  "data": {
    "id": "GCASH-1234567890",
    "status": "completed",
    "referenceNumber": "ORD-20250112-ABC123",
    "amount": 500000,
    "completedAt": "2025-01-12T10:25:00Z"
  }
}
```

### 8️⃣ Database Updated Automatically
```javascript
// Payment record updated to:
{
  status: "paid",
  transactionId: "GCASH-1234567890",
  paidDate: "2025-01-12",
  paymentMethod: "gcash",
  webhookReceived: true
}
```

### 9️⃣ User Sees Confirmation
```
✅ Payment completed!
Transaction ID: GCASH-1234567890
Reference: ORD-20250112-ABC123
Amount: ₱5,000.00
Date: Jan 12, 2025
```

### 🔟 Landlord Sees Updated Status
```
Tenant: John Doe
Payment: January 2025
Amount: ₱5,000
Status: PAID ✅
Paid Date: Jan 12, 2025
Method: GCash
Transaction: GCASH-1234567890
```

---

## 💻 Developer Reference

### Frontend - Initiate Payment

```javascript
// From MakePaymentPage.jsx
const handleInitiateGCashPayment = async () => {
  const response = await fetch('/api/gcash/initiate-gcash', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      paymentId: tenantPayment.id,
      amount: tenantPayment.amount,
      tenantId: user.tenantId
    })
  });

  const data = await response.json();
  window.location.href = data.paymentLink; // Redirect to GCash
};
```

### Backend - GCash Service

```javascript
// From gcashService.js
import GCashService from './services/gcashService.js';

// Initiate payment
const result = await GCashService.initiatePayment({
  referenceNumber: 'ORD-20250112-ABC123',
  amount: 5000,
  currency: 'PHP',
  description: 'Boarding House Payment - January 2025',
  customerEmail: 'john@example.com',
  customerPhone: '09123456789',
  returnUrl: 'http://localhost:5173/payment-success',
  cancelUrl: 'http://localhost:5173/payment-cancelled'
});

// Check status
const status = await GCashService.getPaymentStatus('GCASH-1234567890');

// Verify webhook
const isValid = GCashService.verifyWebhookSignature(payload, signature);

// Create refund
const refund = await GCashService.createRefund('GCASH-1234567890', 5000);
```

### Backend - Webhook Handler

```javascript
// From webhooks.js
router.post('/gcash', (req, res) => {
  const signature = req.headers['x-signature'];
  
  // Verify signature
  if (!GCashService.verifyWebhookSignature(req.body, signature)) {
    return res.status(401).json({ error: 'Invalid signature' });
  }

  const { event, data } = JSON.parse(req.body);

  if (event === 'payment.completed') {
    // Update database: status = 'paid'
    // Store transaction ID
    // Send confirmation email
  } else if (event === 'payment.failed') {
    // Update database: status = 'failed'
    // Send failure notification
  }

  res.status(200).json({ received: true });
});
```

---

## 🔧 Configuration Files

### .env (Create this)
```env
# GCash Configuration
GCASH_API_KEY=pk_test_1234567890
GCASH_SECRET_KEY=sk_test_0987654321
GCASH_MERCHANT_ID=merchant_12345
GCASH_API_ENDPOINT=https://sandbox-api.gcash.com/v1
GCASH_WEBHOOK_SECRET=whsec_test_abc123

# Application URLs
FRONTEND_URL=http://localhost:5173
BACKEND_URL=http://localhost:5000

# Server
PORT=5000
NODE_ENV=development
```

### .env.example (Template - Already provided)
```env
GCASH_API_KEY=test_key_your_api_key_here
GCASH_SECRET_KEY=test_secret_your_secret_here
GCASH_MERCHANT_ID=your_merchant_id
GCASH_API_ENDPOINT=https://sandbox-api.gcash.com/v1
GCASH_WEBHOOK_SECRET=your_webhook_secret
FRONTEND_URL=http://localhost:5173
BACKEND_URL=http://localhost:5000
```

---

## 🧪 Testing Checklist

### Unit Testing
```bash
# Test signature verification
GCashService.verifyWebhookSignature(payload, signature)

# Test reference number generation
const ref = GCashService.generateReferenceNumber()
// Output: ORD-20250112-ABC123

# Test amount formatting
GCashService.formatAmount(5000)
// Output: 500000 (in cents)
```

### Integration Testing
```javascript
// 1. Test payment initiation
POST /api/gcash/initiate-gcash
{
  "paymentId": "test123",
  "amount": 5000,
  "tenantId": "test_tenant"
}

// 2. Test webhook delivery
POST /api/webhooks/gcash
X-Signature: (calculated signature)
{
  "event": "payment.completed",
  "data": { ... }
}

// 3. Verify payment status updated
GET /api/gcash/gcash-status/ORD-20250112-ABC123

// 4. Check database
db.data.payments.find(p => p.status === 'paid')
```

### End-to-End Testing
```
1. User clicks "Pay with GCash"
2. Redirected to GCash payment page
3. Complete payment in GCash app
4. Webhook received and processed
5. Check payment status updated to "paid"
6. Verify payment shows in landlord dashboard
7. Check email confirmation sent
```

---

## 🐛 Common Issues & Solutions

### Issue: "Invalid signature"
**Cause**: Webhook secret mismatch  
**Solution**: Verify GCASH_WEBHOOK_SECRET matches GCash dashboard

### Issue: "Payment not found"
**Cause**: Reference number doesn't match  
**Solution**: Ensure payment created before GCash initiation

### Issue: "API key invalid"
**Cause**: Wrong or expired credentials  
**Solution**: Get new credentials from GCash dashboard

### Issue: "Payment link expired"
**Cause**: User waited too long  
**Solution**: Payment link expires after 1 hour, user must reinitiate

### Issue: "Webhook not received"
**Cause**: URL not accessible or firewall blocking  
**Solution**: Use ngrok for local testing, check firewall rules

---

## 📊 Monitoring Checklist

### Daily
- [ ] Check webhook delivery history in GCash dashboard
- [ ] Monitor failed payments in database
- [ ] Review payment logs

### Weekly
- [ ] Reconcile GCash transactions with database
- [ ] Check for failed webhook deliveries
- [ ] Review error logs

### Monthly
- [ ] Generate payment reconciliation report
- [ ] Analyze payment methods usage
- [ ] Plan for any needed adjustments

---

## 🔒 Security Checklist

- [ ] All API keys in `.env` (never in code)
- [ ] HTTPS enabled in production
- [ ] Webhook signature verification enabled
- [ ] Database access restricted
- [ ] Logs don't contain sensitive data
- [ ] Webhook retries configured
- [ ] Rate limiting implemented
- [ ] API key rotation scheduled

---

## 🚀 Deployment Checklist

### Before Going Live
- [ ] Test in sandbox environment
- [ ] Get production GCash credentials
- [ ] Update `.env` with production values
- [ ] Update webhook URL to production domain
- [ ] Enable HTTPS on production server
- [ ] Test full payment flow in production
- [ ] Set up monitoring and alerts
- [ ] Create runbook for support team
- [ ] Document refund process
- [ ] Train staff on new payment system

### After Going Live
- [ ] Monitor webhook deliveries
- [ ] Check for payment errors
- [ ] Verify payment confirmations being sent
- [ ] Monitor system performance
- [ ] Review customer feedback

---

## 📞 Quick Support Links

| Issue | Link |
|-------|------|
| GCash API Docs | https://merchant.gcash.com/docs |
| Webhook Security | https://merchant.gcash.com/docs/webhooks |
| Sandbox Testing | https://merchant.gcash.com/docs/sandbox |
| GCash Status | https://status.gcash.com |

---

## 💡 Pro Tips

1. **Always verify webhook signatures** - Protects against unauthorized requests
2. **Store both reference and transaction IDs** - Enables proper reconciliation
3. **Implement retry logic** - Handles network failures gracefully
4. **Log webhook deliveries** - Helps with debugging
5. **Set up email alerts** - Know immediately when payments fail
6. **Test refunds regularly** - Ensure refund flow works
7. **Monitor webhook delivery** - Catch configuration issues early
8. **Document your process** - Help future developers understand flow

---

## 📋 File Structure

```
boardingHouseSystem/
├── server/
│   ├── services/
│   │   └── gcashService.js          ← GCash API wrapper
│   ├── routes/
│   │   ├── gcashPayments.js         ← Payment endpoints
│   │   └── webhooks.js              ← Webhook handler
│   └── index.js                     ← Updated with GCash routes
├── client/
│   └── src/pages/
│       └── MakePaymentPage.jsx      ← Updated UI
├── .env                             ← Your configuration
├── .env.example                     ← Configuration template
├── setup-gcash.js                   ← Setup script
├── GCASH_INTEGRATION.md             ← Full documentation
└── GCASH_IMPLEMENTATION_SUMMARY.md  ← This summary
```

---

## ✅ You're All Set!

Everything is configured and ready to integrate with GCash. Follow the setup steps in `GCASH_INTEGRATION.md` to get your merchant credentials and configure the webhook.

**Questions?** Check GCASH_INTEGRATION.md for detailed documentation!

