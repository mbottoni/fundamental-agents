import Link from 'next/link';
import Image from 'next/image';

export default function Home() {
  return (
    <div className="bg-gray-950 text-white min-h-screen">
      {/* ── Navigation ─────────────────────────────────────── */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-transparent">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="flex justify-between items-center h-20">
            <Link href="/" className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-white/10 backdrop-blur-sm flex items-center justify-center border border-white/20">
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
              </div>
              <span className="text-lg font-semibold tracking-tight">StockAnalyzer AI</span>
            </Link>
            <div className="flex items-center gap-3">
              <Link
                href="/login"
                className="text-sm text-gray-300 hover:text-white transition px-4 py-2"
              >
                Log In
              </Link>
              <Link
                href="/register"
                className="text-sm bg-white/10 hover:bg-white/20 backdrop-blur-sm border border-white/20 text-white px-5 py-2 rounded-lg transition"
              >
                Sign Up
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* ── Hero Section ───────────────────────────────────── */}
      <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
        {/* Background Image */}
        <div className="absolute inset-0">
          <Image
            src="/mountain.jpg"
            alt="Mountain landscape"
            fill
            className="object-cover"
            priority
            quality={85}
          />
          {/* Gradient overlays */}
          <div className="absolute inset-0 bg-gradient-to-b from-gray-950/70 via-gray-950/50 to-gray-950" />
          <div className="absolute inset-0 bg-gradient-to-r from-gray-950/30 to-transparent" />
        </div>

        {/* Hero Content */}
        <div className="relative z-10 max-w-5xl mx-auto px-6 text-center">
          <div className="mb-6">
            <span className="inline-block text-xs font-medium tracking-widest uppercase text-blue-400/80 bg-blue-400/10 border border-blue-400/20 px-4 py-1.5 rounded-full backdrop-blur-sm">
              Multi-Agent AI Analysis Platform
            </span>
          </div>

          <h1 className="text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-bold tracking-tight leading-[0.95] mb-8">
            Don&apos;t just watch
            <br />
            the market.
            <br />
            <span className="text-gradient">Analyze it.</span>
          </h1>

          <p className="text-lg md:text-xl text-gray-300/90 max-w-2xl mx-auto mb-10 leading-relaxed">
            Institutional-grade stock analysis powered by AI agents.
            DCF valuation, technical indicators, risk metrics, and sentiment —
            all in one comprehensive report.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/dashboard" className="btn-primary">
              Start Analyzing
            </Link>
            <Link href="/register" className="btn-secondary">
              Sign Up Free
            </Link>
          </div>

          {/* Scroll indicator */}
          <div className="mt-20 animate-bounce">
            <svg className="w-5 h-5 mx-auto text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
            </svg>
          </div>
        </div>
      </section>

      {/* ── How It Works ───────────────────────────────────── */}
      <section className="relative py-32 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-20">
            <p className="text-sm font-medium tracking-widest uppercase text-gray-500 mb-3">How it works</p>
            <h2 className="text-4xl md:text-5xl font-bold tracking-tight">
              From ticker to thesis.
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {/* Step 1 */}
            <div className="glass-card p-8 group hover:border-white/20 transition-all duration-500">
              <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-500">
                <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
                </svg>
              </div>
              <p className="text-xs font-medium tracking-widest uppercase text-gray-500 mb-2">Step 01</p>
              <h3 className="text-xl font-semibold mb-3">Data Gathering</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                Real-time financial statements, historical prices, company profiles,
                and news articles — all gathered automatically from institutional data sources.
              </p>
              <div className="mt-6 p-4 rounded-lg bg-gray-950/50 font-mono text-xs text-gray-500 border border-white/5">
                <span className="text-blue-400">agent</span>.gather(<span className="text-emerald-400">&quot;AAPL&quot;</span>)<br />
                <span className="text-gray-600">→ income_statement, balance_sheet,</span><br />
                <span className="text-gray-600">&nbsp;&nbsp;cash_flow, prices, profile</span>
              </div>
            </div>

            {/* Step 2 */}
            <div className="glass-card p-8 group hover:border-white/20 transition-all duration-500">
              <div className="w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-500">
                <svg className="w-6 h-6 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
                </svg>
              </div>
              <p className="text-xs font-medium tracking-widest uppercase text-gray-500 mb-2">Step 02</p>
              <h3 className="text-xl font-semibold mb-3">Multi-Agent Analysis</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                Five specialized AI agents run in parallel — financial metrics,
                technicals (RSI, MACD, Bollinger), DCF valuation, risk assessment,
                and sentiment analysis.
              </p>
              <div className="mt-6 p-4 rounded-lg bg-gray-950/50 font-mono text-xs text-gray-500 border border-white/5">
                <span className="text-cyan-400">pipeline</span>.run([<br />
                &nbsp;&nbsp;metrics, technicals,<br />
                &nbsp;&nbsp;valuation, risk, sentiment<br />
                ])
              </div>
            </div>

            {/* Step 3 */}
            <div className="glass-card p-8 group hover:border-white/20 transition-all duration-500">
              <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-500">
                <svg className="w-6 h-6 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
              </div>
              <p className="text-xs font-medium tracking-widest uppercase text-gray-500 mb-2">Step 03</p>
              <h3 className="text-xl font-semibold mb-3">Comprehensive Report</h3>
              <p className="text-gray-400 text-sm leading-relaxed">
                Everything synthesized into a professional report with 30+ metrics,
                risk ratings, confidence scores, and a clear investment thesis.
              </p>
              <div className="mt-6 p-4 rounded-lg bg-gray-950/50 font-mono text-xs text-gray-500 border border-white/5">
                <span className="text-emerald-400">report</span>.generate()<br />
                <span className="text-gray-600">→ Recommendation: </span><span className="text-white">BUY</span><br />
                <span className="text-gray-600">&nbsp;&nbsp;Confidence: </span><span className="text-white">78%</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Metrics Grid ───────────────────────────────────── */}
      <section className="py-24 px-6 border-t border-white/5">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
              Professional-grade analysis.
            </h2>
            <p className="text-gray-400 text-lg max-w-2xl mx-auto">
              Every report includes institutional-level depth across four key dimensions.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              number="30+"
              label="Financial Metrics"
              detail="P/E, ROE, ROIC, margins, growth rates, FCF yield, and more"
              color="blue"
            />
            <MetricCard
              number="12"
              label="Technical Indicators"
              detail="RSI, MACD, Bollinger Bands, moving averages, ATR, momentum"
              color="cyan"
            />
            <MetricCard
              number="8"
              label="Risk Metrics"
              detail="Sharpe, Sortino, VaR, max drawdown, volatility, beta"
              color="amber"
            />
            <MetricCard
              number="20+"
              label="News Articles"
              detail="Real-time sentiment analysis with NLP scoring"
              color="emerald"
            />
          </div>
        </div>
      </section>

      {/* ── CTA Section ────────────────────────────────────── */}
      <section className="relative py-32 px-6 overflow-hidden">
        {/* Subtle background image */}
        <div className="absolute inset-0 opacity-10">
          <Image
            src="/mountain.jpg"
            alt=""
            fill
            className="object-cover"
            quality={50}
          />
        </div>
        <div className="absolute inset-0 bg-gradient-to-b from-gray-950 via-transparent to-gray-950" />

        <div className="relative z-10 max-w-3xl mx-auto text-center">
          <h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-6">
            Ready to analyze?
          </h2>
          <p className="text-gray-400 text-lg mb-10 leading-relaxed">
            Enter any ticker. Get a comprehensive, AI-powered analysis report
            in under a minute. No credit card required.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/register" className="btn-primary">
              Create Free Account
            </Link>
            <Link href="/pricing" className="btn-secondary">
              View Plans
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────── */}
      <footer className="border-t border-white/5 py-12 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-white/10 flex items-center justify-center">
              <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
            <span className="text-sm font-medium text-gray-400">StockAnalyzer AI</span>
          </div>
          <div className="flex items-center gap-6 text-sm text-gray-500">
            <Link href="/pricing" className="hover:text-gray-300 transition">Pricing</Link>
            <Link href="/login" className="hover:text-gray-300 transition">Login</Link>
            <Link href="/register" className="hover:text-gray-300 transition">Sign Up</Link>
          </div>
          <p className="text-xs text-gray-600">
            &copy; {new Date().getFullYear()} StockAnalyzer AI
          </p>
        </div>
      </footer>
    </div>
  );
}

/* ── Metric Card Component ─────────────────────────────────── */

function MetricCard({
  number,
  label,
  detail,
  color,
}: {
  number: string;
  label: string;
  detail: string;
  color: 'blue' | 'cyan' | 'amber' | 'emerald';
}) {
  const colors = {
    blue: 'text-blue-400',
    cyan: 'text-cyan-400',
    amber: 'text-amber-400',
    emerald: 'text-emerald-400',
  };

  return (
    <div className="glass-card p-6 hover:border-white/20 transition-all duration-500">
      <p className={`text-4xl font-bold ${colors[color]} mb-1`}>{number}</p>
      <p className="font-semibold text-white mb-2">{label}</p>
      <p className="text-gray-500 text-sm leading-relaxed">{detail}</p>
    </div>
  );
}
