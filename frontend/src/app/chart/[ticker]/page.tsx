'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Area, AreaChart, ReferenceLine,
} from 'recharts';
import api from '@/lib/api';

interface OHLCVPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface ChartResponse {
  ticker: string;
  name: string;
  dates: string[];
  ohlcv: OHLCVPoint[];
  indicators: {
    sma20?: (number | null)[];
    sma50?: (number | null)[];
    sma200?: (number | null)[];
    ema12?: (number | null)[];
    ema26?: (number | null)[];
    rsi?: (number | null)[];
    macd?: {
      macd: (number | null)[];
      signal: (number | null)[];
      histogram: (number | null)[];
    };
    bollinger?: {
      sma: (number | null)[];
      upper: (number | null)[];
      lower: (number | null)[];
    };
  };
}

const TIMEFRAMES = ['1m', '3m', '6m', '1y', '2y', '5y'];
const INDICATORS = ['sma', 'ema', 'rsi', 'macd', 'bollinger'];

export default function ChartPage() {
  const params = useParams();
  const ticker = (params.ticker as string)?.toUpperCase() || '';

  const [data, setData] = useState<ChartResponse | null>(null);
  const [timeframe, setTimeframe] = useState('1y');
  const [activeIndicators, setActiveIndicators] = useState<Set<string>>(new Set(['sma']));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchChart = useCallback(async () => {
    if (!ticker) return;
    setLoading(true);
    setError('');
    try {
      const indicators = Array.from(activeIndicators).join(',');
      const { data: chartData } = await api.get<ChartResponse>(`/chart/${ticker}`, {
        params: { timeframe, indicators },
      });
      setData(chartData);
    } catch {
      setError('Failed to load chart data. Check the ticker symbol.');
    } finally {
      setLoading(false);
    }
  }, [ticker, timeframe, activeIndicators]);

  useEffect(() => {
    fetchChart();
  }, [fetchChart]);

  const toggleIndicator = (ind: string) => {
    setActiveIndicators((prev) => {
      const next = new Set(prev);
      if (next.has(ind)) next.delete(ind);
      else next.add(ind);
      return next;
    });
  };

  // Build merged data for chart
  const chartPoints = data
    ? data.ohlcv.map((p, i) => ({
        date: p.date,
        close: p.close,
        volume: p.volume,
        sma20: data.indicators.sma20?.[i] ?? undefined,
        sma50: data.indicators.sma50?.[i] ?? undefined,
        sma200: data.indicators.sma200?.[i] ?? undefined,
        ema12: data.indicators.ema12?.[i] ?? undefined,
        ema26: data.indicators.ema26?.[i] ?? undefined,
        bbUpper: data.indicators.bollinger?.upper?.[i] ?? undefined,
        bbLower: data.indicators.bollinger?.lower?.[i] ?? undefined,
        bbSma: data.indicators.bollinger?.sma?.[i] ?? undefined,
        rsi: data.indicators.rsi?.[i] ?? undefined,
        macd: data.indicators.macd?.macd?.[i] ?? undefined,
        signal: data.indicators.macd?.signal?.[i] ?? undefined,
        histogram: data.indicators.macd?.histogram?.[i] ?? undefined,
      }))
    : [];

  const lastPrice = chartPoints.length > 0 ? chartPoints[chartPoints.length - 1].close : null;
  const firstPrice = chartPoints.length > 0 ? chartPoints[0].close : null;
  const priceChange = lastPrice && firstPrice ? ((lastPrice - firstPrice) / firstPrice) * 100 : null;

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

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Ticker Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
          <div>
            <h1 className="text-4xl font-bold">{data?.name || ticker}</h1>
            <p className="text-gray-400 mt-1">{ticker}</p>
          </div>
          {lastPrice && (
            <div className="text-right">
              <p className="text-4xl font-bold">${lastPrice.toFixed(2)}</p>
              {priceChange !== null && (
                <p className={`text-lg font-semibold ${priceChange >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)}% ({timeframe})
                </p>
              )}
            </div>
          )}
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-4 mb-6">
          {/* Timeframe */}
          <div className="flex bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`px-4 py-2 text-sm font-medium transition ${timeframe === tf ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
              >
                {tf.toUpperCase()}
              </button>
            ))}
          </div>

          {/* Indicators */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-gray-500 uppercase font-medium">Indicators:</span>
            {INDICATORS.map((ind) => (
              <button
                key={ind}
                onClick={() => toggleIndicator(ind)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition ${
                  activeIndicators.has(ind)
                    ? 'bg-blue-600/20 border-blue-500 text-blue-400'
                    : 'bg-gray-900 border-gray-700 text-gray-400 hover:border-gray-500'
                }`}
              >
                {ind.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {error && <p className="text-red-400 text-center py-10">{error}</p>}

        {loading && (
          <div className="flex justify-center py-20">
            <div className="animate-spin h-10 w-10 border-4 border-blue-500 border-t-transparent rounded-full" />
          </div>
        )}

        {!loading && data && chartPoints.length > 0 && (
          <div className="space-y-6">
            {/* Price Chart */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
              <h3 className="text-lg font-bold mb-4">Price</h3>
              <ResponsiveContainer width="100%" height={400}>
                <AreaChart data={chartPoints}>
                  <defs>
                    <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#6b7280' }} tickLine={false} axisLine={false}
                    tickFormatter={(d) => { const dt = new Date(d); return `${dt.getMonth() + 1}/${dt.getDate()}`; }}
                    interval={Math.floor(chartPoints.length / 8)}
                  />
                  <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11, fill: '#6b7280' }} tickLine={false} axisLine={false}
                    tickFormatter={(v) => `$${v}`}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: '12px', fontSize: '12px' }}
                    labelStyle={{ color: '#9ca3af' }}
                    formatter={(v: number | undefined, name: string | undefined) => [`$${(v ?? 0).toFixed(2)}`, name ?? '']}
                  />
                  <Area type="monotone" dataKey="close" stroke="#3b82f6" strokeWidth={2} fill="url(#priceGradient)" dot={false} name="Price" />
                  {activeIndicators.has('sma') && (
                    <>
                      <Line type="monotone" dataKey="sma20" stroke="#f59e0b" strokeWidth={1.5} dot={false} name="SMA 20" connectNulls />
                      <Line type="monotone" dataKey="sma50" stroke="#10b981" strokeWidth={1.5} dot={false} name="SMA 50" connectNulls />
                      <Line type="monotone" dataKey="sma200" stroke="#ef4444" strokeWidth={1.5} dot={false} name="SMA 200" connectNulls />
                    </>
                  )}
                  {activeIndicators.has('ema') && (
                    <>
                      <Line type="monotone" dataKey="ema12" stroke="#a78bfa" strokeWidth={1.5} dot={false} name="EMA 12" connectNulls />
                      <Line type="monotone" dataKey="ema26" stroke="#f472b6" strokeWidth={1.5} dot={false} name="EMA 26" connectNulls />
                    </>
                  )}
                  {activeIndicators.has('bollinger') && (
                    <>
                      <Line type="monotone" dataKey="bbUpper" stroke="#6366f1" strokeWidth={1} strokeDasharray="4 4" dot={false} name="BB Upper" connectNulls />
                      <Line type="monotone" dataKey="bbLower" stroke="#6366f1" strokeWidth={1} strokeDasharray="4 4" dot={false} name="BB Lower" connectNulls />
                      <Line type="monotone" dataKey="bbSma" stroke="#6366f1" strokeWidth={1.5} dot={false} name="BB Mid" connectNulls />
                    </>
                  )}
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Volume */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
              <h3 className="text-lg font-bold mb-4">Volume</h3>
              <ResponsiveContainer width="100%" height={150}>
                <BarChart data={chartPoints}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#6b7280' }} tickLine={false} axisLine={false}
                    tickFormatter={(d) => { const dt = new Date(d); return `${dt.getMonth() + 1}/${dt.getDate()}`; }}
                    interval={Math.floor(chartPoints.length / 8)}
                  />
                  <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} tickLine={false} axisLine={false}
                    tickFormatter={(v) => `${(v / 1e6).toFixed(0)}M`}
                  />
                  <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: '12px', fontSize: '12px' }}
                    formatter={(v: number | undefined) => [`${((v ?? 0) / 1e6).toFixed(2)}M`, 'Volume'] as [string, string]}
                  />
                  <Bar dataKey="volume" fill="#374151" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* RSI */}
            {activeIndicators.has('rsi') && (
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
                <h3 className="text-lg font-bold mb-4">RSI (14)</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chartPoints}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#6b7280' }} tickLine={false} axisLine={false}
                      tickFormatter={(d) => { const dt = new Date(d); return `${dt.getMonth() + 1}/${dt.getDate()}`; }}
                      interval={Math.floor(chartPoints.length / 8)}
                    />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#6b7280' }} tickLine={false} axisLine={false} />
                    <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="4 4" label={{ value: 'Overbought', fill: '#ef4444', fontSize: 10, position: 'right' }} />
                    <ReferenceLine y={30} stroke="#10b981" strokeDasharray="4 4" label={{ value: 'Oversold', fill: '#10b981', fontSize: 10, position: 'right' }} />
                    <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: '12px', fontSize: '12px' }} />
                    <Line type="monotone" dataKey="rsi" stroke="#a78bfa" strokeWidth={2} dot={false} name="RSI" connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* MACD */}
            {activeIndicators.has('macd') && (
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
                <h3 className="text-lg font-bold mb-4">MACD</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={chartPoints}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#6b7280' }} tickLine={false} axisLine={false}
                      tickFormatter={(d) => { const dt = new Date(d); return `${dt.getMonth() + 1}/${dt.getDate()}`; }}
                      interval={Math.floor(chartPoints.length / 8)}
                    />
                    <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: '12px', fontSize: '12px' }} />
                    <ReferenceLine y={0} stroke="#374151" />
                    <Bar dataKey="histogram" name="Histogram"
                      fill="#374151"
                      radius={[2, 2, 0, 0]}
                    />
                    <Line type="monotone" dataKey="macd" stroke="#3b82f6" strokeWidth={1.5} dot={false} name="MACD" connectNulls />
                    <Line type="monotone" dataKey="signal" stroke="#ef4444" strokeWidth={1.5} dot={false} name="Signal" connectNulls />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Quick Actions */}
            <div className="flex flex-wrap justify-center gap-4 pt-4">
              <Link href={`/dashboard`} className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-xl font-medium transition">
                Run Full Analysis
              </Link>
              <Link href={`/compare?ticker1=${ticker}`} className="bg-gray-800 hover:bg-gray-700 border border-gray-700 text-white px-6 py-3 rounded-xl font-medium transition">
                Compare with another stock
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
