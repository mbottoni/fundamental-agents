'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import api from '@/lib/api';

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

export default function MarketPage() {
  const [tab, setTab] = useState<TabKey>('gainers');
  const [gainers, setGainers] = useState<Mover[]>([]);
  const [losers, setLosers] = useState<Mover[]>([]);
  const [active, setActive] = useState<Mover[]>([]);
  const [sectors, setSectors] = useState<SectorData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchAll() {
      setLoading(true);
      try {
        const [g, l, a, s] = await Promise.all([
          api.get<Mover[]>('/market/gainers').catch(() => ({ data: [] })),
          api.get<Mover[]>('/market/losers').catch(() => ({ data: [] })),
          api.get<Mover[]>('/market/most-active').catch(() => ({ data: [] })),
          api.get<SectorData[]>('/market/sector-performance').catch(() => ({ data: [] })),
        ]);
        setGainers(g.data);
        setLosers(l.data);
        setActive(a.data);
        setSectors(s.data);
      } finally {
        setLoading(false);
      }
    }
    fetchAll();
  }, []);

  const tabData: Record<TabKey, Mover[]> = { gainers, losers, active };
  const currentData = tabData[tab];

  return (
    <div className="bg-gray-950 text-white min-h-screen">
      {/* Navigation */}
      <nav className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-lg sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 flex justify-between items-center h-16">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
            <span className="text-lg font-bold">StockAnalyzer</span>
          </Link>
          <div className="flex items-center gap-6">
            <Link href="/compare" className="text-sm text-gray-400 hover:text-white transition">Compare</Link>
            <Link href="/screener" className="text-sm text-gray-400 hover:text-white transition">Screener</Link>
            <Link href="/lists" className="text-sm text-gray-400 hover:text-white transition">Lists</Link>
            <Link href="/dashboard" className="text-sm text-gray-400 hover:text-white transition">Dashboard</Link>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="text-center mb-10">
          <h1 className="text-4xl md:text-5xl font-bold mb-3">Market Overview</h1>
          <p className="text-gray-400 text-lg">Track market movers, sector performance, and trending stocks</p>
        </div>

        {/* Sector Performance */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-8">
          <h2 className="text-xl font-bold mb-4">Sector Performance</h2>
          {loading ? (
            <div className="flex justify-center py-8"><div className="animate-spin h-8 w-8 border-3 border-blue-500 border-t-transparent rounded-full" /></div>
          ) : sectors.length === 0 ? (
            <p className="text-gray-500 text-center py-4">Sector data unavailable</p>
          ) : (
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
          )}
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

          {loading ? (
            <div className="flex justify-center py-16"><div className="animate-spin h-10 w-10 border-4 border-blue-500 border-t-transparent rounded-full" /></div>
          ) : (
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
          )}
        </div>
      </div>
    </div>
  );
}
