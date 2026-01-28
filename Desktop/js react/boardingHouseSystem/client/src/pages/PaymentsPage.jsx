import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';

export const PaymentsPage = () => {
  const { user } = useAuth();
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('all');

  useEffect(() => {
    fetchPayments();
  }, []);

  const fetchPayments = async () => {
    try {
      const response = await fetch('/api/payments');
      const data = await response.json();
      setPayments(data);
    } catch (error) {
      console.error('Error fetching payments:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAsPaid = async (id) => {
    try {
      const response = await fetch(`/api/payments/${id}/pay`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paymentMethod: 'bank_transfer' })
      });

      if (response.ok) {
        fetchPayments();
      }
    } catch (error) {
      console.error('Error marking payment as paid:', error);
    }
  };

  const filteredPayments = filterStatus === 'all'
    ? payments
    : payments.filter(p => p.status === filterStatus);

  const stats = {
    total: payments.length,
    paid: payments.filter(p => p.status === 'paid').length,
    pending: payments.filter(p => p.status === 'pending').length,
    overdue: payments.filter(p => p.status === 'overdue').length
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-800">Payments Management</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard title="Total" value={stats.total} icon="💳" color="blue" />
        <StatCard title="Paid" value={stats.paid} icon="✅" color="green" />
        <StatCard title="Pending" value={stats.pending} icon="⏳" color="yellow" />
        <StatCard title="Overdue" value={stats.overdue} icon="⚠️" color="red" />
      </div>

      <div className="bg-white p-6 rounded-lg shadow">
        <div className="mb-4 flex gap-2 flex-wrap">
          {['all', 'paid', 'pending', 'overdue'].map(status => (
            <button
              key={status}
              onClick={() => setFilterStatus(status)}
              className={`px-4 py-2 rounded transition ${
                filterStatus === status
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-800 hover:bg-gray-300'
              }`}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="text-center py-8">Loading...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-100">
                <tr>
                  <th className="px-4 py-2 text-left">Tenant</th>
                  <th className="px-4 py-2 text-left">Month</th>
                  <th className="px-4 py-2 text-left">Amount</th>
                  <th className="px-4 py-2 text-left">Due Date</th>
                  <th className="px-4 py-2 text-left">Status</th>
                  <th className="px-4 py-2 text-left">Paid Date</th>
                  {user?.role === 'landlord' && <th className="px-4 py-2 text-left">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {filteredPayments.map(payment => (
                  <tr key={payment.id} className="border-t hover:bg-gray-50">
                    <td className="px-4 py-2">{payment.tenantName}</td>
                    <td className="px-4 py-2">{payment.month}</td>
                    <td className="px-4 py-2">₱{payment.amount}</td>
                    <td className="px-4 py-2">{payment.dueDate}</td>
                    <td className="px-4 py-2">
                      <span className={`px-3 py-1 rounded text-sm font-semibold ${getStatusColor(payment.status)}`}>
                        {payment.status.charAt(0).toUpperCase() + payment.status.slice(1)}
                      </span>
                    </td>
                    <td className="px-4 py-2">{payment.paidDate || '-'}</td>
                    {user?.role === 'landlord' && (
                      <td className="px-4 py-2">
                        {payment.status !== 'paid' && (
                          <button
                            onClick={() => handleMarkAsPaid(payment.id)}
                            className="text-green-600 hover:text-green-800"
                          >
                            Mark Paid
                          </button>
                        )}
                      </td>
                    )}
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
