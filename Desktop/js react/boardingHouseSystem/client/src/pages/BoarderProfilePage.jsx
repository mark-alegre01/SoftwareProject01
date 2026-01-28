import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';

export const BoarderProfilePage = () => {
  const { user } = useAuth();
  const [tenant, setTenant] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTenant();
  }, []);

  const fetchTenant = async () => {
    try {
      const response = await fetch(`/api/tenants/${user?.tenantId}`);
      if (response.ok) {
        const data = await response.json();
        setTenant(data);
      }
    } catch (error) {
      console.error('Error fetching tenant:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-800 mb-6">My Profile</h1>

      <div className="bg-white p-8 rounded-lg shadow">
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">Full Name</label>
              <p className="text-lg text-gray-900">{tenant?.name}</p>
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">Room Number</label>
              <p className="text-lg text-gray-900">{tenant?.roomNumber}</p>
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">Email</label>
              <p className="text-lg text-gray-900">{tenant?.email}</p>
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">Phone</label>
              <p className="text-lg text-gray-900">{tenant?.phone}</p>
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">Move-in Date</label>
              <p className="text-lg text-gray-900">{tenant?.moveInDate}</p>
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">Monthly Rate</label>
              <p className="text-lg text-gray-900 font-bold text-green-600">₱{tenant?.monthlyRate}</p>
            </div>
          </div>

          <div className="bg-blue-50 p-4 rounded border-l-4 border-blue-500">
            <p className="text-sm text-gray-700">
              <strong>Status:</strong> {tenant?.status === 'active' ? '✅ Active' : '❌ Inactive'}
            </p>
          </div>

          <div className="text-gray-600 text-sm">
            <p>To update your information, please contact your landlord.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
