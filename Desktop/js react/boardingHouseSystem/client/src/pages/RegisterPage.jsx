import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';

export const RegisterPage = () => {
  const [step, setStep] = useState('details'); // details, confirm
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    confirmPassword: '',
    name: '',
    email: '',
    phone: '',
    roomNumber: '',
    monthlyRate: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    setError('');
  };

  const validateForm = () => {
    if (!formData.username || !formData.password || !formData.name || !formData.email || !formData.phone || !formData.roomNumber || !formData.monthlyRate) {
      setError('All fields are required');
      return false;
    }
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return false;
    }
    if (formData.password.length < 6) {
      setError('Password must be at least 6 characters');
      return false;
    }
    if (!/\S+@\S+\.\S+/.test(formData.email)) {
      setError('Please enter a valid email address');
      return false;
    }
    if (isNaN(formData.monthlyRate) || formData.monthlyRate <= 0) {
      setError('Monthly rate must be a valid positive number');
      return false;
    }
    return true;
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          username: formData.username,
          password: formData.password,
          name: formData.name,
          email: formData.email,
          phone: formData.phone,
          roomNumber: formData.roomNumber,
          monthlyRate: parseFloat(formData.monthlyRate)
        })
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Registration failed');
      }

      // Move to confirmation step
      setStep('confirm');
    } catch (err) {
      setError(err.message || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (step === 'confirm') {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-green-500 to-green-700">
        <div className="bg-white p-12 rounded-lg shadow-2xl max-w-md w-full text-center">
          <div className="text-6xl mb-4">✓</div>
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Registration Successful!</h1>
          <p className="text-gray-600 mb-6">
            Welcome, <strong>{formData.name}</strong>! Your boarder account has been created.
          </p>
          
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6 text-left">
            <p className="text-sm text-gray-700 mb-2"><strong>Room:</strong> {formData.roomNumber}</p>
            <p className="text-sm text-gray-700 mb-2"><strong>Monthly Rate:</strong> ₱{parseFloat(formData.monthlyRate).toLocaleString()}</p>
            <p className="text-sm text-gray-700"><strong>Email:</strong> {formData.email}</p>
          </div>

          <p className="text-sm text-gray-600 mb-6">
            You can now login with your credentials to access your dashboard.
          </p>

          <Link
            to="/login"
            className="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-3 rounded-lg transition block"
          >
            Go to Login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-green-500 to-green-700 p-4">
      <div className="bg-white p-8 rounded-lg shadow-2xl max-w-md w-full">
        <Link
          to="/login"
          className="text-green-600 hover:text-green-800 text-sm mb-4 inline-flex items-center"
        >
          ← Back to Login
        </Link>

        <h1 className="text-3xl font-bold text-center mb-2 text-gray-800">
          👤 Boarder Registration
        </h1>
        <p className="text-center text-gray-600 mb-6">Create your account</p>

        {error && (
          <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleRegister} className="space-y-4">
          {/* Personal Information */}
          <div>
            <label className="block text-gray-700 font-semibold mb-2 text-sm">Full Name</label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-green-500"
              placeholder="John Doe"
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-gray-700 font-semibold mb-2 text-sm">Email</label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-green-500"
              placeholder="john@example.com"
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-gray-700 font-semibold mb-2 text-sm">Phone Number</label>
            <input
              type="tel"
              name="phone"
              value={formData.phone}
              onChange={handleChange}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-green-500"
              placeholder="09123456789"
              disabled={loading}
            />
          </div>

          {/* Room Information */}
          <div>
            <label className="block text-gray-700 font-semibold mb-2 text-sm">Room Number</label>
            <input
              type="text"
              name="roomNumber"
              value={formData.roomNumber}
              onChange={handleChange}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-green-500"
              placeholder="101"
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-gray-700 font-semibold mb-2 text-sm">Monthly Rate (₱)</label>
            <input
              type="number"
              name="monthlyRate"
              value={formData.monthlyRate}
              onChange={handleChange}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-green-500"
              placeholder="5000"
              disabled={loading}
            />
          </div>

          {/* Account Information */}
          <hr className="my-4" />

          <div>
            <label className="block text-gray-700 font-semibold mb-2 text-sm">Username</label>
            <input
              type="text"
              name="username"
              value={formData.username}
              onChange={handleChange}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-green-500"
              placeholder="johndoe"
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-gray-700 font-semibold mb-2 text-sm">Password</label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-green-500"
              placeholder="••••••"
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-gray-700 font-semibold mb-2 text-sm">Confirm Password</label>
            <input
              type="password"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-green-500"
              placeholder="••••••"
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-3 rounded-lg transition disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {loading ? 'Creating Account...' : 'Register'}
          </button>
        </form>

        <p className="text-center text-sm text-gray-600 mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-green-600 hover:text-green-800 font-semibold">
            Login here
          </Link>
        </p>
      </div>
    </div>
  );
};
