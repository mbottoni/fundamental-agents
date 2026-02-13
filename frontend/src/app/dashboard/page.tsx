'use client';

import React, { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import api from '@/lib/api';
import { getErrorMessage } from '@/lib/errors';
import type { AnalysisJob, JobStatus } from '@/types';

const STATUS_LABELS: Record<JobStatus, string> = {
  pending: 'Pending',
  gathering_data: 'Gathering Data',
  analyzing: 'Analyzing',
  generating_report: 'Generating Report',
  complete: 'Complete',
  failed: 'Failed',
};

const STATUS_COLORS: Record<JobStatus, string> = {
  pending: 'bg-yellow-500/20 text-yellow-400',
  gathering_data: 'bg-blue-500/20 text-blue-400',
  analyzing: 'bg-blue-500/20 text-blue-400',
  generating_report: 'bg-purple-500/20 text-purple-400',
  complete: 'bg-green-500/20 text-green-400',
  failed: 'bg-red-500/20 text-red-400',
};

const FREE_ANALYSIS_LIMIT = 3;
const POLL_INTERVAL_MS = 4000;

export default function DashboardPage() {
  const { isAuthenticated, isLoading, user, logout } = useAuth();
  const router = useRouter();
  const [ticker, setTicker] = useState('');
  const [jobs, setJobs] = useState<AnalysisJob[]>([]);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Redirect if not authenticated
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  // Fetch jobs on mount
  const fetchJobs = useCallback(async () => {
    try {
      const response = await api.get<AnalysisJob[]>('/analysis/');
      setJobs(response.data);
    } catch {
      console.error('Failed to fetch jobs');
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      fetchJobs();
    }
  }, [isAuthenticated, fetchJobs]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const canRunAnalysis = useMemo(() => {
    if (!user) return false;
    if (user.subscription_status === 'active') return true;
    return jobs.length < FREE_ANALYSIS_LIMIT;
  }, [user, jobs]);

  const isAnalyzing = activeJobId !== null;

  const pollJobStatus = useCallback(
    (jobId: number) => {
      setActiveJobId(jobId);
      pollIntervalRef.current = setInterval(async () => {
        try {
          const response = await api.get<AnalysisJob>(`/analysis/${jobId}`);
          const job = response.data;

          if (job.status === 'complete') {
            clearInterval(pollIntervalRef.current!);
            pollIntervalRef.current = null;
            setActiveJobId(null);
            await fetchJobs();
            if (job.report_id) {
              router.push(`/report/${job.report_id}`);
            } else {
              setError('Analysis complete, but report is not available yet.');
            }
          } else if (job.status === 'failed') {
            clearInterval(pollIntervalRef.current!);
            pollIntervalRef.current = null;
            setActiveJobId(null);
            await fetchJobs();
            setError('Analysis failed. Please try again with a valid ticker.');
          }
        } catch {
          clearInterval(pollIntervalRef.current!);
          pollIntervalRef.current = null;
          setActiveJobId(null);
          setError('An error occurred while checking analysis status.');
        }
      }, POLL_INTERVAL_MS);
    },
    [fetchJobs, router]
  );

  const handleAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canRunAnalysis || isAnalyzing) return;

    setError('');

    if (!/^[A-Z]{1,5}$/.test(ticker)) {
      setError('Please enter a valid ticker symbol (1-5 letters, e.g. AAPL).');
      return;
    }

    try {
      const response = await api.post<AnalysisJob>('/analysis/', { ticker });
      pollJobStatus(response.data.id);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to start analysis. Please try again.'));
    }
  };

  if (isLoading || !isAuthenticated || !user) {
    return (
      <div className="bg-gray-950 text-white min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-gray-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="bg-gray-950 text-white min-h-screen p-4 md:p-8">
      {/* Header */}
      <header className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
        <div className="flex items-center gap-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
          </Link>
          <div>
            <h1 className="text-3xl font-bold">Dashboard</h1>
            <p className="text-gray-400">Welcome back, {user.email}</p>
          </div>
        </div>
        <button
          onClick={logout}
          className="bg-gray-800 hover:bg-gray-700 text-white font-medium py-2 px-4 rounded-lg transition duration-300 text-sm border border-gray-700"
        >
          Log Out
        </button>
      </header>

      {/* Upgrade Banner */}
      {user.subscription_status !== 'active' && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 text-yellow-300 p-4 rounded-xl mb-8 text-center">
          You are on the free plan ({jobs.length}/{FREE_ANALYSIS_LIMIT} analyses used).{' '}
          <Link href="/pricing" className="font-bold underline ml-1">
            Upgrade to Premium
          </Link>
        </div>
      )}

      {/* New Analysis */}
      <div className="bg-gray-900 border border-gray-800 p-6 rounded-xl mb-8">
        <h2 className="text-xl font-semibold mb-4">New Analysis</h2>
        <form onSubmit={handleAnalysis}>
          <div className="flex gap-4">
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase().replace(/[^A-Z]/g, ''))}
              placeholder="e.g., AAPL"
              maxLength={5}
              className="flex-grow bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 focus:outline-none focus:border-blue-500 transition text-white"
              required
              disabled={isAnalyzing}
            />
            <button
              type="submit"
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white font-bold py-2 px-6 rounded-xl transition duration-300"
              disabled={isAnalyzing || !canRunAnalysis}
            >
              {isAnalyzing ? 'Analyzing...' : 'Analyze'}
            </button>
          </div>
          {error && (
            <p className="text-red-400 mt-3 text-sm">{error}</p>
          )}
          {isAnalyzing && (
            <div className="mt-3 flex items-center gap-2 text-blue-400 text-sm">
              <div className="animate-spin h-4 w-4 border-2 border-blue-400 border-t-transparent rounded-full" />
              Analysis in progress. This may take a minute...
            </div>
          )}
        </form>
      </div>

      {/* Past Jobs */}
      {jobs.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 p-6 rounded-xl">
          <h2 className="text-xl font-semibold mb-4">Analysis History</h2>
          <div className="space-y-3">
            {jobs.map((job) => (
              <div
                key={job.id}
                className="flex items-center justify-between bg-gray-800/50 border border-gray-800 p-4 rounded-xl"
              >
                <div className="flex items-center gap-4">
                  <span className="font-mono font-bold text-lg">{job.ticker}</span>
                  <span
                    className={`text-xs px-2 py-1 rounded-full font-medium ${
                      STATUS_COLORS[job.status] || 'bg-gray-500/20 text-gray-400'
                    }`}
                  >
                    {STATUS_LABELS[job.status] || job.status}
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-gray-400 text-sm">
                    {new Date(job.created_at).toLocaleDateString()}
                  </span>
                  {job.status === 'complete' && job.report_id && (
                    <Link
                      href={`/report/${job.report_id}`}
                      className="text-blue-400 hover:text-blue-300 text-sm font-medium transition"
                    >
                      View Report
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
