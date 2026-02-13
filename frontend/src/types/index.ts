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

// --- API Errors ---
export interface ApiError {
  detail: string;
}
