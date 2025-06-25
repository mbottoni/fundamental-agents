'use client';

import React, { useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import api from '@/lib/api';

const DashboardPage = () => {
  const { isAuthenticated, user, logout, token } = useAuth();
  const router = useRouter();
  const [ticker, setTicker] = useState('');
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    } else {
      api.get('/analysis/', { headers: { Authorization: `Bearer ${token}` } })
        .then(response => setJobs(response.data))
        .catch(err => console.error("Failed to fetch jobs", err));
    }
  }, [isAuthenticated, router, token]);

  const canRunAnalysis = useMemo(() => {
    if (!user) return false;
    if (user.subscription_status === 'active') return true;
    return jobs.length < 3;
  }, [user, jobs]);

  const handleAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canRunAnalysis) {
      setError('You have reached your analysis limit. Please upgrade to premium.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const response = await api.post('/analysis/', { ticker }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const { id: jobId } = response.data;
      
      const interval = setInterval(async () => {
        try {
          const statusResponse = await api.get(`/analysis/${jobId}`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          if (statusResponse.data.status === 'complete') {
            clearInterval(interval);
            setLoading(false);
            router.push(`/report/${statusResponse.data.report_id}`);
          } else if (statusResponse.data.status === 'failed') {
            clearInterval(interval);
            setLoading(false);
            setError('Analysis failed. Please try again.');
          }
        } catch (pollError) {
          clearInterval(interval);
          setLoading(false);
          setError('An error occurred while checking analysis status.');
        }
      }, 5000);

    } catch (err: any) {
      setLoading(false);
      setError(err.response?.data?.detail || 'An error occurred during analysis.');
    }
  };

  if (!isAuthenticated || !user) {
    return null; // or a loading spinner
  }

  return (
    <div className="bg-gray-900 text-white min-h-screen p-8">
      <header className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-gray-400">Welcome back, {user.email}!</p>
        </div>
        <button
          onClick={logout}
          className="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 rounded-lg transition duration-300"
        >
          Logout
        </button>
      </header>
      
      {user.subscription_status !== 'active' && (
        <div className="bg-yellow-500 text-black p-4 rounded-lg mb-8 text-center">
          You are on the free plan. You have used {jobs.length} of 3 free analyses. 
          <Link href="/pricing" className="font-bold underline ml-2">Upgrade to Premium</Link>
        </div>
      )}

      <div className="bg-gray-800 p-6 rounded-lg">
        <h2 className="text-xl font-semibold mb-4">New Analysis</h2>
        <form onSubmit={handleAnalysis}>
          <div className="flex gap-4">
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="e.g., AAPL"
              className="flex-grow bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
              required
            />
            <button
              type="submit"
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-lg transition duration-300 disabled:bg-gray-500"
              disabled={loading || !canRunAnalysis}
            >
              {loading ? 'Analyzing...' : 'Analyze'}
            </button>
          </div>
          {error && <p className="text-red-500 mt-4">{error}</p>}
        </form>
      </div>
      
      {/* List of past reports will go here */}
    </div>
  );
};

export default DashboardPage;
