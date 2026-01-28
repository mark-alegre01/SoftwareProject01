import express from 'express';
import { getDB } from '../db/database.js';
import GCashService from '../services/gcashService.js';

const router = express.Router();

/**
 * GCash Webhook Handler
 * Receives payment status updates from GCash
 * 
 * Expected webhook payload:
 * {
 *   event: "payment.completed" | "payment.failed" | "payment.cancelled",
 *   data: {
 *     id: "transaction_id",
 *     status: "completed",
 *     referenceNumber: "ORD-20250112-ABC123",
 *     amount: 500000,  // in cents
 *     currency: "PHP",
 *     completedAt: "2025-01-12T10:30:00Z"
 *   }
 * }
 */
router.post('/gcash', express.raw({ type: 'application/json' }), (req, res) => {
  try {
    // Get signature from headers
    const signature = req.headers['x-signature'];

    if (!signature) {
      return res.status(400).json({ error: 'Missing signature' });
    }

    // Verify webhook signature
    if (!GCashService.verifyWebhookSignature(req.body.toString(), signature)) {
      console.warn('Invalid GCash webhook signature');
      return res.status(401).json({ error: 'Invalid signature' });
    }

    const body = JSON.parse(req.body.toString());
    const { event, data } = body;

    console.log(`[GCash Webhook] Event: ${event}`, data);

    // Route based on event type
    if (event === 'payment.completed') {
      handlePaymentCompleted(data);
    } else if (event === 'payment.failed') {
      handlePaymentFailed(data);
    } else if (event === 'payment.cancelled') {
      handlePaymentCancelled(data);
    }

    // Always return 200 immediately to acknowledge receipt
    // Process the actual update asynchronously
    res.status(200).json({ received: true });

  } catch (error) {
    console.error('Webhook Error:', error);
    // Return 200 anyway to prevent retries for parse errors
    res.status(200).json({ error: 'Webhook received but processing failed' });
  }
});

/**
 * Handle successful payment
 */
function handlePaymentCompleted(data) {
  try {
    const db = getDB();

    // Find payment by reference number
    const paymentIndex = db.data.payments.findIndex(
      p => p.referenceNumber === data.referenceNumber
    );

    if (paymentIndex === -1) {
      console.warn(`Payment not found for reference: ${data.referenceNumber}`);
      return;
    }

    // Update payment status
    db.data.payments[paymentIndex].status = 'paid';
    db.data.payments[paymentIndex].paymentMethod = 'gcash';
    db.data.payments[paymentIndex].paidDate = new Date(data.completedAt).toISOString().split('T')[0];
    db.data.payments[paymentIndex].transactionId = data.id;
    db.data.payments[paymentIndex].gcashAmount = data.amount / 100; // Convert from cents
    db.data.payments[paymentIndex].webhookReceived = true;
    db.data.payments[paymentIndex].webhookReceivedAt = new Date().toISOString();

    db.write();

    console.log(`✅ Payment marked as paid - Reference: ${data.referenceNumber}, Transaction: ${data.id}`);

    // TODO: Send confirmation email to boarder
    // sendPaymentConfirmationEmail(boarder, paymentData);

  } catch (error) {
    console.error('Error handling payment completion:', error);
  }
}

/**
 * Handle failed payment
 */
function handlePaymentFailed(data) {
  try {
    const db = getDB();

    const paymentIndex = db.data.payments.findIndex(
      p => p.referenceNumber === data.referenceNumber
    );

    if (paymentIndex === -1) {
      console.warn(`Payment not found for reference: ${data.referenceNumber}`);
      return;
    }

    db.data.payments[paymentIndex].status = 'failed';
    db.data.payments[paymentIndex].transactionId = data.id;
    db.data.payments[paymentIndex].failureReason = data.failureReason || 'Unknown error';
    db.data.payments[paymentIndex].webhookReceived = true;
    db.data.payments[paymentIndex].webhookReceivedAt = new Date().toISOString();

    db.write();

    console.log(`❌ Payment failed - Reference: ${data.referenceNumber}, Reason: ${data.failureReason}`);

    // TODO: Send failure notification to boarder

  } catch (error) {
    console.error('Error handling payment failure:', error);
  }
}

/**
 * Handle cancelled payment
 */
function handlePaymentCancelled(data) {
  try {
    const db = getDB();

    const paymentIndex = db.data.payments.findIndex(
      p => p.referenceNumber === data.referenceNumber
    );

    if (paymentIndex === -1) {
      console.warn(`Payment not found for reference: ${data.referenceNumber}`);
      return;
    }

    db.data.payments[paymentIndex].status = 'cancelled';
    db.data.payments[paymentIndex].transactionId = data.id;
    db.data.payments[paymentIndex].webhookReceived = true;
    db.data.payments[paymentIndex].webhookReceivedAt = new Date().toISOString();

    db.write();

    console.log(`⛔ Payment cancelled - Reference: ${data.referenceNumber}`);

  } catch (error) {
    console.error('Error handling payment cancellation:', error);
  }
}

export default router;
