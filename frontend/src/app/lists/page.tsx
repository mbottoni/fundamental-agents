'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import api from '@/lib/api';

interface ListSummary {
  id: string;
  name: string;
  description: string;
  count: number;
}

interface ListStock {
  ticker: string;
  name: string;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  market_cap: number | null;
  volume: number | null;
}

interface ListDetail {
  id: string;
  name: string;
  description: string;
  stocks: ListStock[];
}

function formatMktCap(val: number | null): string {
  if (!val) return 'N/A';
  if (val >= 1e12) return `$${(val / 1e12).toFixed(1)}T`;
  if (val >= 1e9) return `$${(val / 1e9).toFixed(1)}B`;
  if (val >= 1e6) return `$${(val / 1e6).toFixed(0)}M`;
  return `$${val.toLocaleString()}`;
}

const THEME_COLORS: Record<string, string> = {
  'magnificent-7': 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  'dividend-aristocrats': 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  'ai-leaders': 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  'clean-energy': 'bg-green-500/20 text-green-400 border-green-500/30',
  'healthcare-innovation': 'bg-pink-500/20 text-pink-400 border-pink-500/30',
  'fintech': 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  'semiconductors': 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
  'value-stocks': 'bg-teal-500/20 text-teal-400 border-teal-500/30',
};

export default function ListsPage() {
  const [lists, setLists] = useState<ListSummary[]>([]);
  const [selectedList, setSelectedList] = useState<string | null>(null);
  const [detail, setDetail] = useState<ListDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    async function fetchLists() {
      try {
        const { data } = await api.get<ListSummary[]>('/market/lists');
        setLists(data);
      } finally {
        setLoading(false);
      }
    }
    fetchLists();
  }, []);

  const loadDetail = async (id: string) => {
    if (selectedList === id) {
      setSelectedList(null);
      setDetail(null);
      return;
    }
    setSelectedList(id);
    setDetailLoading(true);
    try {
      const { data } = await api.get<ListDetail>(`/market/lists/${id}`);
      setDetail(data);
    } finally {
      setDetailLoading(false);
    }
  };

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
            <Link href="/market" className="text-sm text-gray-400 hover:text-white transition">Market</Link>
            <Link href="/dashboard" className="text-sm text-gray-400 hover:text-white transition">Dashboard</Link>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="text-center mb-10">
          <h1 className="text-4xl md:text-5xl font-bold mb-3">Stock Lists</h1>
          <p className="text-gray-400 text-lg">Curated collections of stocks by theme and strategy</p>
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <div className="animate-spin h-10 w-10 border-4 border-blue-500 border-t-transparent rounded-full" />
          </div>
        ) : (
          <div className="space-y-4">
            {lists.map((list) => {
              const colorClass = THEME_COLORS[list.id] || 'bg-gray-500/20 text-gray-400 border-gray-500/30';
              const isOpen = selectedList === list.id;

              return (
                <div key={list.id} className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
                  <button
                    onClick={() => loadDetail(list.id)}
                    className="w-full flex items-center justify-between p-6 hover:bg-gray-800/30 transition text-left"
                  >
                    <div className="flex items-center gap-4">
                      <span className={`px-3 py-1 rounded-full text-xs font-bold border ${colorClass}`}>
                        {list.count} stocks
                      </span>
                      <div>
                        <h3 className="text-lg font-bold">{list.name}</h3>
                        <p className="text-gray-400 text-sm">{list.description}</p>
                      </div>
                    </div>
                    <svg className={`w-5 h-5 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>

                  {isOpen && (
                    <div className="border-t border-gray-800">
                      {detailLoading ? (
                        <div className="flex justify-center py-8"><div className="animate-spin h-8 w-8 border-3 border-blue-500 border-t-transparent rounded-full" /></div>
                      ) : detail ? (
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="border-b border-gray-800 text-gray-400">
                                <th className="text-left px-5 py-3 font-medium">Ticker</th>
                                <th className="text-left px-5 py-3 font-medium">Name</th>
                                <th className="text-right px-5 py-3 font-medium">Price</th>
                                <th className="text-right px-5 py-3 font-medium">Change</th>
                                <th className="text-right px-5 py-3 font-medium">Mkt Cap</th>
                                <th className="text-center px-5 py-3 font-medium">Actions</th>
                              </tr>
                            </thead>
                            <tbody>
                              {detail.stocks.map((stock) => (
                                <tr key={stock.ticker} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition">
                                  <td className="px-5 py-3 font-bold text-blue-400">{stock.ticker}</td>
                                  <td className="px-5 py-3 text-gray-300">{stock.name}</td>
                                  <td className="px-5 py-3 text-right font-medium">{stock.price ? `$${stock.price.toFixed(2)}` : 'N/A'}</td>
                                  <td className={`px-5 py-3 text-right font-medium ${(stock.change_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                    {stock.change_pct != null ? `${stock.change_pct >= 0 ? '+' : ''}${stock.change_pct.toFixed(2)}%` : 'N/A'}
                                  </td>
                                  <td className="px-5 py-3 text-right text-gray-400">{formatMktCap(stock.market_cap)}</td>
                                  <td className="px-5 py-3 text-center">
                                    <div className="flex items-center justify-center gap-2">
                                      <Link href={`/chart/${stock.ticker}`} className="text-blue-400 hover:text-blue-300 text-xs font-medium">Chart</Link>
                                      <span className="text-gray-700">|</span>
                                      <Link href={`/dashboard`} className="text-emerald-400 hover:text-emerald-300 text-xs font-medium">Analyze</Link>
                                    </div>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : null}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
