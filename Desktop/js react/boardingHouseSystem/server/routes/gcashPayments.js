import express from 'express';
import { getDB } from '../db/database.js';
import GCashService from '../services/gcashService.js';

const router = express.Router();

/**
 * Initiate a GCash payment
 * POST /api/payments/initiate-gcash
 */
router.post('/initiate-gcash', async (req, res) => {
  try {
    const { paymentId, amount, tenantId, returnUrl, cancelUrl } = req.body;

    if (!paymentId || !amount || !tenantId) {
      return res.status(400).json({ error: 'Missing required fields' });
    }

    const db = getDB();

    // Find the payment
    const payment = db.data.payments.find(p => p.id === paymentId);
    if (!payment) {
      return res.status(404).json({ error: 'Payment not found' });
    }

    // Find the tenant for email
    const tenant = db.data.tenants.find(t => t.id === tenantId);
    if (!tenant) {
      return res.status(404).json({ error: 'Tenant not found' });
    }

    // Generate reference number
    const referenceNumber = GCashService.generateReferenceNumber();

    // Update payment with reference number
    payment.referenceNumber = referenceNumber;
    payment.gcashInitiated = true;
    payment.gcashInitiatedAt = new Date().toISOString();
    await db.write();

    // Call GCash API to initiate payment
    const gcashResponse = await GCashService.initiatePayment({
      referenceNumber,
      amount,
      currency: 'PHP',
      description: `Boarding House Payment - ${payment.month}`,
      customerEmail: tenant.email,
      customerPhone: tenant.phone,
      returnUrl: returnUrl || `${process.env.FRONTEND_URL || 'http://localhost:5173'}/payment-success`,
      cancelUrl: cancelUrl || `${process.env.FRONTEND_URL || 'http://localhost:5173'}/payment-cancelled`
    });

    if (!gcashResponse.success) {
      return res.status(400).json({ error: gcashResponse.error });
    }

    res.json({
      success: true,
      transactionId: gcashResponse.transactionId,
      paymentLink: gcashResponse.paymentLink,
      qrCode: gcashResponse.qrCode,
      referenceNumber: referenceNumber,
      expiresAt: gcashResponse.expiresAt,
      amount: amount,
      tenantName: tenant.name
    });

  } catch (error) {
    console.error('Error initiating GCash payment:', error);
    res.status(500).json({ error: 'Failed to initiate payment' });
  }
});

/**
 * Check GCash payment status
 * GET /api/payments/gcash-status/:referenceNumber
 */
router.get('/gcash-status/:referenceNumber', async (req, res) => {
  try {
    const { referenceNumber } = req.params;
    const db = getDB();

    // Find payment by reference number
    const payment = db.data.payments.find(p => p.referenceNumber === referenceNumber);
    if (!payment) {
      return res.status(404).json({ error: 'Payment not found' });
    }

    // If we have a transaction ID from webhook, get fresh status
    if (payment.transactionId) {
      const statusResponse = await GCashService.getPaymentStatus(payment.transactionId);
      
      if (statusResponse.success) {
        return res.json({
          success: true,
          status: statusResponse.status,
          referenceNumber: referenceNumber,
          amount: payment.amount,
          tenantName: payment.tenantName,
          month: payment.month,
          completedAt: statusResponse.completedAt
        });
      }
    }

    // Return current local status
    res.json({
      success: true,
      status: payment.status,
      referenceNumber: referenceNumber,
      amount: payment.amount,
      tenantName: payment.tenantName,
      month: payment.month,
      completedAt: payment.paidDate
    });

  } catch (error) {
    console.error('Error checking GCash status:', error);
    res.status(500).json({ error: 'Failed to check payment status' });
  }
});

/**
 * Handle GCash payment return (after user completes payment)
 * GET /api/payments/gcash-return?reference=xxxxx
 */
router.get('/gcash-return', async (req, res) => {
  try {
    const { reference } = req.query;

    if (!reference) {
      return res.status(400).json({ error: 'Missing reference number' });
    }

    const db = getDB();
    const payment = db.data.payments.find(p => p.referenceNumber === reference);

    if (!payment) {
      return res.status(404).json({ error: 'Payment not found' });
    }

    // If payment has transaction ID, verify status with GCash
    if (payment.transactionId) {
      const statusResponse = await GCashService.getPaymentStatus(payment.transactionId);
      
      return res.json({
        success: true,
        paymentStatus: statusResponse.status,
        referenceNumber: reference,
        message: statusResponse.status === 'completed' 
          ? 'Payment completed successfully!' 
          : 'Payment is being processed. Please wait for confirmation.'
      });
    }

    // Return pending status if no transaction ID yet
    res.json({
      success: true,
      paymentStatus: 'pending',
      referenceNumber: reference,
      message: 'Payment is being processed. You will receive a confirmation shortly.'
    });

  } catch (error) {
    console.error('Error handling payment return:', error);
    res.status(500).json({ error: 'Error processing payment return' });
  }
});

/**
 * Request refund for a payment
 * POST /api/payments/:id/refund
 */
router.post('/:id/refund', async (req, res) => {
  try {
    const { id } = req.params;
    const { amount, reason } = req.body;

    const db = getDB();
    const payment = db.data.payments.find(p => p.id === id);

    if (!payment) {
      return res.status(404).json({ error: 'Payment not found' });
    }

    if (payment.status !== 'paid') {
      return res.status(400).json({ error: 'Can only refund paid payments' });
    }

    if (!payment.transactionId) {
      return res.status(400).json({ error: 'No GCash transaction to refund' });
    }

    // Request refund from GCash
    const refundResponse = await GCashService.createRefund(
      payment.transactionId,
      amount || payment.amount
    );

    if (!refundResponse.success) {
      return res.status(400).json({ error: refundResponse.error });
    }

    // Update payment record
    payment.status = 'refunded';
    payment.refundId = refundResponse.refundId;
    payment.refundAmount = refundResponse.amount;
    payment.refundReason = reason || 'User requested refund';
    payment.refundedAt = new Date().toISOString();

    await db.write();

    res.json({
      success: true,
      message: 'Refund processed successfully',
      refundId: refundResponse.refundId,
      amount: refundResponse.amount,
      status: refundResponse.status
    });

  } catch (error) {
    console.error('Error processing refund:', error);
    res.status(500).json({ error: 'Failed to process refund' });
  }
});

export default router;
