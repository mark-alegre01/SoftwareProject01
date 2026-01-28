import express from 'express';
import cors from 'cors';
import { fileURLToPath } from 'url';
import { dirname } from 'path';
import authRoutes from './routes/auth.js';
import tenantsRoutes from './routes/tenants.js';
import paymentsRoutes from './routes/payments.js';
import gcashPaymentsRoutes from './routes/gcashPayments.js';
import webhooksRoutes from './routes/webhooks.js';
import { initializeDB } from './db/database.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(cors());
app.use(express.json());

// Initialize database
initializeDB();

// Routes
app.use('/api/auth', authRoutes);
app.use('/api/tenants', tenantsRoutes);
app.use('/api/payments', paymentsRoutes);
app.use('/api/gcash', gcashPaymentsRoutes);
app.use('/api/webhooks', webhooksRoutes);

// Basic health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', message: 'Server is running' });
});

// Start server
app.listen(PORT, () => {
  console.log(`✓ Backend server running on http://localhost:${PORT}`);
  console.log(`✓ API available at http://localhost:${PORT}/api`);
  console.log(`✓ GCash webhook endpoint: http://localhost:${PORT}/api/webhooks/gcash`);
});
