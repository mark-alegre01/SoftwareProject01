import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';

export const BoarderDashboard = () => {
  const { user } = useAuth();
  const [tenant, setTenant] = useState(null);
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const tenantsRes = await fetch('/api/tenants');
      const tenants = await tenantsRes.json();
      const currentTenant = tenants.find(t => t.id === user?.tenantId);
      setTenant(currentTenant);

      const paymentsRes = await fetch(`/api/payments/tenant/${user?.tenantId}`);
      const paymentData = await paymentsRes.json();
      setPayments(paymentData);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getPaymentStats = () => {
    const paid = payments.filter(p => p.status === 'paid').length;
    const pending = payments.filter(p => p.status === 'pending').length;
    const overdue = payments.filter(p => p.status === 'overdue').length;
    return { paid, pending, overdue };
  };

  const stats = getPaymentStats();

  if (loading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-800">Welcome, {user?.name}!</h1>
        <p className="text-gray-600">Room: {tenant?.roomNumber} | Monthly Rate: ₱{tenant?.monthlyRate}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard title="Paid Payments" value={stats.paid} icon="✅" color="green" />
        <StatCard title="Pending" value={stats.pending} icon="⏳" color="yellow" />
        <StatCard title="Overdue" value={stats.overdue} icon="⚠️" color="red" />
      </div>

      <div className="bg-white p-6 rounded-lg shadow">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">Your Payment History</h2>
          <a href="/make-payment" className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
            Make Payment
          </a>
        </div>

        {payments.length === 0 ? (
          <p className="text-gray-600">No payments found</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-100">
                <tr>
                  <th className="px-4 py-2 text-left">Month</th>
                  <th className="px-4 py-2 text-left">Amount</th>
                  <th className="px-4 py-2 text-left">Due Date</th>
                  <th className="px-4 py-2 text-left">Status</th>
                  <th className="px-4 py-2 text-left">Paid Date</th>
                </tr>
              </thead>
              <tbody>
                {payments.map(payment => (
                  <tr key={payment.id} className="border-t hover:bg-gray-50">
                    <td className="px-4 py-2">{payment.month}</td>
                    <td className="px-4 py-2">₱{payment.amount}</td>
                    <td className="px-4 py-2">{payment.dueDate}</td>
                    <td className="px-4 py-2">
                      <span className={`px-3 py-1 rounded text-sm font-semibold ${getStatusColor(payment.status)}`}>
                        {payment.status.charAt(0).toUpperCase() + payment.status.slice(1)}
                      </span>
                    </td>
                    <td className="px-4 py-2">{payment.paidDate || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
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

const getStatusColor = (status) => {
  switch (status) {
    case 'paid':
      return 'bg-green-100 text-green-800';
    case 'pending':
      return 'bg-yellow-100 text-yellow-800';
    case 'overdue':
      return 'bg-red-100 text-red-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
};
