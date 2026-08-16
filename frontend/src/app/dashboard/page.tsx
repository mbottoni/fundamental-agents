'use client';

import React, { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import api from '@/lib/api';
import { getErrorMessage } from '@/lib/errors';
import type { AnalysisJob, JobStatus } from '@/types';
import AppNav from '@/components/AppNav';
import RequireAuth from '@/components/RequireAuth';

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

// Polling starts responsive and eases off, so a slow analysis does not hold a
// request open every few seconds for minutes on end.
const POLL_INITIAL_MS = 3000;
const POLL_MAX_MS = 15000;
const POLL_BACKOFF = 1.4;
// An analysis that has not finished by now is not going to; the backend fails
// interrupted jobs on restart, but nothing rescues a hung one mid-flight.
const POLL_TIMEOUT_MS = 5 * 60 * 1000;

function DashboardPageContent() {
  const { isAuthenticated, isLoading, user, logout } = useAuth();
  const router = useRouter();
  const [ticker, setTicker] = useState('');
  const [jobs, setJobs] = useState<AnalysisJob[]>([]);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [limits, setLimits] = useState<{ used: number; limit: number | null }>({
    used: 0,
    limit: null,
  });
  const pollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

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

  // The daily cap is a server setting; duplicating it here meant the two could
  // disagree after a config change.
  const fetchLimits = useCallback(async () => {
    try {
      const { data } = await api.get<{
        total_analyses: number;
        free_tier_daily_limit: number | null;
        analyses_today: number;
      }>('/dashboard/stats');
      setLimits({ used: data.analyses_today, limit: data.free_tier_daily_limit });
    } catch {
      // Non-fatal: the banner is hidden rather than showing a wrong number.
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) fetchLimits();
  }, [isAuthenticated, fetchLimits]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
      }
    };
  }, []);

  const canRunAnalysis = useMemo(() => {
    if (!user) return false;
    if (user.subscription_status === 'active') return true;
    if (limits.limit === null) return true; // unknown limit: let the server decide
    return limits.used < limits.limit;
  }, [user, limits]);

  const isAnalyzing = activeJobId !== null;

  const pollJobStatus = useCallback(
    (jobId: number) => {
      setActiveJobId(jobId);

      const startedAt = Date.now();
      let delay = POLL_INITIAL_MS;

      const stop = () => {
        if (pollTimeoutRef.current) {
          clearTimeout(pollTimeoutRef.current);
          pollTimeoutRef.current = null;
        }
        setActiveJobId(null);
      };

      const tick = async () => {
        try {
          const { data: job } = await api.get<AnalysisJob>(`/analysis/${jobId}`);

          if (job.status === 'complete') {
            stop();
            await fetchJobs();
            await fetchLimits();
            if (job.report_id) {
              router.push(`/report/${job.report_id}`);
            } else {
              setError('Analysis complete, but the report is not available yet.');
            }
            return;
          }

          if (job.status === 'failed') {
            stop();
            await fetchJobs();
            await fetchLimits();
            setError(
              job.error_message ||
                'Analysis failed. Please try again with a valid ticker.'
            );
            return;
          }

          if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
            stop();
            await fetchJobs();
            setError(
              'This analysis is taking longer than expected. It will keep running — ' +
                'check the history below in a few minutes.'
            );
            return;
          }

          // Ease off as the wait grows rather than asking every few seconds
          // for the whole run.
          delay = Math.min(delay * POLL_BACKOFF, POLL_MAX_MS);
          pollTimeoutRef.current = setTimeout(tick, delay);
        } catch {
          stop();
          setError('An error occurred while checking analysis status.');
        }
      };

      pollTimeoutRef.current = setTimeout(tick, delay);
    },
    [fetchJobs, fetchLimits, router]
  );

  const handleAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canRunAnalysis || isAnalyzing) return;

    setError('');

    if (!/^[A-Z0-9]{1,6}([.-][A-Z0-9]{1,4})?$/.test(ticker)) {
      setError('Please enter a valid ticker symbol (e.g. AAPL, BRK.B).');
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
      <div className="-mx-4 md:-mx-8 -mt-4 md:-mt-8 mb-8">
        <AppNav />
      </div>
      <header className="mb-8">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-gray-400">Welcome back, {user.email}</p>
      </header>

      {/* Upgrade Banner */}
      {user.subscription_status !== 'active' && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 text-yellow-300 p-4 rounded-xl mb-8 text-center">
          You are on the free plan ({limits.used}/{limits.limit ?? '—'} analyses used today).{' '}
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
              onChange={(e) => setTicker(e.target.value.toUpperCase().replace(/[^A-Z0-9.-]/g, ''))}
              placeholder="e.g., AAPL or BRK.B"
              maxLength={11}
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
                className="bg-gray-800/50 border border-gray-800 p-4 rounded-xl"
              >
                <div className="flex items-center justify-between">
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
                {/* Tell the user why it failed rather than leaving a bare badge. */}
                {job.status === 'failed' && job.error_message && (
                  <p className="mt-3 text-sm text-red-300/80 leading-relaxed">
                    {job.error_message}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardPageContent />
    </RequireAuth>
  );
}
