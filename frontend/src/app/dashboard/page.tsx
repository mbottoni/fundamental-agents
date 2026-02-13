'use client';

import React, { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import api from '@/lib/api';
import { getErrorMessage } from '@/lib/errors';
import type { AnalysisJob, JobStatus, WatchlistItem, DashboardStats, SearchResult } from '@/types';

/* ── Constants ─────────────────────────────────────────────── */

const STATUS_LABELS: Record<JobStatus, string> = {
  pending: 'Pending',
  gathering_data: 'Gathering Data',
  analyzing: 'Analyzing',
  generating_report: 'Generating Report',
  complete: 'Complete',
  failed: 'Failed',
};

const STATUS_COLORS: Record<JobStatus, string> = {
  pending: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  gathering_data: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  analyzing: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  generating_report: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  complete: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30',
};

const FREE_ANALYSIS_LIMIT = 3;
const POLL_INTERVAL_MS = 4000;

/* ── Page ──────────────────────────────────────────────────── */

export default function DashboardPage() {
  const { isAuthenticated, isLoading, user, logout } = useAuth();
  const router = useRouter();

  // State
  const [ticker, setTicker] = useState('');
  const [jobs, setJobs] = useState<AnalysisJob[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [watchlistTicker, setWatchlistTicker] = useState('');
  const [watchlistError, setWatchlistError] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const [activeTab, setActiveTab] = useState<'analyze' | 'history' | 'watchlist'>('analyze');
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Redirect if not authenticated
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  // Fetch data on mount
  const fetchJobs = useCallback(async () => {
    try {
      const response = await api.get<AnalysisJob[]>('/analysis/');
      setJobs(response.data);
    } catch {
      /* ignore */
    }
  }, []);

  const fetchWatchlist = useCallback(async () => {
    try {
      const response = await api.get<WatchlistItem[]>('/watchlist/');
      setWatchlist(response.data);
    } catch {
      /* ignore */
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const response = await api.get<DashboardStats>('/dashboard/stats');
      setStats(response.data);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      fetchJobs();
      fetchWatchlist();
      fetchStats();
    }
  }, [isAuthenticated, fetchJobs, fetchWatchlist, fetchStats]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    };
  }, []);

  const canRunAnalysis = useMemo(() => {
    if (!user) return false;
    if (user.subscription_status === 'active') return true;
    return jobs.length < FREE_ANALYSIS_LIMIT;
  }, [user, jobs]);

  const isAnalyzing = activeJobId !== null;

  /* ── Polling ─────────────────────────────────────────────── */

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
            await fetchStats();
            if (job.report_id) {
              router.push(`/report/${job.report_id}`);
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
          setError('Error checking analysis status.');
        }
      }, POLL_INTERVAL_MS);
    },
    [fetchJobs, fetchStats, router]
  );

  /* ── Handlers ────────────────────────────────────────────── */

  const handleAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canRunAnalysis || isAnalyzing) return;
    setError('');
    const t = ticker.trim().toUpperCase();
    if (!/^[A-Z]{1,5}$/.test(t)) {
      setError('Enter a valid ticker (1-5 letters, e.g. AAPL).');
      return;
    }
    try {
      const response = await api.post<AnalysisJob>('/analysis/', { ticker: t });
      pollJobStatus(response.data.id);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to start analysis.'));
    }
  };

  const handleQuickAnalyze = async (t: string) => {
    if (isAnalyzing) return;
    setTicker(t);
    setError('');
    try {
      const response = await api.post<AnalysisJob>('/analysis/', { ticker: t });
      pollJobStatus(response.data.id);
      setActiveTab('analyze');
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to start analysis.'));
    }
  };

  const handleAddToWatchlist = async (e: React.FormEvent) => {
    e.preventDefault();
    setWatchlistError('');
    const t = watchlistTicker.trim().toUpperCase();
    if (!/^[A-Z]{1,10}$/.test(t)) {
      setWatchlistError('Enter a valid ticker symbol.');
      return;
    }
    try {
      await api.post('/watchlist/', { ticker: t });
      setWatchlistTicker('');
      fetchWatchlist();
      fetchStats();
    } catch (err) {
      setWatchlistError(getErrorMessage(err, 'Failed to add to watchlist.'));
    }
  };

  const handleRemoveFromWatchlist = async (itemId: number) => {
    try {
      await api.delete(`/watchlist/${itemId}`);
      fetchWatchlist();
      fetchStats();
    } catch {
      /* ignore */
    }
  };

  // Ticker search (debounced)
  const handleTickerInput = (value: string) => {
    const clean = value.toUpperCase().replace(/[^A-Z]/g, '');
    setTicker(clean);
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    if (clean.length >= 1) {
      searchTimeoutRef.current = setTimeout(async () => {
        try {
          const resp = await api.get<SearchResult[]>(`/dashboard/search?q=${clean}`);
          setSearchResults(resp.data.slice(0, 6));
          setShowSearch(true);
        } catch {
          setSearchResults([]);
        }
      }, 300);
    } else {
      setSearchResults([]);
      setShowSearch(false);
    }
  };

  /* ── Render guards ───────────────────────────────────────── */

  if (isLoading || !isAuthenticated || !user) {
    return (
      <div className="bg-gray-950 text-white min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full" />
          <span className="text-gray-400">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  const isPremium = user.subscription_status === 'active';

  /* ── JSX ─────────────────────────────────────────────────── */

  return (
    <div className="bg-gray-950 text-white min-h-screen">
      {/* ── Top Navigation Bar ─────────────────────────────── */}
      <nav className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-3">
              <span className="text-xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                StockAnalyzer AI
              </span>
              {isPremium && (
                <span className="text-[10px] font-bold bg-gradient-to-r from-amber-400 to-orange-500 text-black px-2 py-0.5 rounded-full uppercase tracking-wide">
                  Premium
                </span>
              )}
            </div>
            <div className="flex items-center gap-4">
              <span className="text-gray-400 text-sm hidden sm:block">{user.email}</span>
              <button
                onClick={logout}
                className="text-gray-400 hover:text-white text-sm transition"
              >
                Log Out
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* ── Upgrade Banner ───────────────────────────────── */}
        {!isPremium && (
          <div className="bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/20 rounded-xl p-4 mb-8 flex flex-col sm:flex-row items-center justify-between gap-3">
            <p className="text-amber-200 text-sm">
              Free plan: {jobs.length}/{FREE_ANALYSIS_LIMIT} analyses used.
              Upgrade for unlimited analyses and priority processing.
            </p>
            <Link
              href="/pricing"
              className="bg-gradient-to-r from-amber-500 to-orange-500 text-black font-semibold px-5 py-2 rounded-lg text-sm hover:opacity-90 transition whitespace-nowrap"
            >
              Upgrade to Premium
            </Link>
          </div>
        )}

        {/* ── Stats Cards ──────────────────────────────────── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard label="Total Analyses" value={stats?.total_analyses ?? 0} icon="chart" />
          <StatCard label="Completed" value={stats?.completed_analyses ?? 0} icon="check" color="emerald" />
          <StatCard label="Watchlist" value={stats?.watchlist_count ?? 0} icon="eye" color="blue" />
          <StatCard label="Tickers Covered" value={stats?.tickers_analyzed?.length ?? 0} icon="layers" color="purple" />
        </div>

        {/* ── Tab Navigation ───────────────────────────────── */}
        <div className="flex gap-1 bg-gray-900 p-1 rounded-xl mb-6 w-fit">
          {(['analyze', 'history', 'watchlist'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-5 py-2 rounded-lg text-sm font-medium transition ${
                activeTab === tab
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {tab === 'analyze' ? 'New Analysis' : tab === 'history' ? 'History' : 'Watchlist'}
            </button>
          ))}
        </div>

        {/* ── Tab: New Analysis ────────────────────────────── */}
        {activeTab === 'analyze' && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-1">Run Stock Analysis</h2>
            <p className="text-gray-400 text-sm mb-5">
              Enter a ticker symbol to generate a comprehensive AI-powered analysis report
              with valuation, technicals, risk metrics, and more.
            </p>
            <form onSubmit={handleAnalysis}>
              <div className="relative flex gap-3">
                <div className="relative flex-grow">
                  <input
                    type="text"
                    value={ticker}
                    onChange={(e) => handleTickerInput(e.target.value)}
                    onBlur={() => setTimeout(() => setShowSearch(false), 200)}
                    onFocus={() => searchResults.length > 0 && setShowSearch(true)}
                    placeholder="Search ticker (e.g. AAPL, TSLA, MSFT)"
                    maxLength={5}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 transition placeholder:text-gray-500"
                    required
                    disabled={isAnalyzing}
                  />
                  {/* Search Dropdown */}
                  {showSearch && searchResults.length > 0 && (
                    <div className="absolute top-full left-0 right-0 mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-20 overflow-hidden">
                      {searchResults.map((r) => (
                        <button
                          key={r.symbol}
                          type="button"
                          className="w-full text-left px-4 py-2.5 hover:bg-gray-700/50 transition flex justify-between items-center"
                          onMouseDown={() => {
                            setTicker(r.symbol);
                            setShowSearch(false);
                          }}
                        >
                          <span>
                            <span className="font-mono font-semibold text-white">{r.symbol}</span>
                            <span className="text-gray-400 text-sm ml-2">{r.name}</span>
                          </span>
                          <span className="text-gray-500 text-xs">{r.stockExchange}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  type="submit"
                  className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-semibold py-3 px-8 rounded-lg transition whitespace-nowrap"
                  disabled={isAnalyzing || !canRunAnalysis}
                >
                  {isAnalyzing ? 'Analyzing...' : 'Analyze'}
                </button>
              </div>
              {error && <p className="text-red-400 mt-3 text-sm">{error}</p>}
              {isAnalyzing && (
                <div className="mt-4 bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
                  <div className="flex items-center gap-3 text-blue-400 text-sm">
                    <div className="animate-spin h-4 w-4 border-2 border-blue-400 border-t-transparent rounded-full" />
                    <span>Analysis in progress — gathering data, computing metrics, generating report...</span>
                  </div>
                  <div className="mt-3 w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
                    <div className="bg-blue-500 h-full rounded-full animate-pulse" style={{ width: '60%' }} />
                  </div>
                </div>
              )}
            </form>

            {/* Quick access from watchlist */}
            {watchlist.length > 0 && (
              <div className="mt-6 pt-5 border-t border-gray-800">
                <p className="text-gray-400 text-xs uppercase tracking-wider font-medium mb-3">Quick Analyze from Watchlist</p>
                <div className="flex flex-wrap gap-2">
                  {watchlist.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => handleQuickAnalyze(item.ticker)}
                      disabled={isAnalyzing}
                      className="bg-gray-800 hover:bg-gray-700 disabled:opacity-50 border border-gray-700 px-3 py-1.5 rounded-lg text-sm font-mono transition"
                    >
                      {item.ticker}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Tab: History ─────────────────────────────────── */}
        {activeTab === 'history' && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="p-6 border-b border-gray-800">
              <h2 className="text-lg font-semibold">Analysis History</h2>
              <p className="text-gray-400 text-sm">All your past and current analyses</p>
            </div>
            {jobs.length === 0 ? (
              <div className="p-12 text-center text-gray-500">
                <p className="text-lg mb-2">No analyses yet</p>
                <p className="text-sm">Run your first analysis to see results here.</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-800">
                {jobs.map((job) => (
                  <div key={job.id} className="flex items-center justify-between px-6 py-4 hover:bg-gray-800/50 transition">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-gray-800 flex items-center justify-center font-mono font-bold text-sm">
                        {job.ticker.slice(0, 4)}
                      </div>
                      <div>
                        <p className="font-semibold">{job.ticker}</p>
                        <p className="text-gray-500 text-xs">{new Date(job.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className={`text-xs px-2.5 py-1 rounded-full font-medium border ${STATUS_COLORS[job.status] || 'bg-gray-500/20 text-gray-400'}`}>
                        {STATUS_LABELS[job.status] || job.status}
                      </span>
                      {job.status === 'complete' && job.report_id && (
                        <Link
                          href={`/report/${job.report_id}`}
                          className="text-blue-400 hover:text-blue-300 text-sm font-medium transition"
                        >
                          View Report &rarr;
                        </Link>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Tab: Watchlist ───────────────────────────────── */}
        {activeTab === 'watchlist' && (
          <div className="space-y-6">
            {/* Add to watchlist */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
              <h2 className="text-lg font-semibold mb-4">Add to Watchlist</h2>
              <form onSubmit={handleAddToWatchlist} className="flex gap-3">
                <input
                  type="text"
                  value={watchlistTicker}
                  onChange={(e) => setWatchlistTicker(e.target.value.toUpperCase().replace(/[^A-Z]/g, ''))}
                  placeholder="Ticker symbol (e.g. AAPL)"
                  maxLength={10}
                  className="flex-grow bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500 transition placeholder:text-gray-500"
                  required
                />
                <button
                  type="submit"
                  className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-2.5 px-6 rounded-lg transition"
                >
                  Add
                </button>
              </form>
              {watchlistError && <p className="text-red-400 mt-2 text-sm">{watchlistError}</p>}
            </div>

            {/* Watchlist items */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
              <div className="p-6 border-b border-gray-800">
                <h2 className="text-lg font-semibold">Your Watchlist</h2>
                <p className="text-gray-400 text-sm">{watchlist.length} ticker{watchlist.length !== 1 ? 's' : ''} tracked</p>
              </div>
              {watchlist.length === 0 ? (
                <div className="p-12 text-center text-gray-500">
                  <p className="text-lg mb-2">Watchlist is empty</p>
                  <p className="text-sm">Add tickers to quickly run analyses or track stocks.</p>
                </div>
              ) : (
                <div className="divide-y divide-gray-800">
                  {watchlist.map((item) => (
                    <div key={item.id} className="flex items-center justify-between px-6 py-4 hover:bg-gray-800/50 transition">
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center font-mono font-bold text-blue-400 text-sm">
                          {item.ticker.slice(0, 4)}
                        </div>
                        <div>
                          <p className="font-semibold">{item.ticker}</p>
                          <p className="text-gray-500 text-xs">Added {new Date(item.created_at).toLocaleDateString()}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleQuickAnalyze(item.ticker)}
                          disabled={isAnalyzing}
                          className="text-blue-400 hover:text-blue-300 text-sm font-medium transition disabled:opacity-50"
                        >
                          Analyze
                        </button>
                        <span className="text-gray-700">|</span>
                        <button
                          onClick={() => handleRemoveFromWatchlist(item.id)}
                          className="text-red-400 hover:text-red-300 text-sm transition"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

/* ── Stat Card Component ──────────────────────────────────── */

function StatCard({
  label,
  value,
  icon,
  color = 'gray',
}: {
  label: string;
  value: number;
  icon: 'chart' | 'check' | 'eye' | 'layers';
  color?: 'gray' | 'emerald' | 'blue' | 'purple';
}) {
  const colors = {
    gray: 'from-gray-500/20 to-gray-500/5 border-gray-700',
    emerald: 'from-emerald-500/20 to-emerald-500/5 border-emerald-800',
    blue: 'from-blue-500/20 to-blue-500/5 border-blue-800',
    purple: 'from-purple-500/20 to-purple-500/5 border-purple-800',
  };

  const iconColors = {
    gray: 'text-gray-400',
    emerald: 'text-emerald-400',
    blue: 'text-blue-400',
    purple: 'text-purple-400',
  };

  const icons = {
    chart: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
      </svg>
    ),
    check: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    eye: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
    layers: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6.429 9.75L2.25 12l4.179 2.25m0-4.5l5.571 3 5.571-3m-11.142 0L2.25 7.5 12 2.25l9.75 5.25-4.179 2.25m0 0L12 12.75 6.429 9.75m11.142 0l4.179 2.25-9.75 5.25-9.75-5.25 4.179-2.25" />
      </svg>
    ),
  };

  return (
    <div className={`bg-gradient-to-br ${colors[color]} border rounded-xl p-5`}>
      <div className="flex items-center justify-between mb-3">
        <span className={iconColors[color]}>{icons[icon]}</span>
      </div>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-gray-400 text-sm mt-0.5">{label}</p>
    </div>
  );
}
