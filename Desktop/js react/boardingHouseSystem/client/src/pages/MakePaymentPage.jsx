import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

export const MakePaymentPage = () => {
  const { user } = useAuth();
  const [formData, setFormData] = useState({
    paymentMethod: 'gcash'
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [tenantPayment, setTenantPayment] = useState(null);
  const [gcashLink, setGcashLink] = useState(null);

  // Fetch tenant's pending payment
  useEffect(() => {
    const fetchTenantPayment = async () => {
      try {
        const response = await fetch(`/api/payments/tenant/${user?.tenantId}`);
        const payments = await response.json();
        const pendingPayment = payments.find(p => p.status === 'pending');
        if (pendingPayment) {
          setTenantPayment(pendingPayment);
        }
      } catch (error) {
        console.error('Error fetching payment:', error);
      }
    };
    
    if (user?.tenantId) {
      fetchTenantPayment();
    }
  }, [user]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
  };

  const handleInitiateGCashPayment = async () => {
    if (!tenantPayment) {
      setMessage('No pending payment found');
      return;
    }

    setLoading(true);
    setMessage('');

    try {
      const response = await fetch('/api/gcash/initiate-gcash', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          paymentId: tenantPayment.id,
          amount: tenantPayment.amount,
          tenantId: user.tenantId
        })
      });

      const data = await response.json();

      if (!response.ok) {
        setMessage(`Error: ${data.error}`);
        return;
      }

      // Store reference number and redirect to GCash
      setMessage(`✅ Payment link generated! Redirecting to GCash...`);
      setGcashLink({
        paymentLink: data.paymentLink,
        qrCode: data.qrCode,
        referenceNumber: data.referenceNumber,
        expiresAt: data.expiresAt
      });

      // Redirect to GCash payment link after 2 seconds
      setTimeout(() => {
        window.location.href = data.paymentLink;
      }, 2000);

    } catch (error) {
      setMessage('Error initiating payment: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleManualPaymentSubmit = async (e) => {
    e.preventDefault();
    
    if (!tenantPayment) {
      setMessage('No pending payment found');
      return;
    }

    setLoading(true);
    setMessage('');

    try {
      // This would submit a manual bank transfer or other payment method
      // For now, just show a message
      setMessage('✅ Payment submitted! Your landlord will verify it shortly.');
      
      setTimeout(() => {
        setMessage('');
      }, 5000);
    } catch (error) {
      setMessage('Error processing payment: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const getPaymentAmount = () => {
    return tenantPayment?.amount || 5000;
  };

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-800 mb-6">Make Payment</h1>

      <div className="grid md:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="md:col-span-2">
          {/* Message Alert */}
          {message && (
            <div className={`mb-6 p-4 rounded font-semibold ${message.includes('✅') ? 'bg-green-100 text-green-700 border-l-4 border-green-500' : 'bg-red-100 text-red-700 border-l-4 border-red-500'}`}>
              {message}
            </div>
          )}

          {/* GCash Option - Highlighted */}
          <div className="bg-gradient-to-r from-blue-50 to-cyan-50 p-8 rounded-lg shadow-md border-2 border-blue-200 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold text-blue-900 flex items-center gap-2">
                <span className="text-3xl">📱</span> GCash Payment
              </h2>
              <span className="bg-green-500 text-white px-3 py-1 rounded-full text-sm font-semibold">RECOMMENDED</span>
            </div>

            <p className="text-gray-700 mb-4">
              Fastest and most secure way to pay. Pay directly from your GCash app.
            </p>

            {/* Payment Summary */}
            <div className="bg-white p-4 rounded-lg mb-4 border-l-4 border-blue-500">
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-gray-600 text-sm">Amount Due</p>
                  <p className="text-3xl font-bold text-blue-600">₱{getPaymentAmount().toLocaleString()}</p>
                </div>
                <div className="text-right">
                  <p className="text-gray-600 text-sm">{tenantPayment?.month}</p>
                  <p className="text-sm text-gray-500">Due: {tenantPayment?.dueDate}</p>
                </div>
              </div>
            </div>

            {/* GCash Steps */}
            <div className="bg-white p-4 rounded-lg mb-4 space-y-3">
              <h3 className="font-semibold text-gray-800">How it works:</h3>
              <div className="space-y-2 text-sm">
                <div className="flex gap-3">
                  <span className="bg-blue-500 text-white rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-xs font-bold">1</span>
                  <p className="text-gray-700">Click "Pay with GCash" button below</p>
                </div>
                <div className="flex gap-3">
                  <span className="bg-blue-500 text-white rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-xs font-bold">2</span>
                  <p className="text-gray-700">You'll be redirected to GCash</p>
                </div>
                <div className="flex gap-3">
                  <span className="bg-blue-500 text-white rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-xs font-bold">3</span>
                  <p className="text-gray-700">Complete payment in GCash app</p>
                </div>
                <div className="flex gap-3">
                  <span className="bg-blue-500 text-white rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-xs font-bold">4</span>
                  <p className="text-gray-700">Automatic confirmation upon completion</p>
                </div>
              </div>
            </div>

            {/* GCash Payment Button */}
            <button
              onClick={handleInitiateGCashPayment}
              disabled={loading || !tenantPayment}
              className="w-full py-4 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 text-white font-bold rounded-lg transition disabled:bg-gray-400 disabled:cursor-not-allowed text-lg"
            >
              {loading ? '⏳ Processing...' : '💳 Pay with GCash'}
            </button>
          </div>

          {/* Other Payment Methods - Collapsed */}
          <details className="bg-gray-50 p-6 rounded-lg border border-gray-200">
            <summary className="font-bold text-gray-800 cursor-pointer hover:text-blue-600">
              Other Payment Methods
            </summary>

            <form onSubmit={handleManualPaymentSubmit} className="mt-6 space-y-6">
              <div>
                <label className="block text-gray-700 font-semibold mb-2">Select Payment Method</label>
                <select
                  name="paymentMethod"
                  value={formData.paymentMethod}
                  onChange={handleChange}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="bank_transfer">Bank Transfer</option>
                  <option value="cash">Cash on Hand</option>
                  <option value="check">Check</option>
                </select>
              </div>

              {/* Bank Transfer Details */}
              {formData.paymentMethod === 'bank_transfer' && (
                <div className="p-4 bg-green-50 rounded-lg border-l-4 border-green-500">
                  <h3 className="font-bold text-green-900 mb-3">🏦 Bank Transfer</h3>
                  <div className="text-sm text-gray-700 space-y-2 bg-white p-3 rounded">
                    <p><strong>Bank Name:</strong> Sample Bank</p>
                    <p><strong>Account Number:</strong> 1234567890</p>
                    <p><strong>Account Name:</strong> Boarding House Owner</p>
                  </div>
                </div>
              )}

              {/* Cash Payment Info */}
              {formData.paymentMethod === 'cash' && (
                <div className="p-4 bg-yellow-50 rounded-lg border-l-4 border-yellow-500">
                  <h3 className="font-bold text-yellow-900 flex items-center gap-2">
                    <span>💰</span> Cash Payment
                  </h3>
                  <p className="text-sm text-gray-700 mt-2">Please pay directly to your landlord with exact amount.</p>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full px-6 py-3 bg-gray-600 text-white font-bold rounded hover:bg-gray-700 disabled:bg-gray-400 transition"
              >
                {loading ? 'Processing...' : 'Submit Payment'}
              </button>
            </form>
          </details>
        </div>

        {/* Right Sidebar */}
        <div className="space-y-4">
          {/* Payment Info */}
          {tenantPayment && (
            <div className="bg-blue-50 p-4 rounded-lg border-l-4 border-blue-500">
              <h3 className="font-bold text-gray-800 mb-3">📋 Payment Details</h3>
              <div className="text-sm text-gray-700 space-y-2">
                <div className="flex justify-between">
                  <span>Month:</span>
                  <span className="font-semibold">{tenantPayment.month}</span>
                </div>
                <div className="flex justify-between">
                  <span>Amount:</span>
                  <span className="font-semibold">₱{tenantPayment.amount.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span>Due Date:</span>
                  <span className="font-semibold">{tenantPayment.dueDate}</span>
                </div>
                <div className="flex justify-between">
                  <span>Status:</span>
                  <span className="font-semibold text-red-600">{tenantPayment.status.toUpperCase()}</span>
                </div>
              </div>
            </div>
          )}

          {/* Safety Tips */}
          <div className="bg-green-50 p-4 rounded-lg border-l-4 border-green-500">
            <h3 className="font-bold text-gray-800 mb-2">✅ Safety Tips</h3>
            <ul className="text-xs text-gray-700 space-y-1">
              <li>✓ Only use official GCash app</li>
              <li>✓ Never share your PIN</li>
              <li>✓ Verify merchant details</li>
              <li>✓ Keep confirmation receipt</li>
            </ul>
          </div>

          {/* GCash Link Card */}
          {gcashLink && (
            <div className="bg-purple-50 p-4 rounded-lg border-2 border-purple-300">
              <h3 className="font-bold text-gray-800 mb-2">🔗 Payment Link</h3>
              <p className="text-xs text-gray-600 mb-2">
                <strong>Reference:</strong> {gcashLink.referenceNumber}
              </p>
              {gcashLink.qrCode && (
                <div className="mb-3">
                  <img src={gcashLink.qrCode} alt="GCash QR Code" className="w-full" />
                </div>
              )}
              <p className="text-xs text-gray-500">
                Link expires at {new Date(gcashLink.expiresAt).toLocaleString()}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
