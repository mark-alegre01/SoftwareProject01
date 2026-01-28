#!/bin/bash

# Boarding House Payment System - Setup Script for macOS/Linux

echo ""
echo "===================================="
echo "Boarding House Payment System Setup"
echo "===================================="
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "[ERROR] Node.js is not installed!"
    echo ""
    echo "Please download and install Node.js from:"
    echo "https://nodejs.org/"
    echo ""
    exit 1
fi

echo "[OK] Node.js is installed"
node --version
npm --version
echo ""

# Install root dependencies
echo "[STEP 1] Installing root dependencies..."
npm install
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install root dependencies"
    exit 1
fi
echo "[OK] Root dependencies installed"
echo ""

# Install client dependencies
echo "[STEP 2] Installing client dependencies..."
cd client
npm install
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install client dependencies"
    exit 1
fi
echo "[OK] Client dependencies installed"
cd ..
echo ""

echo ""
echo "===================================="
echo "Setup Complete!"
echo "===================================="
echo ""
echo "To start the application, run:"
echo "  npm run dev"
echo ""
echo "This will start both the backend (port 5000) and frontend (port 5173)"
echo ""
