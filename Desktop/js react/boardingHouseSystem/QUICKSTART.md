# Quick Start Guide

## ⚡ Fast Track to Running the App

### Prerequisites
- **Node.js** installed (download from https://nodejs.org/)

### 3 Steps to Get Started

#### Step 1: Navigate to Project
```bash
cd "c:\Users\Mark Anthony Alegre\Desktop\js react\boardingHouseSystem"
```

#### Step 2: Install Dependencies
```bash
npm install
cd client && npm install && cd ..
```

#### Step 3: Start the App
```bash
npm run dev
```

Open browser to: **http://localhost:5173**

---

## 🔐 Login Credentials

| Role | Username | Password |
|------|----------|----------|
| Landlord | landlord | password |
| Boarder | boarder1 | password |

---

## 📱 What You Can Do

### As Landlord 🏢
- View dashboard with statistics
- Manage tenants (add, view, delete)
- Monitor all payments
- View financial reports

### As Boarder 👤
- View personal dashboard
- Check payment history
- Make payment submissions
- View profile information

---

## 🚀 Useful Commands

| Command | What it does |
|---------|-------------|
| `npm run dev` | Start backend + frontend together |
| `npm run server` | Start only backend |
| `cd client && npm run dev` | Start only frontend |
| `npm run build` | Build frontend for production |

---

## ⚠️ Troubleshooting

**Port already in use?**
```bash
# Windows - Find process using port 5000
netstat -ano | findstr :5000
# Kill the process
taskkill /PID <PID> /F
```

**npm command not found?**
- Reinstall Node.js
- Make sure to click "Add to PATH" during installation
- Restart your terminal

**Module not found?**
```bash
# Delete and reinstall
rm -r node_modules package-lock.json
npm install
cd client && npm install && cd ..
```

---

## 📂 Project Structure

```
📦 boardingHouseSystem
├── 📁 server/          ← Backend (Express)
├── 📁 client/          ← Frontend (React)
├── 📄 package.json     ← Root configuration
├── 📄 setup.bat        ← Windows auto-setup
└── 📄 setup.sh         ← Mac/Linux auto-setup
```

---

## 🎯 Next Steps

1. ✅ Install Node.js if you haven't
2. ✅ Run `npm install` from root folder
3. ✅ Run `cd client && npm install` 
4. ✅ Run `npm run dev`
5. ✅ Open http://localhost:5173
6. ✅ Login with demo credentials
7. ✅ Explore the features!

---

For detailed setup instructions, see **SETUP_INSTRUCTIONS.md**
