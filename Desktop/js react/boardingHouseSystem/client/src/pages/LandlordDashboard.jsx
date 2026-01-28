import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';

export const LandlordDashboard = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState({
    totalTenants: 0,
    totalPayments: 0,
    paidPayments: 0,
    pendingPayments: 0,
    overduePayments: 0
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const [tenantsRes, paymentsRes] = await Promise.all([
        fetch('/api/tenants'),
        fetch('/api/payments')
      ]);

      const tenants = await tenantsRes.json();
      const payments = await paymentsRes.json();

      setStats({
        totalTenants: tenants.length,
        totalPayments: payments.length,
        paidPayments: payments.filter(p => p.status === 'paid').length,
        pendingPayments: payments.filter(p => p.status === 'pending').length,
        overduePayments: payments.filter(p => p.status === 'overdue').length
      });
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-800">Welcome back, {user?.name}!</h1>
        <p className="text-gray-600">Manage your boarding house efficiently</p>
      </div>

      {loading ? (
        <div className="text-center py-8">Loading...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <StatCard title="Total Tenants" value={stats.totalTenants} icon="👥" color="blue" />
          <StatCard title="Total Payments" value={stats.totalPayments} icon="💳" color="green" />
          <StatCard title="Paid" value={stats.paidPayments} icon="✅" color="green" />
          <StatCard title="Pending" value={stats.pendingPayments} icon="⏳" color="yellow" />
          <StatCard title="Overdue" value={stats.overduePayments} icon="⚠️" color="red" />
        </div>
      )}

      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-bold mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a href="/tenants" className="p-4 bg-blue-100 rounded hover:bg-blue-200 transition text-center">
            <span className="text-3xl block mb-2">👥</span>
            <p className="font-semibold">Manage Tenants</p>
          </a>
          <a href="/payments" className="p-4 bg-green-100 rounded hover:bg-green-200 transition text-center">
            <span className="text-3xl block mb-2">💳</span>
            <p className="font-semibold">View Payments</p>
          </a>
          <a href="/reports" className="p-4 bg-purple-100 rounded hover:bg-purple-200 transition text-center">
            <span className="text-3xl block mb-2">📊</span>
            <p className="font-semibold">View Reports</p>
          </a>
        </div>
      </div>
    </div>
  );
};

const StatCard = ({ title, value, icon, color }) => {
  const colorClasses = {
    blue: 'bg-blue-100 text-blue-800',
    green: 'bg-green-100 text-green-800',
    yellow: 'bg-yellow-100 text-yellow-800',
    red: 'bg-red-100 text-red-800'
  };

  return (
    <div className={`${colorClasses[color]} p-6 rounded-lg shadow`}>
      <div className="text-3xl mb-2">{icon}</div>
      <p className="text-sm font-medium text-gray-600">{title}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
};
