// --- User ---
export interface User {
  id: number;
  email: string;
  subscription_status: string;
  is_verified: boolean;
}

// --- Auth ---
export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AuthContextType {
  token: string | null;
  user: User | null;
  login: (token: string, refreshToken?: string) => void;
  logout: () => void;
  isAuthenticated: boolean;
  isLoading: boolean;
}

// --- Analysis Jobs ---
export type JobStatus =
  | 'pending'
  | 'gathering_data'
  | 'analyzing'
  | 'generating_report'
  | 'complete'
  | 'failed';

export interface AnalysisJob {
  id: number;
  user_id: number;
  ticker: string;
  status: JobStatus;
  report_id: number | null;
  created_at: string;
}

// --- Reports ---
export interface Report {
  id: number;
  content: string;
  chart_data: ChartData | null;
  job_id: number;
  created_at: string;
}

// --- Watchlist ---
export interface WatchlistItem {
  id: number;
  user_id: number;
  ticker: string;
  notes: string | null;
  created_at: string;
}

// --- Dashboard ---
export interface DashboardStats {
  total_analyses: number;
  completed_analyses: number;
  failed_analyses: number;
  pending_analyses: number;
  tickers_analyzed: string[];
  watchlist_count: number;
  subscription_status: string;
  is_premium: boolean;
}

export interface StockQuote {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changesPercentage: number;
  volume: number;
  marketCap: number;
  dayHigh: number;
  dayLow: number;
  previousClose: number;
}

export interface SearchResult {
  symbol: string;
  name: string;
  currency: string;
  stockExchange: string;
}

// --- Chart Data (structured data for visualizations) ---

export interface PricePoint {
  date: string;
  close: number;
  volume: number;
  sma_20?: number | null;
  sma_50?: number | null;
  sma_200?: number | null;
  bb_upper?: number | null;
  bb_lower?: number | null;
}

export interface BarDataPoint {
  name: string;
  value: number;
}

export interface SentimentSlice {
  name: string;
  value: number;
  color?: string;
}

export interface ChartData {
  ticker: string;
  company_name: string;
  current_price: number | null;
  price_series: PricePoint[];
  moving_averages: {
    sma_20: number | null;
    sma_50: number | null;
    sma_200: number | null;
  };
  bollinger_bands: {
    upper: number | null;
    lower: number | null;
    middle: number | null;
  };
  rsi: number | null;
  macd: {
    macd_line: number | null;
    signal_line: number | null;
    histogram: number | null;
  };
  atr: number | null;
  volume_profile: {
    avg_volume: number | null;
    relative_volume: number | null;
  };
  momentum: {
    price_momentum_1m: number | null;
    price_momentum_3m: number | null;
    price_momentum_6m: number | null;
  };
  trend_signals: string[];
  support_resistance: {
    support: number | null;
    resistance: number | null;
  };
  profitability: BarDataPoint[];
  valuation_multiples: BarDataPoint[];
  sentiment: SentimentSlice[];
  sentiment_score: number;
  growth: BarDataPoint[];
  risk: {
    rating: string;
    annual_volatility: number | null;
    sharpe_ratio: number | null;
    sortino_ratio: number | null;
    max_drawdown_pct: number | null;
    beta: number | null;
    var_95: number | null;
  };
  dcf: {
    intrinsic_value: number | null;
    wacc: number | null;
    current_price: number | null;
  };
  liquidity: Record<string, number | null>;
  leverage: Record<string, number | null>;
  revenue_segments?: {
    product: { name: string; value: number }[];
    geographic: { name: string; value: number }[];
  };
  dividend_history?: { date: string; dividend: number }[];
}

// --- API Errors ---
export interface ApiError {
  detail: string;
}
