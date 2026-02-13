import Link from 'next/link';

/* ── Stock data for marquees ─────────────────────────────────── */
const POPULAR_STOCKS = [
  { ticker: 'AAPL', name: 'Apple Inc' },
  { ticker: 'NVDA', name: 'NVIDIA Corp' },
  { ticker: 'MSFT', name: 'Microsoft Corp' },
  { ticker: 'AMZN', name: 'Amazon.com Inc' },
  { ticker: 'GOOG', name: 'Alphabet Inc' },
  { ticker: 'META', name: 'Meta Platforms' },
  { ticker: 'TSLA', name: 'Tesla Inc' },
  { ticker: 'BRK.B', name: 'Berkshire Hathaway' },
  { ticker: 'AVGO', name: 'Broadcom Inc' },
  { ticker: 'LLY', name: 'Eli Lilly & Co' },
  { ticker: 'WMT', name: 'Walmart Inc' },
  { ticker: 'V', name: 'Visa Inc' },
  { ticker: 'XOM', name: 'Exxon Mobil' },
  { ticker: 'MA', name: 'Mastercard Inc' },
  { ticker: 'COST', name: 'Costco Wholesale' },
  { ticker: 'HD', name: 'Home Depot Inc' },
  { ticker: 'PG', name: 'Procter & Gamble' },
  { ticker: 'NFLX', name: 'Netflix Inc' },
];

const CATEGORIES = [
  'AI Stocks', 'Semiconductors', 'Cybersecurity', 'Biotechnology',
  'Electric Vehicles', 'FinTech', 'Renewables', 'Space Stocks',
  'E-commerce', 'Cloud Computing', 'Healthcare', 'Dividends',
];

export default function Home() {
  return (
    <div className="bg-white text-gray-900 min-h-screen">
      {/* ── Navigation ─────────────────────────────────────── */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-lg border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link href="/" className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
              </div>
              <span className="text-lg font-bold tracking-tight">StockAnalyzer</span>
            </Link>
            <div className="hidden md:flex items-center gap-8">
              <Link href="/screener" className="text-sm text-gray-500 hover:text-gray-900 transition font-medium">Screener</Link>
              <Link href="/compare" className="text-sm text-gray-500 hover:text-gray-900 transition font-medium">Compare</Link>
              <Link href="/market" className="text-sm text-gray-500 hover:text-gray-900 transition font-medium">Market</Link>
              <Link href="/lists" className="text-sm text-gray-500 hover:text-gray-900 transition font-medium">Lists</Link>
              <Link href="/pricing" className="text-sm text-gray-500 hover:text-gray-900 transition font-medium">Pricing</Link>
              <Link href="/login" className="text-sm text-gray-500 hover:text-gray-900 transition font-medium">Log In</Link>
              <Link href="/register" className="text-sm bg-brand-600 hover:bg-brand-700 text-white px-5 py-2 rounded-lg transition font-semibold">
                Sign Up
              </Link>
            </div>
            <div className="md:hidden flex items-center gap-3">
              <Link href="/login" className="text-sm text-gray-500 font-medium">Log In</Link>
              <Link href="/register" className="text-sm bg-brand-600 text-white px-4 py-1.5 rounded-lg font-semibold">
                Sign Up
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* ── Hero Section ───────────────────────────────────── */}
      <section className="pt-32 pb-8 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-5xl sm:text-6xl md:text-7xl font-bold tracking-tight leading-[1.05] mb-6">
            Next-level Stock Investing{' '}
            <span className="text-brand-600">powered by AI</span>
          </h1>
          <p className="text-lg md:text-xl text-gray-500 max-w-2xl mx-auto mb-10 leading-relaxed">
            Our mission is to help you make better investment decisions.
            Comprehensive AI-powered analysis with DCF valuation, technical indicators,
            risk metrics, and sentiment — all in one report.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/register" className="btn-primary">
              Start now for free
            </Link>
            <Link href="/pricing" className="btn-secondary">
              Pricing
            </Link>
          </div>
        </div>
      </section>

      {/* ── Stock Ticker Marquee ──────────────────────────── */}
      <section className="py-10">
        <div className="marquee-container">
          <div className="marquee-track animate-marquee">
            {[...POPULAR_STOCKS, ...POPULAR_STOCKS].map((stock, i) => (
              <div key={i} className="flex-shrink-0 flex items-center gap-3 bg-gray-50 border border-gray-100 rounded-xl px-5 py-3 hover:shadow-md transition-shadow cursor-pointer">
                <div className="w-10 h-10 rounded-lg bg-brand-50 border border-brand-100 flex items-center justify-center text-brand-700 font-bold text-sm">
                  {stock.ticker.charAt(0)}
                </div>
                <div>
                  <p className="font-bold text-sm text-gray-900">{stock.ticker}</p>
                  <p className="text-xs text-gray-400">{stock.name}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="marquee-container mt-4">
          <div className="marquee-track animate-marquee-reverse">
            {[...POPULAR_STOCKS.slice(9), ...POPULAR_STOCKS.slice(0, 9), ...POPULAR_STOCKS.slice(9), ...POPULAR_STOCKS.slice(0, 9)].map((stock, i) => (
              <div key={i} className="flex-shrink-0 flex items-center gap-3 bg-gray-50 border border-gray-100 rounded-xl px-5 py-3 hover:shadow-md transition-shadow cursor-pointer">
                <div className="w-10 h-10 rounded-lg bg-brand-50 border border-brand-100 flex items-center justify-center text-brand-700 font-bold text-sm">
                  {stock.ticker.charAt(0)}
                </div>
                <div>
                  <p className="font-bold text-sm text-gray-900">{stock.ticker}</p>
                  <p className="text-xs text-gray-400">{stock.name}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features Overview ─────────────────────────────── */}
      <section className="py-24 px-6 section-gray">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
              We help you make better investments.
            </h2>
            <p className="text-gray-500 text-lg max-w-2xl mx-auto">
              AI-powered stock analysis, risk assessment, and portfolio insights to
              help you find the best investment opportunities.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            <FeatureCard
              icon={<ChartIcon />}
              title="Graphical Representation"
              description="We use charts, heatmaps, and interactive visualizations to make complex financial data simple and actionable."
            />
            <FeatureCard
              icon={<AnalyticsIcon />}
              title="Fundamental Analysis"
              description="Over 30 fundamental ratios including P/E, ROIC, margins, growth rates, FCF yield, and more for every stock."
            />
            <FeatureCard
              icon={<TechnicalIcon />}
              title="Technical Indicators"
              description="RSI, MACD, Bollinger Bands, moving averages, ATR, momentum — all calculated and visualized for you."
            />
            <FeatureCard
              icon={<ValuationIcon />}
              title="Professional Valuations"
              description="DCF intrinsic value calculations with WACC, along with relative valuation multiples and peer comparisons."
            />
            <FeatureCard
              icon={<ShieldIcon />}
              title="Risk Assessment"
              description="Sharpe ratio, Sortino, VaR, max drawdown, beta, and volatility metrics with clear risk ratings."
            />
            <FeatureCard
              icon={<SentimentIcon />}
              title="News Sentiment"
              description="Real-time sentiment analysis of 20+ news articles using NLP to gauge market perception."
            />
          </div>
        </div>
      </section>

      {/* ── Step 1: Stock Analysis ────────────────────────── */}
      <section className="py-24 px-6 section-light">
        <div className="max-w-6xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div>
              <span className="step-badge">Stock Analysis</span>
              <h2 className="text-3xl md:text-4xl font-bold tracking-tight mt-6 mb-4">
                Analyze stocks to find the best investments
              </h2>
              <p className="text-gray-500 mb-8 leading-relaxed">
                Our AI-powered stock analysis provides institutional-grade research in
                under a minute. Enter any ticker and get a comprehensive report with
                valuation, financial health, growth metrics, and a clear investment thesis.
              </p>
              <div className="space-y-4 mb-8">
                <FeatureListItem title="Multi-layered Analysis" description="Comprehensive reports covering valuation, growth, profitability, risk, and sentiment." />
                <FeatureListItem title="Intelligent Valuations" description="DCF intrinsic value calculations alongside relative valuation multiples." />
                <FeatureListItem title="100+ Financial Metrics" description="Deep-dive into every aspect of a company's financial performance." />
              </div>
              <Link href="/register" className="btn-primary inline-block">
                Get Started now
              </Link>
            </div>
            <div className="relative">
              <div className="card-light-elevated p-6 lg:p-8">
                <AnalysisPreview />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Stock Ticker Marquee 2 ────────────────────────── */}
      <section className="py-6 section-gray">
        <div className="marquee-container">
          <div className="marquee-track animate-marquee-slow">
            {[...POPULAR_STOCKS, ...POPULAR_STOCKS].map((stock, i) => (
              <div key={i} className="flex-shrink-0 bg-white border border-gray-100 rounded-xl px-4 py-2.5 flex items-center gap-3 hover:shadow-sm transition-shadow">
                <span className="font-bold text-sm text-brand-700">{stock.ticker}</span>
                <span className="text-xs text-gray-400">{stock.name}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Step 2: AI-Powered Intelligence ───────────────── */}
      <section className="py-24 px-6 section-light">
        <div className="max-w-6xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div className="order-2 lg:order-1">
              <div className="card-light-elevated p-6 lg:p-8">
                <AIPreview />
              </div>
            </div>
            <div className="order-1 lg:order-2">
              <span className="step-badge">AI-Powered</span>
              <h2 className="text-3xl md:text-4xl font-bold tracking-tight mt-6 mb-4">
                Five specialized AI agents working for you
              </h2>
              <p className="text-gray-500 mb-8 leading-relaxed">
                Our multi-agent pipeline runs five specialized AI agents in parallel —
                each expert in their domain — to deliver a complete investment thesis.
              </p>
              <div className="space-y-4 mb-8">
                <FeatureListItem title="Data Gathering Agent" description="Pulls real-time financials, historical prices, and company profiles from institutional sources." />
                <FeatureListItem title="Financial Metrics Agent" description="Calculates 30+ ratios across valuation, profitability, liquidity, leverage, and growth." />
                <FeatureListItem title="Technical Analysis Agent" description="RSI, MACD, Bollinger Bands, moving averages, support/resistance, and momentum signals." />
                <FeatureListItem title="Risk & Sentiment Agents" description="VaR, Sharpe ratio, beta calculations combined with NLP news sentiment analysis." />
              </div>
              <Link href="/register" className="btn-primary inline-block">
                Start Analyzing
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── Step 3: Reports & Portfolio ───────────────────── */}
      <section className="py-24 px-6 section-gray">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <span className="step-badge">Reports & Insights</span>
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight mt-6 mb-4">
              Professional reports with interactive charts
            </h2>
            <p className="text-gray-500 text-lg max-w-2xl mx-auto">
              Every analysis produces a comprehensive report with data visualizations,
              price charts, risk dashboards, and a clear investment recommendation.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <ReportFeatureCard
              title="Price & Technical Charts"
              description="Interactive price history with moving averages, Bollinger Bands, RSI gauge, and volume analysis."
              metric="12 indicators"
            />
            <ReportFeatureCard
              title="Financial Dashboard"
              description="Profitability bars, valuation multiples, growth metrics, and DCF vs. current price comparison."
              metric="30+ metrics"
            />
            <ReportFeatureCard
              title="Risk & Sentiment"
              description="Risk rating, Sharpe/Sortino ratios, VaR, max drawdown, and news sentiment donut chart."
              metric="8 risk metrics"
            />
          </div>
        </div>
      </section>

      {/* ── Categories Marquee ────────────────────────────── */}
      <section className="py-6 section-light">
        <div className="marquee-container">
          <div className="marquee-track animate-marquee">
            {[...CATEGORIES, ...CATEGORIES, ...CATEGORIES].map((cat, i) => (
              <span key={i} className="flex-shrink-0 bg-gray-50 border border-gray-200 text-gray-600 text-sm font-medium px-5 py-2.5 rounded-full hover:bg-brand-50 hover:text-brand-700 hover:border-brand-200 transition-colors cursor-pointer">
                {cat}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── Tools & Features ─────────────────────────────── */}
      <section className="py-24 px-6 section-light">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-center mb-4">
            Professional Tools
          </h2>
          <p className="text-gray-500 text-lg text-center max-w-2xl mx-auto mb-16">
            Everything you need for serious stock research, all in one platform.
          </p>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Stock Screener */}
            <Link href="/screener" className="card-light p-7 group hover:border-brand-100 block">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-blue-50 border border-blue-100 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                  </svg>
                </div>
                <h3 className="text-lg font-bold">Stock Screener</h3>
              </div>
              <p className="text-gray-500 text-sm leading-relaxed mb-3">
                Filter stocks by sector, market cap, price, exchange, and more. Find your next investment in seconds.
              </p>
              <span className="text-brand-600 text-sm font-semibold group-hover:underline">Try Screener &rarr;</span>
            </Link>

            {/* Compare */}
            <Link href="/compare" className="card-light p-7 group hover:border-brand-100 block">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-purple-50 border border-purple-100 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                  </svg>
                </div>
                <h3 className="text-lg font-bold">Stock Comparison</h3>
              </div>
              <p className="text-gray-500 text-sm leading-relaxed mb-3">
                Compare two stocks side-by-side across 20+ metrics including valuation, profitability, and growth.
              </p>
              <span className="text-brand-600 text-sm font-semibold group-hover:underline">Compare Stocks &rarr;</span>
            </Link>

            {/* Interactive Charts */}
            <Link href="/chart/AAPL" className="card-light p-7 group hover:border-brand-100 block">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-emerald-50 border border-emerald-100 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
                <h3 className="text-lg font-bold">Interactive Charts</h3>
              </div>
              <p className="text-gray-500 text-sm leading-relaxed mb-3">
                Full technical charts with SMA, EMA, RSI, MACD, Bollinger Bands. Multiple timeframes from 1M to 5Y.
              </p>
              <span className="text-brand-600 text-sm font-semibold group-hover:underline">View Charts &rarr;</span>
            </Link>

            {/* Market Overview */}
            <Link href="/market" className="card-light p-7 group hover:border-brand-100 block">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-amber-50 border border-amber-100 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <h3 className="text-lg font-bold">Market Overview</h3>
              </div>
              <p className="text-gray-500 text-sm leading-relaxed mb-3">
                Top gainers, losers, most active stocks, and sector performance. Stay on top of market trends.
              </p>
              <span className="text-brand-600 text-sm font-semibold group-hover:underline">View Market &rarr;</span>
            </Link>

            {/* Stock Lists */}
            <Link href="/lists" className="card-light p-7 group hover:border-brand-100 block">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-pink-50 border border-pink-100 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <svg className="w-5 h-5 text-pink-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                </div>
                <h3 className="text-lg font-bold">Stock Lists & Themes</h3>
              </div>
              <p className="text-gray-500 text-sm leading-relaxed mb-3">
                Curated collections: Magnificent 7, AI Leaders, Dividend Aristocrats, Semiconductors, and more.
              </p>
              <span className="text-brand-600 text-sm font-semibold group-hover:underline">Browse Lists &rarr;</span>
            </Link>

            {/* Watchlist */}
            <Link href="/dashboard" className="card-light p-7 group hover:border-brand-100 block">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <svg className="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                  </svg>
                </div>
                <h3 className="text-lg font-bold">Watchlist & History</h3>
              </div>
              <p className="text-gray-500 text-sm leading-relaxed mb-3">
                Save stocks, add notes, track analysis history, and access all your previous reports.
              </p>
              <span className="text-brand-600 text-sm font-semibold group-hover:underline">Go to Dashboard &rarr;</span>
            </Link>
          </div>
        </div>
      </section>

      {/* ── CTA Section ───────────────────────────────────── */}
      <section className="py-24 px-6 bg-gray-900 text-white">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-6">
            Ready to start investing smarter?
          </h2>
          <p className="text-gray-400 text-lg mb-10 leading-relaxed">
            Enter any ticker. Get a comprehensive, AI-powered analysis report
            in under a minute. No credit card required.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/register" className="bg-white text-gray-900 font-semibold px-8 py-3.5 rounded-xl hover:bg-gray-100 transition-all shadow-lg shadow-white/10">
              Create Free Account
            </Link>
            <Link href="/pricing" className="btn-outline-white">
              View Plans
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────── */}
      <footer className="border-t border-gray-100 py-12 px-6 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row justify-between items-start gap-8 mb-8">
            <div>
              <Link href="/" className="flex items-center gap-2.5 mb-3">
                <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
                <span className="text-lg font-bold tracking-tight">StockAnalyzer</span>
              </Link>
              <p className="text-sm text-gray-400 max-w-xs">
                AI-powered fundamental stock analysis for smarter investment decisions.
              </p>
            </div>
            <div className="flex gap-12">
              <div>
                <h4 className="font-semibold text-sm mb-3">Tools</h4>
                <div className="flex flex-col gap-2">
                  <Link href="/screener" className="text-sm text-gray-400 hover:text-gray-700 transition">Stock Screener</Link>
                  <Link href="/compare" className="text-sm text-gray-400 hover:text-gray-700 transition">Stock Comparison</Link>
                  <Link href="/chart/AAPL" className="text-sm text-gray-400 hover:text-gray-700 transition">Charts</Link>
                  <Link href="/market" className="text-sm text-gray-400 hover:text-gray-700 transition">Market Overview</Link>
                  <Link href="/lists" className="text-sm text-gray-400 hover:text-gray-700 transition">Stock Lists</Link>
                </div>
              </div>
              <div>
                <h4 className="font-semibold text-sm mb-3">Product</h4>
                <div className="flex flex-col gap-2">
                  <Link href="/register" className="text-sm text-gray-400 hover:text-gray-700 transition">Stock Analysis</Link>
                  <Link href="/pricing" className="text-sm text-gray-400 hover:text-gray-700 transition">Pricing</Link>
                </div>
              </div>
              <div>
                <h4 className="font-semibold text-sm mb-3">Account</h4>
                <div className="flex flex-col gap-2">
                  <Link href="/login" className="text-sm text-gray-400 hover:text-gray-700 transition">Log In</Link>
                  <Link href="/register" className="text-sm text-gray-400 hover:text-gray-700 transition">Sign Up</Link>
                  <Link href="/dashboard" className="text-sm text-gray-400 hover:text-gray-700 transition">Dashboard</Link>
                </div>
              </div>
            </div>
          </div>
          <div className="border-t border-gray-100 pt-6 flex flex-col sm:flex-row justify-between items-center gap-4">
            <p className="text-xs text-gray-400">
              &copy; {new Date().getFullYear()} StockAnalyzer AI. All rights reserved.
            </p>
            <p className="text-xs text-gray-400">
              Financial data provided for educational purposes only. Not investment advice.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════
   Sub-Components
   ══════════════════════════════════════════════════════════════ */

function FeatureCard({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="card-light p-7 group hover:border-brand-100">
      <div className="w-12 h-12 rounded-xl bg-brand-50 border border-brand-100 flex items-center justify-center mb-5 group-hover:scale-105 transition-transform">
        {icon}
      </div>
      <h3 className="text-lg font-bold mb-2">{title}</h3>
      <p className="text-gray-500 text-sm leading-relaxed">{description}</p>
    </div>
  );
}

function FeatureListItem({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex gap-3">
      <div className="flex-shrink-0 w-6 h-6 rounded-full bg-brand-50 border border-brand-100 flex items-center justify-center mt-0.5">
        <svg className="w-3.5 h-3.5 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
      </div>
      <div>
        <h4 className="font-semibold text-sm">{title}</h4>
        <p className="text-gray-500 text-sm">{description}</p>
      </div>
    </div>
  );
}

function SmallFeature({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <svg className="w-4 h-4 text-brand-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
      <span className="text-sm text-gray-600">{text}</span>
    </div>
  );
}

function ReportFeatureCard({ title, description, metric }: { title: string; description: string; metric: string }) {
  return (
    <div className="card-light p-7">
      <div className="inline-block bg-brand-50 text-brand-700 text-xs font-bold px-3 py-1 rounded-full mb-4">
        {metric}
      </div>
      <h3 className="text-lg font-bold mb-2">{title}</h3>
      <p className="text-gray-500 text-sm leading-relaxed">{description}</p>
    </div>
  );
}

/* ── Analysis Preview Mock ────────────────────────────────── */
function AnalysisPreview() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-brand-100 flex items-center justify-center text-brand-700 font-bold">A</div>
          <div>
            <p className="font-bold">Apple Inc</p>
            <p className="text-xs text-gray-400">AAPL · NASDAQ</p>
          </div>
        </div>
        <div className="text-right">
          <p className="font-bold text-lg">$189.84</p>
          <p className="text-xs text-emerald-600 font-semibold">+1.24%</p>
        </div>
      </div>
      <div className="border-t border-gray-100 pt-4 grid grid-cols-3 gap-4">
        <div><p className="text-[10px] uppercase text-gray-400 font-medium">P/E Ratio</p><p className="font-bold text-sm">29.8</p></div>
        <div><p className="text-[10px] uppercase text-gray-400 font-medium">ROE</p><p className="font-bold text-sm">147.3%</p></div>
        <div><p className="text-[10px] uppercase text-gray-400 font-medium">DCF Value</p><p className="font-bold text-sm text-emerald-600">$201.20</p></div>
      </div>
      <div className="border-t border-gray-100 pt-4 grid grid-cols-3 gap-4">
        <div><p className="text-[10px] uppercase text-gray-400 font-medium">Revenue Growth</p><p className="font-bold text-sm">+8.2%</p></div>
        <div><p className="text-[10px] uppercase text-gray-400 font-medium">Net Margin</p><p className="font-bold text-sm">25.3%</p></div>
        <div><p className="text-[10px] uppercase text-gray-400 font-medium">RSI</p><p className="font-bold text-sm text-amber-600">58.4</p></div>
      </div>
      <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-emerald-500 rounded-full" />
          <span className="text-sm font-semibold text-emerald-800">Recommendation: BUY</span>
        </div>
        <span className="text-xs font-medium text-emerald-600">Confidence: 78%</span>
      </div>
    </div>
  );
}

/* ── AI Preview Mock ──────────────────────────────────────── */
function AIPreview() {
  return (
    <div className="space-y-3">
      <p className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">Multi-Agent Pipeline</p>
      {[
        { name: 'Data Gathering', status: 'complete', color: 'emerald' },
        { name: 'Financial Metrics', status: 'complete', color: 'emerald' },
        { name: 'Technical Analysis', status: 'complete', color: 'emerald' },
        { name: 'Risk Assessment', status: 'complete', color: 'emerald' },
        { name: 'News Sentiment', status: 'complete', color: 'emerald' },
        { name: 'Synthesis Report', status: 'generating', color: 'blue' },
      ].map((agent) => (
        <div key={agent.name} className="flex items-center justify-between bg-gray-50 border border-gray-100 rounded-xl px-4 py-3">
          <div className="flex items-center gap-3">
            <div className={`w-2 h-2 rounded-full ${agent.color === 'emerald' ? 'bg-emerald-500' : 'bg-blue-500 animate-pulse'}`} />
            <span className="text-sm font-medium">{agent.name}</span>
          </div>
          <span className={`text-xs font-semibold ${agent.color === 'emerald' ? 'text-emerald-600' : 'text-blue-600'}`}>
            {agent.status === 'complete' ? 'Complete' : 'Generating...'}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ── Icon Components ──────────────────────────────────────── */

function ChartIcon() {
  return (
    <svg className="w-6 h-6 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
    </svg>
  );
}

function AnalyticsIcon() {
  return (
    <svg className="w-6 h-6 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375" />
    </svg>
  );
}

function TechnicalIcon() {
  return (
    <svg className="w-6 h-6 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
    </svg>
  );
}

function ValuationIcon() {
  return (
    <svg className="w-6 h-6 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg className="w-6 h-6 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
    </svg>
  );
}

function SentimentIcon() {
  return (
    <svg className="w-6 h-6 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 7.5h1.5m-1.5 3h1.5m-7.5 3h7.5m-7.5 3h7.5m3-9h3.375c.621 0 1.125.504 1.125 1.125V18a2.25 2.25 0 01-2.25 2.25M16.5 7.5V18a2.25 2.25 0 002.25 2.25M16.5 7.5V4.875c0-.621-.504-1.125-1.125-1.125H4.125C3.504 3.75 3 4.254 3 4.875V18a2.25 2.25 0 002.25 2.25h13.5M6 7.5h3v3H6v-3z" />
    </svg>
  );
}
