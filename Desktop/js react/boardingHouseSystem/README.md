# Boarding House Payment and Monitoring System

A web application for managing boarding house payments and tenant information with separate interfaces for landlords and boarders.

## Features

- **Landlord Dashboard**: View all tenants, manage payments, monitor payment history, and manage the property
- **Boarder Dashboard**: View personal information, payment status, payment history, and make payments
- **Role-based Authentication**: Simple login with role selection (landlord/boarder)
- **Payment Management**: Track and manage payments with status indicators
- **Tenant Management**: Add, view, and manage tenant information (landlord only)

## Tech Stack

- **Frontend**: React (Vite), React Router, Tailwind CSS
- **Backend**: Express.js, lowdb (file-based JSON database)
- **Development**: Concurrently for running frontend and backend together

## Prerequisites

- Node.js 16+ and npm

## Installation

### 1. Install Backend Dependencies

```bash
npm install
```

### 2. Install Frontend Dependencies

```bash
cd client
npm install
cd ..
```

## Running the Application

### Development Mode (Frontend + Backend)

```bash
npm run dev
```

This will start:
- Backend server on `http://localhost:5000`
- Frontend on `http://localhost:5173`

### Backend Only

```bash
npm run server
```

### Frontend Only

```bash
cd client
npm run dev
```

### Production Build

```bash
npm run build
npm start
```

## Project Structure

```
boardingHouseSystem/
├── server/
│   ├── index.js              # Express server setup
│   ├── routes/
│   │   ├── auth.js          # Authentication routes
│   │   ├── tenants.js       # Tenant management routes
│   │   └── payments.js      # Payment routes
│   ├── db/
│   │   └── db.json          # lowdb database file (auto-generated)
│   └── seed.js              # Database seeding
├── client/                   # React frontend (Vite)
│   ├── src/
│   │   ├── components/      # Reusable components
│   │   ├── pages/           # Page components
│   │   ├── context/         # React context for auth
│   │   ├── App.jsx          # Main app component
│   │   └── main.jsx         # Entry point
│   └── index.html
├── package.json
└── README.md
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login with role selection
- `POST /api/auth/logout` - Logout

### Tenants
- `GET /api/tenants` - Get all tenants
- `GET /api/tenants/:id` - Get tenant by ID
- `POST /api/tenants` - Create new tenant (landlord only)
- `PUT /api/tenants/:id` - Update tenant (landlord only)
- `DELETE /api/tenants/:id` - Delete tenant (landlord only)

### Payments
- `GET /api/payments` - Get all payments
- `GET /api/payments/:id` - Get payment by ID
- `POST /api/payments` - Create payment
- `PUT /api/payments/:id` - Update payment status
- `GET /api/payments/tenant/:tenantId` - Get tenant payments

## Default Login

### Landlord
- Username: `landlord` / Password: `password`

### Boarder
- Username: `boarder1` / Password: `password`

## Development Notes

- The backend uses lowdb for simple file-based storage (no database setup required)
- User authentication is stub-based for demonstration; implement proper JWT for production
- CORS is enabled for local development
- Tailwind CSS is configured for styling

## License

MIT
