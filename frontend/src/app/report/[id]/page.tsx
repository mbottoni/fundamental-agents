'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import api from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import type { Report, ChartData, PricePoint, BarDataPoint } from '@/types';
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  ReferenceLine, Legend, RadialBarChart, RadialBar,
  ComposedChart,
} from 'recharts';

/* ═══════════════════════════════════════════════════════════════
   Shared Styles / Constants
   ═══════════════════════════════════════════════════════════════ */

const COLORS = {
  blue: '#60a5fa',
  cyan: '#22d3ee',
  emerald: '#34d399',
  amber: '#fbbf24',
  red: '#f87171',
  purple: '#a78bfa',
  gray: '#6b7280',
  white: '#ffffff',
  dark: '#111827',
  darkCard: 'rgba(17,24,39,0.6)',
};

const CHART_MARGINS = { top: 10, right: 10, left: 0, bottom: 0 };

/* ─── helpers ────────────────────────────────────────────────── */

const fmtCurrency = (v: number | null | undefined) =>
  v != null ? `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'N/A';

const fmtPct = (v: number | null | undefined) =>
  v != null ? `${v.toFixed(2)}%` : 'N/A';

const fmtNum = (v: number | null | undefined) =>
  v != null ? v.toFixed(2) : 'N/A';

const shortDate = (d: string) => {
  const parts = d.split('-');
  return `${parts[1]}/${parts[2]}`;
};

/* ═══════════════════════════════════════════════════════════════
   Chart Section Wrapper
   ═══════════════════════════════════════════════════════════════ */

function ChartSection({ title, subtitle, children, id }: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  id?: string;
}) {
  return (
    <section id={id} className="glass-card p-6 md:p-8">
      <h2 className="text-xl font-bold text-white mb-1">{title}</h2>
      {subtitle && <p className="text-sm text-gray-400 mb-6">{subtitle}</p>}
      {!subtitle && <div className="mb-6" />}
      {children}
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Custom Tooltip
   ═══════════════════════════════════════════════════════════════ */

function ChartTooltip({ active, payload, label, formatter }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-gray-900/95 backdrop-blur-xl border border-white/10 rounded-xl px-4 py-3 shadow-2xl">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      {payload.map((entry: any, idx: number) => (
        <p key={idx} className="text-sm font-medium" style={{ color: entry.color || COLORS.white }}>
          {entry.name}: {formatter ? formatter(entry.value) : entry.value}
        </p>
      ))}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Price History Chart (with Volume bars)
   ═══════════════════════════════════════════════════════════════ */

function PriceChart({ data, ma }: { data: PricePoint[]; ma: ChartData['moving_averages'] }) {
  if (!data.length) return <p className="text-gray-500">No price data available.</p>;

  const chartData = data.map(p => ({
    date: shortDate(p.date),
    close: p.close,
    volume: p.volume || 0,
  }));

  return (
    <div className="space-y-4">
      {/* Moving average legend */}
      <div className="flex gap-4 text-xs text-gray-400">
        {ma.sma_20 && <span><span className="inline-block w-3 h-0.5 bg-blue-400 mr-1" />SMA 20: {fmtCurrency(ma.sma_20)}</span>}
        {ma.sma_50 && <span><span className="inline-block w-3 h-0.5 bg-cyan-400 mr-1" />SMA 50: {fmtCurrency(ma.sma_50)}</span>}
        {ma.sma_200 && <span><span className="inline-block w-3 h-0.5 bg-amber-400 mr-1" />SMA 200: {fmtCurrency(ma.sma_200)}</span>}
      </div>

      {/* Price area */}
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={chartData} margin={CHART_MARGINS}>
          <defs>
            <linearGradient id="gradPrice" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={COLORS.blue} stopOpacity={0.3} />
              <stop offset="95%" stopColor={COLORS.blue} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis yAxisId="price" domain={['auto', 'auto']} tick={{ fill: '#6b7280', fontSize: 10 }} />
          <YAxis yAxisId="vol" orientation="right" tick={false} />
          <Tooltip content={<ChartTooltip formatter={fmtCurrency} />} />

          <Bar yAxisId="vol" dataKey="volume" fill="rgba(96,165,250,0.08)" barSize={4} />
          <Area yAxisId="price" type="monotone" dataKey="close" stroke={COLORS.blue} fill="url(#gradPrice)" strokeWidth={2} dot={false} />

          {ma.sma_20 && <ReferenceLine yAxisId="price" y={ma.sma_20} stroke={COLORS.blue} strokeDasharray="4 4" strokeOpacity={0.5} />}
          {ma.sma_50 && <ReferenceLine yAxisId="price" y={ma.sma_50} stroke={COLORS.cyan} strokeDasharray="4 4" strokeOpacity={0.5} />}
          {ma.sma_200 && <ReferenceLine yAxisId="price" y={ma.sma_200} stroke={COLORS.amber} strokeDasharray="4 4" strokeOpacity={0.5} />}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   RSI Gauge
   ═══════════════════════════════════════════════════════════════ */

function RSIGauge({ value }: { value: number | null }) {
  if (value == null) return <p className="text-gray-500 text-sm">RSI data unavailable.</p>;

  const color = value > 70 ? COLORS.red : value < 30 ? COLORS.emerald : COLORS.blue;
  const label = value > 70 ? 'Overbought' : value < 30 ? 'Oversold' : 'Neutral';

  const gaugeData = [{ name: 'RSI', value, fill: color }];

  return (
    <div className="flex items-center gap-6">
      <ResponsiveContainer width={140} height={140}>
        <RadialBarChart
          innerRadius="70%"
          outerRadius="100%"
          data={gaugeData}
          startAngle={180}
          endAngle={0}
          barSize={12}
        >
          <RadialBar background={{ fill: 'rgba(255,255,255,0.05)' }} dataKey="value" cornerRadius={6} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div>
        <p className="text-4xl font-bold" style={{ color }}>{value.toFixed(1)}</p>
        <p className="text-sm text-gray-400">{label}</p>
        <div className="flex gap-3 mt-2 text-xs text-gray-500">
          <span>{'<30 Oversold'}</span>
          <span>{'30-70 Neutral'}</span>
          <span>{'>70 Overbought'}</span>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Horizontal Bar Chart (for profitability, growth, etc.)
   ═══════════════════════════════════════════════════════════════ */

function MetricBars({ data, color, formatter }: {
  data: BarDataPoint[];
  color: string;
  formatter?: (v: number) => string;
}) {
  const filtered = data.filter(d => d.value != null);
  if (!filtered.length) return <p className="text-gray-500 text-sm">No data available.</p>;

  return (
    <ResponsiveContainer width="100%" height={filtered.length * 44 + 20}>
      <BarChart data={filtered} layout="vertical" margin={{ ...CHART_MARGINS, left: 80 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
        <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 10 }} />
        <YAxis type="category" dataKey="name" tick={{ fill: '#9ca3af', fontSize: 12 }} width={80} />
        <Tooltip content={<ChartTooltip formatter={formatter || fmtPct} />} />
        <Bar dataKey="value" fill={color} radius={[0, 4, 4, 0]} barSize={20} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Sentiment Donut
   ═══════════════════════════════════════════════════════════════ */

function SentimentDonut({ data, score }: { data: ChartData['sentiment']; score: number }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  if (!total) return <p className="text-gray-500 text-sm">No sentiment data.</p>;

  const label = score > 0.05 ? 'Positive' : score < -0.05 ? 'Negative' : 'Neutral';
  const labelColor = score > 0.05 ? COLORS.emerald : score < -0.05 ? COLORS.red : COLORS.gray;

  return (
    <div className="flex items-center gap-8">
      <ResponsiveContainer width={180} height={180}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={80}
            paddingAngle={3}
            dataKey="value"
            stroke="none"
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip content={<ChartTooltip />} />
        </PieChart>
      </ResponsiveContainer>
      <div className="space-y-3">
        <div>
          <p className="text-sm text-gray-400">Overall Sentiment</p>
          <p className="text-2xl font-bold" style={{ color: labelColor }}>{label}</p>
          <p className="text-sm text-gray-500">Compound: {score.toFixed(3)}</p>
        </div>
        <div className="space-y-1">
          {data.map((d, i) => (
            <div key={i} className="flex items-center gap-2 text-sm">
              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: d.color }} />
              <span className="text-gray-300">{d.name}</span>
              <span className="text-gray-500">{d.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Risk Rating Badge
   ═══════════════════════════════════════════════════════════════ */

function RiskBadge({ rating }: { rating: string }) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    low: { bg: 'bg-emerald-500/10 border-emerald-500/30', text: 'text-emerald-400', label: 'Low Risk' },
    moderate: { bg: 'bg-amber-500/10 border-amber-500/30', text: 'text-amber-400', label: 'Moderate Risk' },
    high: { bg: 'bg-orange-500/10 border-orange-500/30', text: 'text-orange-400', label: 'High Risk' },
    very_high: { bg: 'bg-red-500/10 border-red-500/30', text: 'text-red-400', label: 'Very High Risk' },
  };
  const c = config[rating] || config['moderate'];
  return (
    <span className={`inline-flex items-center px-4 py-1.5 rounded-full border text-sm font-semibold ${c.bg} ${c.text}`}>
      {c.label}
    </span>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Stat Card (small KPI)
   ═══════════════════════════════════════════════════════════════ */

function Stat({ label, value, sub, color }: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/5">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-lg font-bold ${color || 'text-white'}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   DCF Comparison
   ═══════════════════════════════════════════════════════════════ */

function DCFComparison({ dcf }: { dcf: ChartData['dcf'] }) {
  if (!dcf.intrinsic_value || !dcf.current_price) return null;

  const upside = ((dcf.intrinsic_value - dcf.current_price) / dcf.current_price) * 100;
  const isUndervalued = upside > 0;

  const barData = [
    { name: 'Current Price', value: dcf.current_price, fill: COLORS.gray },
    { name: 'Intrinsic Value (DCF)', value: dcf.intrinsic_value, fill: isUndervalued ? COLORS.emerald : COLORS.red },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-baseline gap-3">
        <span className={`text-3xl font-bold ${isUndervalued ? 'text-emerald-400' : 'text-red-400'}`}>
          {upside > 0 ? '+' : ''}{upside.toFixed(1)}%
        </span>
        <span className="text-gray-400 text-sm">{isUndervalued ? 'upside potential' : 'overvalued'}</span>
      </div>
      <ResponsiveContainer width="100%" height={100}>
        <BarChart data={barData} layout="vertical" margin={{ ...CHART_MARGINS, left: 130 }}>
          <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 10 }} />
          <YAxis type="category" dataKey="name" tick={{ fill: '#9ca3af', fontSize: 12 }} width={130} />
          <Tooltip content={<ChartTooltip formatter={fmtCurrency} />} />
          <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={24}>
            {barData.map((entry, idx) => (
              <Cell key={idx} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {dcf.wacc && (
        <p className="text-xs text-gray-500">WACC: {(dcf.wacc * 100).toFixed(2)}%</p>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Trend Signals List
   ═══════════════════════════════════════════════════════════════ */

function TrendSignals({ signals }: { signals: string[] }) {
  if (!signals.length) return null;

  return (
    <div className="space-y-2">
      {signals.map((s, i) => {
        const isBullish = s.toLowerCase().includes('bullish');
        const isBearish = s.toLowerCase().includes('bearish');
        const color = isBullish ? 'text-emerald-400' : isBearish ? 'text-red-400' : 'text-gray-300';
        const bg = isBullish ? 'bg-emerald-500/5' : isBearish ? 'bg-red-500/5' : 'bg-white/5';
        return (
          <div key={i} className={`${bg} rounded-lg px-4 py-2.5 border border-white/5 flex items-center gap-3`}>
            <span className={`text-lg ${isBullish ? 'text-emerald-400' : isBearish ? 'text-red-400' : 'text-gray-400'}`}>
              {isBullish ? '↑' : isBearish ? '↓' : '→'}
            </span>
            <span className={`text-sm ${color}`}>{s}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MAIN REPORT PAGE
   ═══════════════════════════════════════════════════════════════ */

export default function ReportPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeSection, setActiveSection] = useState('');
  const params = useParams();
  const reportId = params.id as string;

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (!reportId || !isAuthenticated) return;
    (async () => {
      try {
        const res = await api.get<Report>(`/reports/${reportId}`);
        setReport(res.data);
      } catch {
        setError('Failed to fetch report. It may not exist or you may not have access.');
      } finally {
        setLoading(false);
      }
    })();
  }, [reportId, isAuthenticated]);

  // Extract sections from markdown for the sidebar nav
  const sections = React.useMemo(() => {
    if (!report?.content) return [];
    const headingRegex = /^## (.+)$/gm;
    const found: { id: string; title: string }[] = [];
    let match;
    while ((match = headingRegex.exec(report.content)) !== null) {
      const title = match[1].trim();
      const id = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
      found.push({ id, title });
    }
    return found;
  }, [report?.content]);

  // Scroll spy
  useEffect(() => {
    if (sections.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      { rootMargin: '-20% 0px -70% 0px' }
    );

    sections.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [sections, report]);

  const handlePrint = useCallback(() => {
    window.print();
  }, []);

  if (authLoading || loading) {
    return (
      <div className="bg-gray-950 text-white min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full" />
          <span className="text-gray-400">Loading report...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-950 text-white min-h-screen">
      {/* ── Top Bar ────────────────────────────────────────── */}
      <nav className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-sm sticky top-0 z-50 print:hidden">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-14">
            <div className="flex items-center gap-4">
              <Link
                href="/dashboard"
                className="text-gray-400 hover:text-white transition flex items-center gap-1.5 text-sm"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                Dashboard
              </Link>
              <span className="text-gray-700">|</span>
              <span className="text-gray-300 font-medium text-sm">Report #{reportId}</span>
            </div>
            <div className="flex items-center gap-3">
              {report && (
                <>
                  <span className="text-gray-500 text-xs">
                    Generated {new Date(report.created_at).toLocaleString()}
                  </span>
                  <button
                    onClick={handlePrint}
                    className="text-gray-400 hover:text-white transition text-sm flex items-center gap-1.5"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0110.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18m0 0l.229 2.523a1.125 1.125 0 01-1.12 1.227H7.231c-.662 0-1.18-.568-1.12-1.227L6.34 18m11.318 0h1.091A2.25 2.25 0 0021 15.75V9.456c0-1.081-.768-2.015-1.837-2.175a48.055 48.055 0 00-1.913-.247M6.34 18H5.25A2.25 2.25 0 013 15.75V9.456c0-1.081.768-2.015 1.837-2.175a48.041 48.041 0 011.913-.247m10.5 0a48.536 48.536 0 00-10.5 0m10.5 0V3.375c0-.621-.504-1.125-1.125-1.125h-8.25c-.621 0-1.125.504-1.125 1.125v3.659M18.75 9.456l-.22-3.003" />
                    </svg>
                    Print
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* ── Error ──────────────────────────────────────────── */}
      {error && (
        <div className="max-w-4xl mx-auto px-4 pt-8">
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 p-4 rounded-xl">
            {error}
          </div>
        </div>
      )}

      {/* ── Layout: sidebar + content ──────────────────────── */}
      {report && (
        <div className="max-w-screen-2xl mx-auto flex">
          {/* Sidebar - Table of Contents */}
          <aside className="hidden lg:block w-64 flex-shrink-0 print:hidden">
            <div className="sticky top-20 px-6 py-8">
              <p className="text-xs uppercase tracking-wider text-gray-500 font-semibold mb-4">Table of Contents</p>
              <nav className="space-y-0.5">
                {sections.map(({ id, title }) => (
                  <a
                    key={id}
                    href={`#${id}`}
                    className={`block text-sm py-1.5 px-3 rounded-md transition ${
                      activeSection === id
                        ? 'bg-blue-500/10 text-blue-400 font-medium'
                        : 'text-gray-500 hover:text-gray-300'
                    }`}
                  >
                    {title}
                  </a>
                ))}
              </nav>
            </div>
          </aside>

          {/* Main content */}
          <main className="flex-1 min-w-0 px-4 sm:px-6 lg:px-8 py-8">
            <article className="bg-gray-900 border border-gray-800 rounded-xl p-6 md:p-10 prose prose-invert prose-sm md:prose-base max-w-none
              prose-headings:scroll-mt-20
              prose-h1:text-2xl prose-h1:md:text-3xl prose-h1:font-bold prose-h1:bg-gradient-to-r prose-h1:from-blue-400 prose-h1:to-cyan-400 prose-h1:bg-clip-text prose-h1:text-transparent prose-h1:pb-2
              prose-h2:text-xl prose-h2:md:text-2xl prose-h2:font-semibold prose-h2:text-white prose-h2:border-b prose-h2:border-gray-800 prose-h2:pb-3 prose-h2:mt-10
              prose-h3:text-lg prose-h3:font-medium prose-h3:text-gray-200 prose-h3:mt-6
              prose-strong:text-white
              prose-li:text-gray-300 prose-li:marker:text-gray-600
              prose-p:text-gray-300
              prose-hr:border-gray-800
            ">
              <ReactMarkdown
                components={{
                  h2: ({ children, ...props }) => {
                    const text = typeof children === 'string' ? children : String(children);
                    const id = text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
                    return <h2 id={id} {...props}>{children}</h2>;
                  },
                }}
              >
                {report.content}
              </ReactMarkdown>
            </article>

            {/* Footer actions */}
            <div className="flex justify-between items-center mt-6 print:hidden">
              <Link
                href="/dashboard"
                className="text-gray-400 hover:text-white transition text-sm"
              >
                &larr; Back to Dashboard
              </Link>
              <button
                onClick={handlePrint}
                className="bg-gray-800 hover:bg-gray-700 text-white text-sm px-4 py-2 rounded-lg transition"
              >
                Print / Export PDF
              </button>
            </div>
          </main>
        </div>
      )}
    </div>
  );
}
