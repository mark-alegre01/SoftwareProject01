import express from 'express';
import { getDB } from '../db/database.js';

const router = express.Router();

// Get all tenants
router.get('/', (req, res) => {
  const db = getDB();
  res.json(db.data.tenants);
});

// Get tenant by ID
router.get('/:id', (req, res) => {
  const { id } = req.params;
  const db = getDB();
  const tenant = db.data.tenants.find(t => t.id === id);
  
  if (!tenant) {
    return res.status(404).json({ error: 'Tenant not found' });
  }
  
  res.json(tenant);
});

// Create new tenant (landlord only)
router.post('/', async (req, res) => {
  const { name, email, phone, roomNumber, moveInDate, monthlyRate } = req.body;
  
  if (!name || !email || !roomNumber || !monthlyRate) {
    return res.status(400).json({ error: 'Missing required fields' });
  }
  
  const db = getDB();
  const newTenant = {
    id: String(Date.now()),
    name,
    email,
    phone,
    roomNumber,
    moveInDate: moveInDate || new Date().toISOString().split('T')[0],
    monthlyRate,
    status: 'active',
    createdAt: new Date().toISOString()
  };
  
  db.data.tenants.push(newTenant);
  await db.write();
  
  res.status(201).json(newTenant);
});

// Update tenant
router.put('/:id', async (req, res) => {
  const { id } = req.params;
  const { name, email, phone, roomNumber, monthlyRate, status } = req.body;
  
  const db = getDB();
  const tenantIndex = db.data.tenants.findIndex(t => t.id === id);
  
  if (tenantIndex === -1) {
    return res.status(404).json({ error: 'Tenant not found' });
  }
  
  if (name) db.data.tenants[tenantIndex].name = name;
  if (email) db.data.tenants[tenantIndex].email = email;
  if (phone) db.data.tenants[tenantIndex].phone = phone;
  if (roomNumber) db.data.tenants[tenantIndex].roomNumber = roomNumber;
  if (monthlyRate) db.data.tenants[tenantIndex].monthlyRate = monthlyRate;
  if (status) db.data.tenants[tenantIndex].status = status;
  
  await db.write();
  
  res.json(db.data.tenants[tenantIndex]);
});

// Delete tenant
router.delete('/:id', async (req, res) => {
  const { id } = req.params;
  
  const db = getDB();
  const tenantIndex = db.data.tenants.findIndex(t => t.id === id);
  
  if (tenantIndex === -1) {
    return res.status(404).json({ error: 'Tenant not found' });
  }
  
  const deletedTenant = db.data.tenants.splice(tenantIndex, 1);
  await db.write();
  
  res.json(deletedTenant[0]);
});

export default router;
