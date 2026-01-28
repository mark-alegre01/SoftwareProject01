import React, { useEffect, useState } from 'react';

export const ReportsPage = () => {
  const [stats, setStats] = useState({
    totalRevenue: 0,
    paidRevenue: 0,
    pendingRevenue: 0,
    overdueRevenue: 0,
    occupancyRate: 0,
    payments: []
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchReports();
  }, []);

  const fetchReports = async () => {
    try {
      const [tenantsRes, paymentsRes] = await Promise.all([
        fetch('/api/tenants'),
        fetch('/api/payments')
      ]);

      const tenants = await tenantsRes.json();
      const payments = await paymentsRes.json();

      const totalRevenue = payments.reduce((sum, p) => sum + p.amount, 0);
      const paidRevenue = payments.filter(p => p.status === 'paid').reduce((sum, p) => sum + p.amount, 0);
      const pendingRevenue = payments.filter(p => p.status === 'pending').reduce((sum, p) => sum + p.amount, 0);
      const overdueRevenue = payments.filter(p => p.status === 'overdue').reduce((sum, p) => sum + p.amount, 0);
      const occupancyRate = tenants.length > 0 ? '100%' : '0%';

      setStats({
        totalRevenue,
        paidRevenue,
        pendingRevenue,
        overdueRevenue,
        occupancyRate,
        payments
      });
    } catch (error) {
      console.error('Error fetching reports:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-800">Financial Reports</h1>

      {loading ? (
        <div className="text-center py-8">Loading...</div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <StatCard title="Total Revenue" value={`₱${stats.totalRevenue.toLocaleString()}`} icon="💰" color="blue" />
            <StatCard title="Paid" value={`₱${stats.paidRevenue.toLocaleString()}`} icon="✅" color="green" />
            <StatCard title="Pending" value={`₱${stats.pendingRevenue.toLocaleString()}`} icon="⏳" color="yellow" />
            <StatCard title="Overdue" value={`₱${stats.overdueRevenue.toLocaleString()}`} icon="⚠️" color="red" />
            <StatCard title="Occupancy" value={stats.occupancyRate} icon="📊" color="purple" />
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-bold mb-4">Payment Summary by Status</h2>
            <div className="space-y-2">
              <div className="flex justify-between items-center pb-2">
                <span className="text-gray-700">Paid</span>
                <span className="font-bold text-green-600">₱{stats.paidRevenue.toLocaleString()}</span>
              </div>
              <div className="w-full bg-gray-200 rounded h-2">
                <div
                  className="bg-green-600 h-2 rounded"
                  style={{ width: stats.totalRevenue > 0 ? (stats.paidRevenue / stats.totalRevenue) * 100 + '%' : '0%' }}
                ></div>
              </div>

              <div className="flex justify-between items-center pb-2 pt-4">
                <span className="text-gray-700">Pending</span>
                <span className="font-bold text-yellow-600">₱{stats.pendingRevenue.toLocaleString()}</span>
              </div>
              <div className="w-full bg-gray-200 rounded h-2">
                <div
                  className="bg-yellow-400 h-2 rounded"
                  style={{ width: stats.totalRevenue > 0 ? (stats.pendingRevenue / stats.totalRevenue) * 100 + '%' : '0%' }}
                ></div>
              </div>

              <div className="flex justify-between items-center pb-2 pt-4">
                <span className="text-gray-700">Overdue</span>
                <span className="font-bold text-red-600">₱{stats.overdueRevenue.toLocaleString()}</span>
              </div>
              <div className="w-full bg-gray-200 rounded h-2">
                <div
                  className="bg-red-600 h-2 rounded"
                  style={{ width: stats.totalRevenue > 0 ? (stats.overdueRevenue / stats.totalRevenue) * 100 + '%' : '0%' }}
                ></div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

const StatCard = ({ title, value, icon, color }) => {
  const colorClasses = {
    blue: 'bg-blue-100 text-blue-800',
    green: 'bg-green-100 text-green-800',
    yellow: 'bg-yellow-100 text-yellow-800',
    red: 'bg-red-100 text-red-800',
    purple: 'bg-purple-100 text-purple-800'
  };

  return (
    <div className={`${colorClasses[color]} p-6 rounded-lg shadow`}>
      <div className="text-3xl mb-2">{icon}</div>
      <p className="text-sm font-medium text-gray-600">{title}</p>
      <p className="text-xl font-bold">{value}</p>
    </div>
  );
};
