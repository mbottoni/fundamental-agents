'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import api from '@/lib/api';
import { getErrorMessage } from '@/lib/errors';
import AppNav from '@/components/AppNav';
import RequireAuth from '@/components/RequireAuth';
import { PanelState } from '@/components/PageState';

interface Mover {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changesPercentage: number;
}

interface SectorData {
  sector: string;
  changesPercentage: string;
}

type TabKey = 'gainers' | 'losers' | 'active';

function MarketPageContent() {
  const [tab, setTab] = useState<TabKey>('gainers');
  const [gainers, setGainers] = useState<Mover[]>([]);
  const [losers, setLosers] = useState<Mover[]>([]);
  const [active, setActive] = useState<Mover[]>([]);
  const [sectors, setSectors] = useState<SectorData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Failures used to be swallowed into empty arrays, so a provider outage
  // rendered a blank page that read as "the market has no movers today".
  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [g, l, a, s] = await Promise.all([
        api.get<Mover[]>('/market/gainers'),
        api.get<Mover[]>('/market/losers'),
        api.get<Mover[]>('/market/most-active'),
        api.get<SectorData[]>('/market/sector-performance'),
      ]);
      setGainers(g.data);
      setLosers(l.data);
      setActive(a.data);
      setSectors(s.data);
    } catch (err) {
      setError(getErrorMessage(err, 'Market data is unavailable right now.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const tabData: Record<TabKey, Mover[]> = { gainers, losers, active };
  const currentData = tabData[tab];

  return (
    <div className="bg-gray-950 text-white min-h-screen">
      <AppNav />

      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="text-center mb-10">
          <h1 className="text-4xl md:text-5xl font-bold mb-3">Market Overview</h1>
          <p className="text-gray-400 text-lg">Track market movers, sector performance, and trending stocks</p>
        </div>

        {/* Sector Performance */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-8">
          <h2 className="text-xl font-bold mb-4">Sector Performance</h2>
          <PanelState
            loading={loading}
            error={error}
            isEmpty={sectors.length === 0}
            emptyMessage="Sector data is unavailable."
            onRetry={fetchAll}
          >
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {sectors.map((s) => {
                const pct = parseFloat(s.changesPercentage);
                const isPositive = pct >= 0;
                return (
                  <div key={s.sector} className="flex items-center justify-between bg-gray-800/50 border border-gray-800 rounded-xl px-4 py-3">
                    <span className="text-sm font-medium">{s.sector}</span>
                    <span className={`text-sm font-bold ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
                      {isPositive ? '+' : ''}{pct.toFixed(2)}%
                    </span>
                  </div>
                );
              })}
            </div>
          </PanelState>
        </div>

        {/* Market Movers Tabs */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
          <div className="flex border-b border-gray-800">
            {(['gainers', 'losers', 'active'] as TabKey[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 py-3 text-sm font-bold transition ${tab === t ? 'bg-gray-800 text-white' : 'text-gray-400 hover:text-white'}`}
              >
                {t === 'gainers' ? 'Top Gainers' : t === 'losers' ? 'Top Losers' : 'Most Active'}
              </button>
            ))}
          </div>

          <PanelState
            loading={loading}
            error={error}
            isEmpty={currentData.length === 0}
            emptyMessage="No movers to show right now."
            onRetry={fetchAll}
          >
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800 text-gray-400">
                    <th className="text-left px-5 py-3 font-medium">#</th>
                    <th className="text-left px-5 py-3 font-medium">Symbol</th>
                    <th className="text-left px-5 py-3 font-medium">Name</th>
                    <th className="text-right px-5 py-3 font-medium">Price</th>
                    <th className="text-right px-5 py-3 font-medium">Change</th>
                    <th className="text-right px-5 py-3 font-medium">Change %</th>
                    <th className="text-center px-5 py-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {currentData.map((stock, i) => (
                    <tr key={stock.symbol} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition">
                      <td className="px-5 py-3 text-gray-500">{i + 1}</td>
                      <td className="px-5 py-3 font-bold text-blue-400">{stock.symbol}</td>
                      <td className="px-5 py-3 text-gray-300 max-w-[200px] truncate">{stock.name}</td>
                      <td className="px-5 py-3 text-right font-medium">${stock.price?.toFixed(2)}</td>
                      <td className={`px-5 py-3 text-right font-medium ${stock.change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {stock.change >= 0 ? '+' : ''}{stock.change?.toFixed(2)}
                      </td>
                      <td className={`px-5 py-3 text-right font-bold ${stock.changesPercentage >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {stock.changesPercentage >= 0 ? '+' : ''}{stock.changesPercentage?.toFixed(2)}%
                      </td>
                      <td className="px-5 py-3 text-center">
                        <div className="flex items-center justify-center gap-2">
                          <Link href={`/chart/${stock.symbol}`} className="text-blue-400 hover:text-blue-300 text-xs font-medium">Chart</Link>
                          <span className="text-gray-700">|</span>
                          <Link href={`/dashboard`} className="text-emerald-400 hover:text-emerald-300 text-xs font-medium">Analyze</Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </PanelState>
        </div>
      </div>
    </div>
  );
}

export default function MarketPage() {
  return (
    <RequireAuth>
      <MarketPageContent />
    </RequireAuth>
  );
}
