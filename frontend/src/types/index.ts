// --- User ---
export interface User {
  id: number;
  email: string;
  subscription_status: string;
}

// --- Auth ---
export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface AuthContextType {
  token: string | null;
  user: User | null;
  login: (token: string) => void;
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

// --- Chart Data (structured data for visualizations) ---
export interface PricePoint {
  date: string;
  close: number;
  high?: number;
  low?: number;
  volume?: number;
}

export interface BarDataPoint {
  name: string;
  value: number | null;
}

export interface SentimentSlice {
  name: string;
  value: number;
  color: string;
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
    bb_upper: number | null;
    bb_middle: number | null;
    bb_lower: number | null;
    bb_bandwidth: number | null;
  };
  rsi: number | null;
  macd: {
    macd_line: number | null;
    signal_line: number | null;
    macd_histogram: number | null;
  };
  atr: number | null;
  volume_profile: {
    avg_volume_20: number | null;
    avg_volume_50: number | null;
    volume_trend: string;
  };
  momentum: {
    roc_5d: number | null;
    roc_20d: number | null;
    roc_60d: number | null;
  };
  trend_signals: string[];
  support_resistance: {
    resistance_52w: number | null;
    support_52w: number | null;
    resistance_20d: number | null;
    support_20d: number | null;
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
}

// --- API Errors ---
export interface ApiError {
  detail: string;
}
