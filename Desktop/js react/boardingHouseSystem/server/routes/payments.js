import express from 'express';
import { getDB } from '../db/database.js';

const router = express.Router();

// Get all payments
router.get('/', (req, res) => {
  const db = getDB();
  res.json(db.data.payments);
});

// Get payment by ID
router.get('/:id', (req, res) => {
  const { id } = req.params;
  const db = getDB();
  const payment = db.data.payments.find(p => p.id === id);
  
  if (!payment) {
    return res.status(404).json({ error: 'Payment not found' });
  }
  
  res.json(payment);
});

// Get payments by tenant ID
router.get('/tenant/:tenantId', (req, res) => {
  const { tenantId } = req.params;
  const db = getDB();
  const payments = db.data.payments.filter(p => p.tenantId === tenantId);
  
  res.json(payments);
});

// Create new payment
router.post('/', async (req, res) => {
  const { tenantId, tenantName, amount, month, dueDate } = req.body;
  
  if (!tenantId || !amount || !month) {
    return res.status(400).json({ error: 'Missing required fields' });
  }
  
  const db = getDB();
  const newPayment = {
    id: String(Date.now()),
    tenantId,
    tenantName,
    amount,
    month,
    dueDate: dueDate || new Date().toISOString().split('T')[0],
    paidDate: null,
    status: 'pending',
    paymentMethod: null,
    createdAt: new Date().toISOString()
  };
  
  db.data.payments.push(newPayment);
  await db.write();
  
  res.status(201).json(newPayment);
});

// Update payment status
router.put('/:id', async (req, res) => {
  const { id } = req.params;
  const { status, paidDate, paymentMethod } = req.body;
  
  const db = getDB();
  const paymentIndex = db.data.payments.findIndex(p => p.id === id);
  
  if (paymentIndex === -1) {
    return res.status(404).json({ error: 'Payment not found' });
  }
  
  if (status) db.data.payments[paymentIndex].status = status;
  if (paidDate) db.data.payments[paymentIndex].paidDate = paidDate;
  if (paymentMethod) db.data.payments[paymentIndex].paymentMethod = paymentMethod;
  
  await db.write();
  
  res.json(db.data.payments[paymentIndex]);
});

// Mark payment as paid
router.post('/:id/pay', async (req, res) => {
  const { id } = req.params;
  const { paymentMethod } = req.body;
  
  const db = getDB();
  const paymentIndex = db.data.payments.findIndex(p => p.id === id);
  
  if (paymentIndex === -1) {
    return res.status(404).json({ error: 'Payment not found' });
  }
  
  db.data.payments[paymentIndex].status = 'paid';
  db.data.payments[paymentIndex].paidDate = new Date().toISOString().split('T')[0];
  db.data.payments[paymentIndex].paymentMethod = paymentMethod || 'cash';
  
  await db.write();
  
  res.json(db.data.payments[paymentIndex]);
});

// Submit GCash payment proof
router.post('/:id/submit-gcash', async (req, res) => {
  const { id } = req.params;
  const { gcashNumber, gcashRefNumber, paidDate } = req.body;
  
  // Validate GCash details
  if (!gcashNumber || !gcashRefNumber) {
    return res.status(400).json({ error: 'Missing GCash details' });
  }
  
  const db = getDB();
  const paymentIndex = db.data.payments.findIndex(p => p.id === id);
  
  if (paymentIndex === -1) {
    return res.status(404).json({ error: 'Payment not found' });
  }
  
  // Update payment with GCash proof
  db.data.payments[paymentIndex].status = 'pending'; // Landlord will verify
  db.data.payments[paymentIndex].paymentMethod = 'gcash';
  db.data.payments[paymentIndex].paidDate = paidDate || new Date().toISOString().split('T')[0];
  db.data.payments[paymentIndex].gcashNumber = gcashNumber;
  db.data.payments[paymentIndex].gcashRefNumber = gcashRefNumber;
  
  await db.write();
  
  res.status(201).json({
    message: 'GCash payment proof submitted successfully',
    payment: db.data.payments[paymentIndex]
  });
});

// Submit bank transfer payment proof
router.post('/:id/submit-bank', async (req, res) => {
  const { id } = req.params;
  const { referenceNumber, paidDate } = req.body;
  
  if (!referenceNumber) {
    return res.status(400).json({ error: 'Missing bank reference number' });
  }
  
  const db = getDB();
  const paymentIndex = db.data.payments.findIndex(p => p.id === id);
  
  if (paymentIndex === -1) {
    return res.status(404).json({ error: 'Payment not found' });
  }
  
  db.data.payments[paymentIndex].status = 'pending'; // Landlord will verify
  db.data.payments[paymentIndex].paymentMethod = 'bank_transfer';
  db.data.payments[paymentIndex].paidDate = paidDate || new Date().toISOString().split('T')[0];
  db.data.payments[paymentIndex].referenceNumber = referenceNumber;
  
  await db.write();
  
  res.status(201).json({
    message: 'Bank transfer proof submitted successfully',
    payment: db.data.payments[paymentIndex]
  });
});

export default router;
