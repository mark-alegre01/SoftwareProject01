import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { LandlordDashboard } from './pages/LandlordDashboard';
import { BoarderDashboard } from './pages/BoarderDashboard';
import { TenantListPage } from './pages/TenantListPage';
import { PaymentsPage } from './pages/PaymentsPage';
import { MakePaymentPage } from './pages/MakePaymentPage';
import { BoarderProfilePage } from './pages/BoarderProfilePage';
import { ReportsPage } from './pages/ReportsPage';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { ProtectedRoute } from './components/ProtectedRoute';

const DashboardLayout = ({ children }) => {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Navbar />
        <main className="flex-1 p-6">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

const Dashboard = () => {
  const { user } = useAuth();

  return (
    <DashboardLayout>
      {user?.role === 'landlord' ? <LandlordDashboard /> : <BoarderDashboard />}
    </DashboardLayout>
  );
};

function App() {
  return (
    <Router>
      <AuthProvider>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected Routes */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />

          {/* Landlord Routes */}
          <Route
            path="/tenants"
            element={
              <ProtectedRoute requiredRole="landlord">
                <DashboardLayout>
                  <TenantListPage />
                </DashboardLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/payments"
            element={
              <ProtectedRoute requiredRole="landlord">
                <DashboardLayout>
                  <PaymentsPage />
                </DashboardLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/reports"
            element={
              <ProtectedRoute requiredRole="landlord">
                <DashboardLayout>
                  <ReportsPage />
                </DashboardLayout>
              </ProtectedRoute>
            }
          />

          {/* Boarder Routes */}
          <Route
            path="/my-payments"
            element={
              <ProtectedRoute requiredRole="boarder">
                <DashboardLayout>
                  <PaymentsPage />
                </DashboardLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/make-payment"
            element={
              <ProtectedRoute requiredRole="boarder">
                <DashboardLayout>
                  <MakePaymentPage />
                </DashboardLayout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/profile"
            element={
              <ProtectedRoute requiredRole="boarder">
                <DashboardLayout>
                  <BoarderProfilePage />
                </DashboardLayout>
              </ProtectedRoute>
            }
          />

          {/* Default Route */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </Router>
  );
}

export default App;
