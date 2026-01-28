import axios from 'axios';

// GCash API Configuration
const GCASH_CONFIG = {
  // Replace with your actual GCash merchant credentials
  API_KEY: process.env.GCASH_API_KEY || 'test_key_your_api_key_here',
  SECRET_KEY: process.env.GCASH_SECRET_KEY || 'test_secret_your_secret_here',
  MERCHANT_ID: process.env.GCASH_MERCHANT_ID || 'your_merchant_id',
  API_ENDPOINT: process.env.GCASH_API_ENDPOINT || 'https://sandbox-api.gcash.com/v1', // Sandbox for testing
  WEBHOOK_SECRET: process.env.GCASH_WEBHOOK_SECRET || 'your_webhook_secret'
};

/**
 * GCash Service - Handles all GCash API interactions
 */
class GCashService {
  
  /**
   * Initialize a GCash payment request
   * @param {Object} paymentData - Payment details
   * @returns {Promise<Object>} - GCash payment response with payment link
   */
  static async initiatePayment(paymentData) {
    try {
      const {
        referenceNumber,
        amount,
        currency = 'PHP',
        description,
        customerEmail,
        customerPhone,
        returnUrl,
        cancelUrl
      } = paymentData;

      const payload = {
        merchantId: GCASH_CONFIG.MERCHANT_ID,
        referenceNumber,
        amount: Math.round(amount * 100), // Convert to cents
        currency,
        description,
        customer: {
          email: customerEmail,
          phone: customerPhone
        },
        redirectUrls: {
          return: returnUrl,
          cancel: cancelUrl
        }
      };

      // Sign the request
      const signature = this.generateSignature(payload);

      const response = await axios.post(
        `${GCASH_CONFIG.API_ENDPOINT}/payments`,
        payload,
        {
          headers: {
            'Authorization': `Bearer ${GCASH_CONFIG.API_KEY}`,
            'X-Signature': signature,
            'Content-Type': 'application/json'
          }
        }
      );

      return {
        success: true,
        transactionId: response.data.id,
        paymentLink: response.data.links.payment,
        qrCode: response.data.qrCode || null,
        referenceNumber: referenceNumber,
        expiresAt: response.data.expiresAt
      };
    } catch (error) {
      console.error('GCash Payment Initiation Error:', error.response?.data || error.message);
      return {
        success: false,
        error: error.response?.data?.message || 'Failed to initiate GCash payment'
      };
    }
  }

  /**
   * Get payment status from GCash
   * @param {string} transactionId - GCash transaction ID
   * @returns {Promise<Object>} - Payment status
   */
  static async getPaymentStatus(transactionId) {
    try {
      const response = await axios.get(
        `${GCASH_CONFIG.API_ENDPOINT}/payments/${transactionId}`,
        {
          headers: {
            'Authorization': `Bearer ${GCASH_CONFIG.API_KEY}`,
            'Content-Type': 'application/json'
          }
        }
      );

      return {
        success: true,
        status: response.data.status, // completed, pending, failed, cancelled
        amount: response.data.amount / 100,
        currency: response.data.currency,
        transactionId: response.data.id,
        referenceNumber: response.data.referenceNumber,
        completedAt: response.data.completedAt,
        failureReason: response.data.failureReason || null
      };
    } catch (error) {
      console.error('GCash Status Check Error:', error.response?.data || error.message);
      return {
        success: false,
        error: 'Failed to check payment status'
      };
    }
  }

  /**
   * Verify webhook signature from GCash
   * @param {string} payload - Raw request body
   * @param {string} signature - X-Signature header
   * @returns {boolean} - True if signature is valid
   */
  static verifyWebhookSignature(payload, signature) {
    try {
      const calculatedSignature = this.generateSignature(payload);
      return calculatedSignature === signature;
    } catch (error) {
      console.error('Webhook Signature Verification Error:', error.message);
      return false;
    }
  }

  /**
   * Generate HMAC-SHA256 signature for requests
   * @param {Object} payload - Data to sign
   * @returns {string} - Hex signature
   */
  static generateSignature(payload) {
    const crypto = require('crypto');
    const payloadString = JSON.stringify(payload);
    return crypto
      .createHmac('sha256', GCASH_CONFIG.SECRET_KEY)
      .update(payloadString)
      .digest('hex');
  }

  /**
   * Create refund for completed payment
   * @param {string} transactionId - Original GCash transaction ID
   * @param {number} amount - Amount to refund (optional, full refund if not specified)
   * @returns {Promise<Object>} - Refund response
   */
  static async createRefund(transactionId, amount = null) {
    try {
      const payload = {
        transactionId,
        amount: amount ? Math.round(amount * 100) : undefined
      };

      const signature = this.generateSignature(payload);

      const response = await axios.post(
        `${GCASH_CONFIG.API_ENDPOINT}/refunds`,
        payload,
        {
          headers: {
            'Authorization': `Bearer ${GCASH_CONFIG.API_KEY}`,
            'X-Signature': signature,
            'Content-Type': 'application/json'
          }
        }
      );

      return {
        success: true,
        refundId: response.data.id,
        status: response.data.status,
        amount: response.data.amount / 100
      };
    } catch (error) {
      console.error('GCash Refund Error:', error.response?.data || error.message);
      return {
        success: false,
        error: 'Failed to create refund'
      };
    }
  }

  /**
   * Format transaction amount properly
   * @param {number} amount - Amount in PHP
   * @returns {number} - Amount in cents (for API)
   */
  static formatAmount(amount) {
    return Math.round(amount * 100);
  }

  /**
   * Generate unique reference number for transaction
   * @returns {string} - Reference number (ORD-YYYYMMDD-XXXXXXXX)
   */
  static generateReferenceNumber() {
    const date = new Date();
    const dateStr = date.toISOString().slice(0, 10).replace(/-/g, '');
    const random = Math.random().toString(36).substr(2, 8).toUpperCase();
    return `ORD-${dateStr}-${random}`;
  }
}

export default GCashService;
