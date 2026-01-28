# Boarding House Payment and Monitoring System - Setup Instructions

## Prerequisites

Before you start, make sure you have **Node.js** installed on your computer. 

### Step 1: Install Node.js

1. **Download Node.js**
   - Go to https://nodejs.org/
   - Download the **LTS (Long Term Support)** version (recommended)
   - Choose the installer for your operating system:
     - **Windows**: Download `.msi` file
     - **macOS**: Download `.pkg` file
     - **Linux**: Follow the package manager instructions

2. **Install Node.js**
   - Run the downloaded installer
   - Follow the installation wizard
   - **IMPORTANT**: When asked "Add to PATH", make sure to select **YES**

3. **Verify Installation**
   - Open Command Prompt (Windows) or Terminal (Mac/Linux)
   - Run these commands:
     ```bash
     node --version
     npm --version
     ```
   - You should see version numbers for both

## Setup Instructions

### Option 1: Automatic Setup (Windows)

1. Navigate to the project folder: `c:\Users\Mark Anthony Alegre\Desktop\js react\boardingHouseSystem`
2. Double-click the `setup.bat` file
3. Wait for the installation to complete

### Option 2: Automatic Setup (macOS/Linux)

1. Open Terminal
2. Navigate to the project folder:
   ```bash
   cd "c:/Users/Mark Anthony Alegre/Desktop/js react/boardingHouseSystem"
   ```
3. Run the setup script:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

### Option 3: Manual Setup

1. Open Command Prompt (Windows) or Terminal (Mac/Linux)
2. Navigate to the project folder:
   ```bash
   cd "c:\Users\Mark Anthony Alegre\Desktop\js react\boardingHouseSystem"
   ```

3. Install backend dependencies:
   ```bash
   npm install
   ```

4. Install frontend dependencies:
   ```bash
   cd client
   npm install
   cd ..
   ```

## Running the Application

### Start Both Frontend and Backend Together

```bash
npm run dev
```

This will:
- Start the backend server on **http://localhost:5000**
- Start the frontend on **http://localhost:5173**

The terminal will show both servers running. Open your browser to:
```
http://localhost:5173
```

### Start Only the Backend

```bash
npm run server
```

Backend will run on: http://localhost:5000

### Start Only the Frontend

```bash
cd client
npm run dev
```

Frontend will run on: http://localhost:5173

## Demo Credentials

### Landlord Account
- **Username**: landlord
- **Password**: password

### Boarder Account 1
- **Username**: boarder1
- **Password**: password

### Boarder Account 2
- **Username**: boarder2
- **Password**: password

## Default Users and Tenants

The system comes pre-loaded with demo data:

### Tenants
1. Jane Doe - Room 101 - ₱5,000/month
2. Bob Smith - Room 102 - ₱5,000/month
3. Alice Johnson - Room 103 - ₱5,500/month

### Sample Payments
Pre-configured payment records for testing payment status filters.

## Features by User Role

### Landlord Features
- 📊 **Dashboard**: View key statistics (tenants, payments, status summary)
- 👥 **Tenant Management**: Add, view, edit, delete tenants
- 💳 **Payments**: View all payments, filter by status, mark payments as paid
- 📈 **Reports**: View financial reports and revenue breakdowns

### Boarder Features
- 📊 **Dashboard**: View personal payment status and information
- 💳 **My Payments**: View payment history and status
- 💰 **Make Payment**: Submit payment (demo form)
- 👤 **My Profile**: View personal and room information

## Project Structure

```
boardingHouseSystem/
├── server/                          # Backend (Express + lowdb)
│   ├── index.js                     # Main server file
│   ├── db/
│   │   └── database.js              # Database initialization
│   ├── routes/
│   │   ├── auth.js                  # Authentication endpoints
│   │   ├── tenants.js               # Tenant CRUD endpoints
│   │   └── payments.js              # Payment endpoints
│   └── package.json
│
├── client/                          # Frontend (React + Vite)
│   ├── src/
│   │   ├── pages/                   # Page components
│   │   ├── components/              # Reusable components
│   │   ├── context/                 # React Context (Auth)
│   │   ├── styles/                  # CSS styles
│   │   ├── App.jsx                  # Main app component
│   │   └── main.jsx                 # Entry point
│   ├── vite.config.js               # Vite configuration
│   ├── tailwind.config.js           # Tailwind CSS config
│   └── package.json
│
├── package.json                     # Root package.json
├── README.md                        # General README
└── SETUP_INSTRUCTIONS.md            # This file
```

## Troubleshooting

### Error: "npm is not recognized"
- **Solution**: Node.js is not installed or not in PATH
- **Fix**: Reinstall Node.js and select "Add to PATH" option

### Error: "Port 5000/5173 is already in use"
- **Solution**: Another application is using the port
- **Option 1**: Close the other application
- **Option 2**: Change the port in `server/index.js` or `client/vite.config.js`

### Error: "Cannot find module"
- **Solution**: Dependencies not installed properly
- **Fix**: Delete `node_modules` folder and `package-lock.json`, then run:
  ```bash
  npm install
  cd client
  npm install
  cd ..
  ```

### Frontend not connecting to backend
- **Solution**: Backend server not running
- **Fix**: Make sure to run `npm run dev` from the root folder (not the client folder)

### Changes not appearing
- **Solution**: Browser cache or development server not reloading
- **Fix**: Hard refresh (Ctrl+Shift+R on Windows or Cmd+Shift+R on Mac)

## API Documentation

### Health Check
- `GET /api/health` - Check if server is running

### Authentication
- `POST /api/auth/login` - Login with credentials
- `POST /api/auth/logout` - Logout
- `GET /api/auth/verify` - Verify token

### Tenants
- `GET /api/tenants` - Get all tenants
- `GET /api/tenants/:id` - Get tenant by ID
- `POST /api/tenants` - Create new tenant
- `PUT /api/tenants/:id` - Update tenant
- `DELETE /api/tenants/:id` - Delete tenant

### Payments
- `GET /api/payments` - Get all payments
- `GET /api/payments/:id` - Get payment by ID
- `GET /api/payments/tenant/:tenantId` - Get tenant's payments
- `POST /api/payments` - Create new payment
- `PUT /api/payments/:id` - Update payment
- `POST /api/payments/:id/pay` - Mark payment as paid

## Database

The system uses **lowdb** - a lightweight JSON file database:
- No SQL setup required
- Data stored in `server/db/db.json`
- Auto-created on first run
- Easy to back up and modify

## Production Notes

This is a demonstration application. For production use:

1. **Authentication**: Implement proper JWT tokens instead of base64 encoding
2. **Database**: Use a proper database (PostgreSQL, MongoDB, etc.)
3. **Security**: Add password hashing, HTTPS, environment variables
4. **Validation**: Add comprehensive input validation
5. **Error Handling**: Implement proper error handling and logging
6. **Payment Gateway**: Integrate real payment gateway (Stripe, PayMaya, etc.)
7. **Deployment**: Use production hosting (Heroku, Vercel, DigitalOcean, etc.)

## Support

For issues or questions about the application, check:
- Terminal error messages for specific details
- Browser console (F12) for frontend errors
- Common troubleshooting section above

## License

MIT License - Feel free to use and modify this project.

---

**Happy coding! 🚀**
