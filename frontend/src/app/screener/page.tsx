'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import api from '@/lib/api';

interface ScreenerStock {
  symbol: string;
  companyName: string;
  marketCap: number | null;
  sector: string | null;
  industry: string | null;
  price: number | null;
  beta: number | null;
  volume: number | null;
  lastAnnualDividend: number | null;
  exchangeShortName: string | null;
  country: string | null;
}

const SECTORS = [
  '', 'Technology', 'Healthcare', 'Financial Services', 'Consumer Cyclical',
  'Industrials', 'Communication Services', 'Consumer Defensive',
  'Energy', 'Real Estate', 'Utilities', 'Basic Materials',
];

const EXCHANGES = ['', 'NASDAQ', 'NYSE', 'AMEX'];

const MARKET_CAP_PRESETS = [
  { label: 'Any', min: '', max: '' },
  { label: 'Mega (>200B)', min: '200000000000', max: '' },
  { label: 'Large (10B-200B)', min: '10000000000', max: '200000000000' },
  { label: 'Mid (2B-10B)', min: '2000000000', max: '10000000000' },
  { label: 'Small (300M-2B)', min: '300000000', max: '2000000000' },
  { label: 'Micro (<300M)', min: '', max: '300000000' },
];

function formatMktCap(val: number | null): string {
  if (!val) return 'N/A';
  if (val >= 1e12) return `$${(val / 1e12).toFixed(1)}T`;
  if (val >= 1e9) return `$${(val / 1e9).toFixed(1)}B`;
  if (val >= 1e6) return `$${(val / 1e6).toFixed(0)}M`;
  return `$${val.toLocaleString()}`;
}

export default function ScreenerPage() {
  const [sector, setSector] = useState('');
  const [exchange, setExchange] = useState('');
  const [capPreset, setCapPreset] = useState(0);
  const [priceMin, setPriceMin] = useState('');
  const [priceMax, setPriceMax] = useState('');
  const [limit, setLimit] = useState(50);
  const [results, setResults] = useState<ScreenerStock[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState('');

  const handleScreen = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const params: Record<string, string> = { limit: String(limit) };
      if (sector) params.sector = sector;
      if (exchange) params.exchange = exchange;
      const preset = MARKET_CAP_PRESETS[capPreset];
      if (preset.min) params.marketCapMin = preset.min;
      if (preset.max) params.marketCapMax = preset.max;
      if (priceMin) params.priceMin = priceMin;
      if (priceMax) params.priceMax = priceMax;

      const { data } = await api.get<ScreenerStock[]>('/screener/', { params });
      setResults(data);
      setSearched(true);
    } catch {
      setError('Failed to screen stocks. Please try again.');
    } finally {
      setLoading(false);
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
            <Link href="/market" className="text-sm text-gray-400 hover:text-white transition">Market</Link>
            <Link href="/lists" className="text-sm text-gray-400 hover:text-white transition">Lists</Link>
            <Link href="/dashboard" className="text-sm text-gray-400 hover:text-white transition">Dashboard</Link>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="text-center mb-10">
          <h1 className="text-4xl md:text-5xl font-bold mb-3">Stock Screener</h1>
          <p className="text-gray-400 text-lg">Filter stocks by sector, market cap, price, and more</p>
        </div>

        {/* Filters */}
        <form onSubmit={handleScreen} className="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-8">
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-6">
            <div>
              <label className="block text-xs font-medium text-gray-400 uppercase mb-2">Sector</label>
              <select value={sector} onChange={(e) => setSector(e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 transition">
                {SECTORS.map((s) => <option key={s} value={s}>{s || 'All Sectors'}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 uppercase mb-2">Exchange</label>
              <select value={exchange} onChange={(e) => setExchange(e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 transition">
                {EXCHANGES.map((ex) => <option key={ex} value={ex}>{ex || 'All Exchanges'}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 uppercase mb-2">Market Cap</label>
              <select value={capPreset} onChange={(e) => setCapPreset(Number(e.target.value))} className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 transition">
                {MARKET_CAP_PRESETS.map((p, i) => <option key={i} value={i}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 uppercase mb-2">Min Price ($)</label>
              <input type="number" step="0.01" value={priceMin} onChange={(e) => setPriceMin(e.target.value)} placeholder="0.00" className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 transition" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 uppercase mb-2">Max Price ($)</label>
              <input type="number" step="0.01" value={priceMax} onChange={(e) => setPriceMax(e.target.value)} placeholder="Any" className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 transition" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 uppercase mb-2">Results Limit</label>
              <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 transition">
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end">
            <button type="submit" disabled={loading} className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white font-bold py-2.5 px-8 rounded-xl transition">
              {loading ? 'Screening...' : 'Screen Stocks'}
            </button>
          </div>
        </form>

        {error && <p className="text-red-400 text-center mb-6">{error}</p>}

        {loading && (
          <div className="flex justify-center py-20">
            <div className="animate-spin h-10 w-10 border-4 border-blue-500 border-t-transparent rounded-full" />
          </div>
        )}

        {/* Results Table */}
        {searched && !loading && (
          <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
            <div className="bg-gray-800/50 px-6 py-3 border-b border-gray-800 flex justify-between items-center">
              <h3 className="font-bold">{results.length} stocks found</h3>
            </div>
            {results.length === 0 ? (
              <p className="text-gray-400 text-center py-12">No stocks match your filters. Try broadening your criteria.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-800 text-gray-400">
                      <th className="text-left px-5 py-3 font-medium">Symbol</th>
                      <th className="text-left px-5 py-3 font-medium">Company</th>
                      <th className="text-right px-5 py-3 font-medium">Price</th>
                      <th className="text-right px-5 py-3 font-medium">Mkt Cap</th>
                      <th className="text-left px-5 py-3 font-medium">Sector</th>
                      <th className="text-right px-5 py-3 font-medium">Beta</th>
                      <th className="text-right px-5 py-3 font-medium">Volume</th>
                      <th className="text-center px-5 py-3 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((stock) => (
                      <tr key={stock.symbol} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition">
                        <td className="px-5 py-3 font-bold text-blue-400">{stock.symbol}</td>
                        <td className="px-5 py-3 text-gray-300 max-w-[200px] truncate">{stock.companyName}</td>
                        <td className="px-5 py-3 text-right font-medium">{stock.price ? `$${stock.price.toFixed(2)}` : 'N/A'}</td>
                        <td className="px-5 py-3 text-right">{formatMktCap(stock.marketCap)}</td>
                        <td className="px-5 py-3 text-gray-400 text-xs">{stock.sector || 'N/A'}</td>
                        <td className="px-5 py-3 text-right">{stock.beta?.toFixed(2) ?? 'N/A'}</td>
                        <td className="px-5 py-3 text-right text-gray-400">{stock.volume ? `${(stock.volume / 1e6).toFixed(1)}M` : 'N/A'}</td>
                        <td className="px-5 py-3 text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Link href={`/chart/${stock.symbol}`} className="text-blue-400 hover:text-blue-300 text-xs font-medium">Chart</Link>
                            <span className="text-gray-700">|</span>
                            <Link href={`/dashboard?analyze=${stock.symbol}`} className="text-emerald-400 hover:text-emerald-300 text-xs font-medium">Analyze</Link>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
