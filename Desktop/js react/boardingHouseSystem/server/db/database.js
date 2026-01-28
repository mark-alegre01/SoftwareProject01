import { JSONFile, Low } from 'lowdb';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const dbPath = join(__dirname, 'db.json');
const adapter = new JSONFile(dbPath);

let db;

export async function initializeDB() {
  db = new Low(adapter);
  
  await db.read();
  
  if (!db.data) {
    db.data = {
      tenants: [],
      payments: [],
      users: []
    };
    await db.write();
    seedDatabase();
  }
  
  return db;
}

export function getDB() {
  return db;
}

async function seedDatabase() {
  const db = getDB();
  
  // Seed users
  db.data.users = [
    { id: '1', role: 'landlord', username: 'landlord', password: 'password', name: 'John Landlord' },
    { id: '2', role: 'boarder', username: 'boarder1', password: 'password', name: 'Jane Doe', tenantId: '1' },
    { id: '3', role: 'boarder', username: 'boarder2', password: 'password', name: 'Bob Smith', tenantId: '2' }
  ];
  
  // Seed tenants
  db.data.tenants = [
    {
      id: '1',
      name: 'Jane Doe',
      email: 'jane@example.com',
      phone: '09123456789',
      roomNumber: '101',
      moveInDate: '2024-01-15',
      monthlyRate: 5000,
      status: 'active',
      createdAt: new Date().toISOString()
    },
    {
      id: '2',
      name: 'Bob Smith',
      email: 'bob@example.com',
      phone: '09987654321',
      roomNumber: '102',
      moveInDate: '2024-02-01',
      monthlyRate: 5000,
      status: 'active',
      createdAt: new Date().toISOString()
    },
    {
      id: '3',
      name: 'Alice Johnson',
      email: 'alice@example.com',
      phone: '09555666777',
      roomNumber: '103',
      moveInDate: '2024-03-10',
      monthlyRate: 5500,
      status: 'active',
      createdAt: new Date().toISOString()
    }
  ];
  
  // Seed payments
  db.data.payments = [
    {
      id: '1',
      tenantId: '1',
      tenantName: 'Jane Doe',
      amount: 5000,
      month: 'January 2025',
      dueDate: '2025-01-05',
      paidDate: '2025-01-03',
      status: 'paid',
      paymentMethod: 'bank_transfer',
      createdAt: new Date().toISOString()
    },
    {
      id: '2',
      tenantId: '1',
      tenantName: 'Jane Doe',
      amount: 5000,
      month: 'December 2024',
      dueDate: '2024-12-05',
      paidDate: '2024-12-04',
      status: 'paid',
      paymentMethod: 'bank_transfer',
      createdAt: new Date().toISOString()
    },
    {
      id: '3',
      tenantId: '1',
      tenantName: 'Jane Doe',
      amount: 5000,
      month: 'February 2025',
      dueDate: '2025-02-05',
      paidDate: null,
      status: 'pending',
      paymentMethod: null,
      createdAt: new Date().toISOString()
    },
    {
      id: '4',
      tenantId: '2',
      tenantName: 'Bob Smith',
      amount: 5000,
      month: 'January 2025',
      dueDate: '2025-01-05',
      paidDate: null,
      status: 'overdue',
      paymentMethod: null,
      createdAt: new Date().toISOString()
    },
    {
      id: '5',
      tenantId: '2',
      tenantName: 'Bob Smith',
      amount: 5000,
      month: 'December 2024',
      dueDate: '2024-12-05',
      paidDate: '2024-12-06',
      status: 'paid',
      paymentMethod: 'cash',
      createdAt: new Date().toISOString()
    }
  ];
  
  await db.write();
  console.log('✓ Database seeded with initial data');
}
