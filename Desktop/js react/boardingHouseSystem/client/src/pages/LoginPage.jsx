import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const LoginPage = () => {
  const [step, setStep] = useState('role'); // role, credentials
  const [role, setRole] = useState(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleRoleSelect = (selectedRole) => {
    setRole(selectedRole);
    setStep('credentials');
    setError('');
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await login(username, password, role);
      navigate('/dashboard');
    } catch (err) {
      setError('Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (step === 'role') {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-blue-500 to-blue-700">
        <div className="bg-white p-12 rounded-lg shadow-2xl max-w-md w-full">
          <h1 className="text-3xl font-bold text-center mb-2 text-gray-800">
            Boarding House System
          </h1>
          <p className="text-center text-gray-600 mb-8">Select your role to continue</p>

          <div className="space-y-4">
            <button
              onClick={() => handleRoleSelect('landlord')}
              className="w-full p-6 border-2 border-gray-300 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition text-center"
            >
              <span className="text-4xl block mb-2">🏢</span>
              <h2 className="text-xl font-bold text-gray-800">Landlord</h2>
              <p className="text-sm text-gray-600 mt-2">Manage tenants and payments</p>
            </button>

            <button
              onClick={() => handleRoleSelect('boarder')}
              className="w-full p-6 border-2 border-gray-300 rounded-lg hover:border-green-500 hover:bg-green-50 transition text-center"
            >
              <span className="text-4xl block mb-2">👤</span>
              <h2 className="text-xl font-bold text-gray-800">Boarder</h2>
              <p className="text-sm text-gray-600 mt-2">View payments and profile</p>
            </button>
          </div>

          <p className="text-center text-xs text-gray-500 mt-8">
            Demo Credentials - Both roles: username/password
          </p>

          <Link
            to="/register"
            className="block text-center mt-6 text-green-600 hover:text-green-800 font-semibold"
          >
            Don't have an account? Register here
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-blue-500 to-blue-700">
      <div className="bg-white p-12 rounded-lg shadow-2xl max-w-md w-full">
        <button
          onClick={() => setStep('role')}
          className="text-blue-600 hover:text-blue-800 text-sm mb-4 flex items-center"
        >
          ← Back
        </button>

        <h1 className="text-3xl font-bold text-center mb-2 text-gray-800">
          {role === 'landlord' ? '🏢 Landlord' : '👤 Boarder'} Login
        </h1>
        <p className="text-center text-gray-600 mb-8">Enter your credentials</p>

        {error && (
          <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-gray-700 font-semibold mb-2">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={role === 'landlord' ? 'landlord' : 'boarder1'}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>

          <div>
            <label className="block text-gray-700 font-semibold mb-2">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="password"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-bold py-2 px-4 rounded-lg transition"
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <p className="text-center text-sm text-gray-600 mt-6">
          Demo credentials:
          <br />
          <strong>{role === 'landlord' ? 'landlord / password' : 'boarder1 / password'}</strong>
        </p>
      </div>
    </div>
  );
};
