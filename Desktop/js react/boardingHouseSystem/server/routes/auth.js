import express from 'express';
import { getDB } from '../db/database.js';

const router = express.Router();

// Helper function to generate unique ID
const generateId = () => {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
};

// Register endpoint
router.post('/register', (req, res) => {
  const { username, password, name, email, phone, roomNumber, monthlyRate } = req.body;
  
  // Validate required fields
  if (!username || !password || !name || !email || !phone || !roomNumber || !monthlyRate) {
    return res.status(400).json({ error: 'Missing required fields' });
  }
  
  const db = getDB();
  
  // Check if username already exists
  const existingUser = db.data.users.find(u => u.username === username);
  if (existingUser) {
    return res.status(400).json({ error: 'Username already exists' });
  }
  
  // Generate IDs
  const userId = generateId();
  const tenantId = generateId();
  
  // Create tenant record
  const tenant = {
    id: tenantId,
    name,
    email,
    phone,
    roomNumber,
    moveInDate: new Date().toISOString().split('T')[0],
    monthlyRate: parseFloat(monthlyRate),
    status: 'active',
    createdAt: new Date().toISOString()
  };
  
  // Create user record
  const user = {
    id: userId,
    role: 'boarder',
    username,
    password,
    name,
    tenantId
  };
  
  // Add to database
  db.data.tenants.push(tenant);
  db.data.users.push(user);
  
  // Write to file
  db.write();
  
  res.status(201).json({
    message: 'Registration successful',
    user: {
      id: user.id,
      role: user.role,
      username: user.username,
      name: user.name,
      tenantId: user.tenantId
    }
  });
});

// Login endpoint
router.post('/login', (req, res) => {
  const { username, password, role } = req.body;
  
  if (!username || !password || !role) {
    return res.status(400).json({ error: 'Missing credentials' });
  }
  
  const db = getDB();
  const user = db.data.users.find(u => u.username === username && u.password === password && u.role === role);
  
  if (!user) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }
  
  // Simple token (in production, use JWT)
  const token = Buffer.from(JSON.stringify({ id: user.id, role: user.role, username: user.username })).toString('base64');
  
  res.json({
    token,
    user: {
      id: user.id,
      role: user.role,
      username: user.username,
      name: user.name,
      tenantId: user.tenantId
    }
  });
});

// Logout endpoint
router.post('/logout', (req, res) => {
  res.json({ message: 'Logged out successfully' });
});

// Verify token endpoint
router.get('/verify', (req, res) => {
  const token = req.headers.authorization?.split(' ')[1];
  
  if (!token) {
    return res.status(401).json({ error: 'No token provided' });
  }
  
  try {
    const decoded = JSON.parse(Buffer.from(token, 'base64').toString());
    res.json({ user: decoded });
  } catch (error) {
    res.status(401).json({ error: 'Invalid token' });
  }
});

export default router;
