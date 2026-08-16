'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import api from '@/lib/api';
import { getErrorMessage } from '@/lib/errors';
import AppNav from '@/components/AppNav';
import RequireAuth from '@/components/RequireAuth';
import { PanelState } from '@/components/PageState';

interface Alert {
  id: number;
  ticker: string;
  kind: string;
  message: string;
  triggered_value: number | null;
  read: boolean;
  created_at: string;
}

const KIND_LABELS: Record<string, string> = {
  price_target: 'Price target',
  recommendation_change: 'Rating change',
  score_move: 'Score move',
};

const KIND_STYLES: Record<string, string> = {
  price_target: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  recommendation_change: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
  score_move: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
};

function AlertsPageContent() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [checking, setChecking] = useState(false);

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await api.get<{ unread_count: number; alerts: Alert[] }>('/alerts/');
      setAlerts(data.alerts);
      setUnread(data.unread_count);
    } catch (err) {
      setError(getErrorMessage(err, 'Could not load your alerts.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  // The sweep runs on a timer; this exists so a target set a minute ago can be
  // checked without waiting for it.
  const checkNow = async () => {
    setChecking(true);
    try {
      await api.post('/alerts/check');
      await fetchAlerts();
    } catch (err) {
      setError(getErrorMessage(err, 'Could not check your watchlist.'));
    } finally {
      setChecking(false);
    }
  };

  const markAllRead = async () => {
    try {
      await api.post('/alerts/read-all');
      await fetchAlerts();
    } catch (err) {
      setError(getErrorMessage(err, 'Could not update your alerts.'));
    }
  };

  const markRead = async (id: number) => {
    try {
      await api.post(`/alerts/${id}/read`);
      setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, read: true } : a)));
      setUnread((n) => Math.max(0, n - 1));
    } catch {
      // Non-fatal: the badge corrects itself on the next load.
    }
  };

  return (
    <div className="bg-gray-950 text-white min-h-screen">
      <AppNav />

      <div className="max-w-4xl mx-auto px-6 py-12">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-bold">Alerts</h1>
            <p className="text-gray-400 mt-1">
              What your watchlist has noticed since you last looked.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={checkNow}
              disabled={checking}
              className="bg-gray-800 hover:bg-gray-700 disabled:opacity-50 border border-gray-700 text-sm font-medium px-4 py-2 rounded-lg transition"
            >
              {checking ? 'Checking…' : 'Check now'}
            </button>
            {unread > 0 && (
              <button
                onClick={markAllRead}
                className="bg-blue-600 hover:bg-blue-500 text-sm font-medium px-4 py-2 rounded-lg transition"
              >
                Mark all read
              </button>
            )}
          </div>
        </div>

        <PanelState
          loading={loading}
          error={error}
          isEmpty={alerts.length === 0}
          emptyMessage="No alerts yet. Set a price target on a watchlist item to get one."
          onRetry={fetchAlerts}
        >
          <div className="space-y-3">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className={`border rounded-xl p-4 transition ${
                  alert.read
                    ? 'bg-gray-900/40 border-gray-800'
                    : 'bg-gray-900 border-gray-700'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <Link
                        href={`/chart/${alert.ticker}`}
                        className="font-mono font-bold text-blue-400 hover:text-blue-300"
                      >
                        {alert.ticker}
                      </Link>
                      <span
                        className={`text-[11px] px-2 py-0.5 rounded-full border ${
                          KIND_STYLES[alert.kind] || 'bg-gray-500/15 text-gray-300 border-gray-600'
                        }`}
                      >
                        {KIND_LABELS[alert.kind] || alert.kind}
                      </span>
                      {!alert.read && (
                        <span className="w-2 h-2 rounded-full bg-blue-400" aria-label="Unread" />
                      )}
                    </div>
                    <p className={alert.read ? 'text-gray-400' : 'text-white'}>{alert.message}</p>
                    <p className="text-xs text-gray-600 mt-1.5">
                      {new Date(alert.created_at).toLocaleString()}
                    </p>
                  </div>
                  {!alert.read && (
                    <button
                      onClick={() => markRead(alert.id)}
                      className="text-xs text-gray-400 hover:text-white shrink-0 transition"
                    >
                      Mark read
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </PanelState>
      </div>
    </div>
  );
}

export default function AlertsPage() {
  return (
    <RequireAuth>
      <AlertsPageContent />
    </RequireAuth>
  );
}
