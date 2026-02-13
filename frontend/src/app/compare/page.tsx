'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import api from '@/lib/api';

interface StockData {
  ticker: string;
  name: string;
  sector: string;
  industry: string;
  description: string;
  price: number | null;
  market_cap: number | null;
  change_pct: number | null;
  pe_ratio: number | null;
  pb_ratio: number | null;
  ps_ratio: number | null;
  ev_ebitda: number | null;
  peg_ratio: number | null;
  gross_margin: number | null;
  operating_margin: number | null;
  net_margin: number | null;
  roe: number | null;
  roa: number | null;
  roic: number | null;
  revenue_growth: number | null;
  net_income_growth: number | null;
  eps_growth: number | null;
  current_ratio: number | null;
  debt_equity: number | null;
  interest_coverage: number | null;
  dividend_yield: number | null;
  payout_ratio: number | null;
  beta: number | null;
  avg_volume: number | null;
}

interface CompareResult {
  stock1: StockData;
  stock2: StockData;
}

const METRIC_GROUPS = [
  {
    label: 'Valuation',
    metrics: [
      { key: 'pe_ratio', name: 'P/E Ratio', format: 'number', lowerBetter: true },
      { key: 'pb_ratio', name: 'P/B Ratio', format: 'number', lowerBetter: true },
      { key: 'ps_ratio', name: 'P/S Ratio', format: 'number', lowerBetter: true },
      { key: 'ev_ebitda', name: 'EV/EBITDA', format: 'number', lowerBetter: true },
      { key: 'peg_ratio', name: 'PEG Ratio', format: 'number', lowerBetter: true },
    ],
  },
  {
    label: 'Profitability',
    metrics: [
      { key: 'gross_margin', name: 'Gross Margin', format: 'pct', lowerBetter: false },
      { key: 'operating_margin', name: 'Operating Margin', format: 'pct', lowerBetter: false },
      { key: 'net_margin', name: 'Net Margin', format: 'pct', lowerBetter: false },
      { key: 'roe', name: 'Return on Equity', format: 'pct', lowerBetter: false },
      { key: 'roa', name: 'Return on Assets', format: 'pct', lowerBetter: false },
      { key: 'roic', name: 'ROIC', format: 'pct', lowerBetter: false },
    ],
  },
  {
    label: 'Growth',
    metrics: [
      { key: 'revenue_growth', name: 'Revenue Growth', format: 'pct', lowerBetter: false },
      { key: 'net_income_growth', name: 'Net Income Growth', format: 'pct', lowerBetter: false },
      { key: 'eps_growth', name: 'EPS Growth', format: 'pct', lowerBetter: false },
    ],
  },
  {
    label: 'Financial Health',
    metrics: [
      { key: 'current_ratio', name: 'Current Ratio', format: 'number', lowerBetter: false },
      { key: 'debt_equity', name: 'Debt/Equity', format: 'number', lowerBetter: true },
      { key: 'interest_coverage', name: 'Interest Coverage', format: 'number', lowerBetter: false },
    ],
  },
  {
    label: 'Dividends & Risk',
    metrics: [
      { key: 'dividend_yield', name: 'Dividend Yield', format: 'pct', lowerBetter: false },
      { key: 'payout_ratio', name: 'Payout Ratio', format: 'pct', lowerBetter: true },
      { key: 'beta', name: 'Beta', format: 'number', lowerBetter: null },
    ],
  },
];

function formatValue(val: number | null, format: string): string {
  if (val === null || val === undefined) return 'N/A';
  if (format === 'pct') return `${(val * 100).toFixed(1)}%`;
  return val.toFixed(2);
}

function formatMarketCap(val: number | null): string {
  if (!val) return 'N/A';
  if (val >= 1e12) return `$${(val / 1e12).toFixed(2)}T`;
  if (val >= 1e9) return `$${(val / 1e9).toFixed(2)}B`;
  if (val >= 1e6) return `$${(val / 1e6).toFixed(2)}M`;
  return `$${val.toLocaleString()}`;
}

function getWinnerClass(
  v1: number | null,
  v2: number | null,
  lowerBetter: boolean | null,
  side: 'left' | 'right'
): string {
  if (v1 === null || v2 === null || lowerBetter === null) return '';
  const leftWins = lowerBetter ? v1 < v2 : v1 > v2;
  if (v1 === v2) return '';
  if (side === 'left' && leftWins) return 'text-emerald-400 font-bold';
  if (side === 'right' && !leftWins) return 'text-emerald-400 font-bold';
  return '';
}

export default function ComparePage() {
  const [ticker1, setTicker1] = useState('');
  const [ticker2, setTicker2] = useState('');
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleCompare = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker1 || !ticker2) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const { data } = await api.get<CompareResult>('/compare/', {
        params: { ticker1: ticker1.toUpperCase(), ticker2: ticker2.toUpperCase() },
      });
      setResult(data);
    } catch {
      setError('Failed to compare stocks. Please check the ticker symbols.');
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
            <Link href="/screener" className="text-sm text-gray-400 hover:text-white transition">Screener</Link>
            <Link href="/market" className="text-sm text-gray-400 hover:text-white transition">Market</Link>
            <Link href="/lists" className="text-sm text-gray-400 hover:text-white transition">Lists</Link>
            <Link href="/dashboard" className="text-sm text-gray-400 hover:text-white transition">Dashboard</Link>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="text-center mb-10">
          <h1 className="text-4xl md:text-5xl font-bold mb-3">Stock Comparison</h1>
          <p className="text-gray-400 text-lg">Compare two stocks side-by-side across 20+ key metrics</p>
        </div>

        {/* Input Form */}
        <form onSubmit={handleCompare} className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-12">
          <input
            type="text"
            value={ticker1}
            onChange={(e) => setTicker1(e.target.value.toUpperCase().replace(/[^A-Z.]/g, ''))}
            placeholder="e.g. AAPL"
            className="bg-gray-900 border border-gray-700 rounded-xl px-5 py-3 text-center text-lg font-bold w-40 focus:outline-none focus:border-blue-500 transition"
            maxLength={6}
          />
          <span className="text-gray-500 font-bold text-2xl">vs</span>
          <input
            type="text"
            value={ticker2}
            onChange={(e) => setTicker2(e.target.value.toUpperCase().replace(/[^A-Z.]/g, ''))}
            placeholder="e.g. MSFT"
            className="bg-gray-900 border border-gray-700 rounded-xl px-5 py-3 text-center text-lg font-bold w-40 focus:outline-none focus:border-blue-500 transition"
            maxLength={6}
          />
          <button
            type="submit"
            disabled={loading || !ticker1 || !ticker2}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white font-bold py-3 px-8 rounded-xl transition"
          >
            {loading ? 'Comparing...' : 'Compare'}
          </button>
        </form>

        {error && <p className="text-red-400 text-center mb-8">{error}</p>}

        {loading && (
          <div className="flex justify-center py-20">
            <div className="animate-spin h-10 w-10 border-4 border-blue-500 border-t-transparent rounded-full" />
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-8">
            {/* Header Cards */}
            <div className="grid md:grid-cols-2 gap-6">
              {[result.stock1, result.stock2].map((stock) => (
                <div key={stock.ticker} className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h2 className="text-2xl font-bold">{stock.ticker}</h2>
                      <p className="text-gray-400 text-sm">{stock.name}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-2xl font-bold">${stock.price?.toFixed(2) ?? 'N/A'}</p>
                      <p className={`text-sm font-semibold ${(stock.change_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {stock.change_pct !== null ? `${stock.change_pct >= 0 ? '+' : ''}${stock.change_pct.toFixed(2)}%` : 'N/A'}
                      </p>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <p className="text-gray-500 text-xs uppercase">Sector</p>
                      <p className="font-medium">{stock.sector}</p>
                    </div>
                    <div>
                      <p className="text-gray-500 text-xs uppercase">Market Cap</p>
                      <p className="font-medium">{formatMarketCap(stock.market_cap)}</p>
                    </div>
                    <div>
                      <p className="text-gray-500 text-xs uppercase">Avg Volume</p>
                      <p className="font-medium">{stock.avg_volume ? `${(stock.avg_volume / 1e6).toFixed(1)}M` : 'N/A'}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Metric Groups */}
            {METRIC_GROUPS.map((group) => (
              <div key={group.label} className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
                <div className="bg-gray-800/50 px-6 py-3 border-b border-gray-800">
                  <h3 className="font-bold text-lg">{group.label}</h3>
                </div>
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-800 text-sm text-gray-400">
                      <th className="text-left px-6 py-3 font-medium">Metric</th>
                      <th className="text-center px-6 py-3 font-medium">{result.stock1.ticker}</th>
                      <th className="text-center px-6 py-3 font-medium">{result.stock2.ticker}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.metrics.map((m) => {
                      const v1 = (result.stock1 as unknown as Record<string, unknown>)[m.key] as number | null;
                      const v2 = (result.stock2 as unknown as Record<string, unknown>)[m.key] as number | null;
                      return (
                        <tr key={m.key} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition">
                          <td className="px-6 py-3 text-sm text-gray-300">{m.name}</td>
                          <td className={`px-6 py-3 text-sm text-center ${getWinnerClass(v1, v2, m.lowerBetter, 'left')}`}>
                            {formatValue(v1, m.format)}
                          </td>
                          <td className={`px-6 py-3 text-sm text-center ${getWinnerClass(v1, v2, m.lowerBetter, 'right')}`}>
                            {formatValue(v2, m.format)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ))}

            {/* Action Buttons */}
            <div className="flex justify-center gap-4 pt-4">
              <Link
                href={`/chart/${result.stock1.ticker}`}
                className="bg-gray-800 hover:bg-gray-700 border border-gray-700 text-white px-6 py-3 rounded-xl text-sm font-medium transition"
              >
                Chart {result.stock1.ticker}
              </Link>
              <Link
                href={`/chart/${result.stock2.ticker}`}
                className="bg-gray-800 hover:bg-gray-700 border border-gray-700 text-white px-6 py-3 rounded-xl text-sm font-medium transition"
              >
                Chart {result.stock2.ticker}
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
