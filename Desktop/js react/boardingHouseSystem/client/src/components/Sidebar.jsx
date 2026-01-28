import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const Sidebar = () => {
  const { user } = useAuth();

  if (!user) return null;

  return (
    <aside className="w-64 bg-gray-800 text-white min-h-screen shadow-lg">
      <div className="p-6">
        <h2 className="text-2xl font-bold mb-8">Menu</h2>
        
        <nav className="space-y-2">
          {user.role === 'landlord' ? (
            <>
              <Link to="/dashboard" className="block px-4 py-2 rounded hover:bg-gray-700">
                Dashboard
              </Link>
              <Link to="/tenants" className="block px-4 py-2 rounded hover:bg-gray-700">
                Tenants
              </Link>
              <Link to="/payments" className="block px-4 py-2 rounded hover:bg-gray-700">
                Payments
              </Link>
              <Link to="/reports" className="block px-4 py-2 rounded hover:bg-gray-700">
                Reports
              </Link>
            </>
          ) : (
            <>
              <Link to="/dashboard" className="block px-4 py-2 rounded hover:bg-gray-700">
                My Dashboard
              </Link>
              <Link to="/my-payments" className="block px-4 py-2 rounded hover:bg-gray-700">
                My Payments
              </Link>
              <Link to="/make-payment" className="block px-4 py-2 rounded hover:bg-gray-700">
                Make Payment
              </Link>
              <Link to="/profile" className="block px-4 py-2 rounded hover:bg-gray-700">
                My Profile
              </Link>
            </>
          )}
        </nav>
      </div>
    </aside>
  );
};
