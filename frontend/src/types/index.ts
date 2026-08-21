// Types shared across the app.
//
// Anything the backend defines is DERIVED from `./api.ts`, which is generated
// from the FastAPI OpenAPI document (`npm run gen:types`). These used to be
// retyped by hand and drifted silently — `ChartData.macd` declared a
// `histogram` field the backend has always called `macd_histogram`, and
// nothing failed, because a mismatched field simply reads as undefined.
//
// Only view models with no server counterpart are still written out below.

import type { components } from './api';

type Schemas = components['schemas'];

// --- User ---
export type User = Schemas['User'];

// --- Auth (client-side shapes; the token response is not modelled server-side) ---
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
// The backend types `status` as a plain string; the union is a frontend
// refinement, so it is layered over the generated shape rather than replacing
// it. Everything else on the job comes from the server.
export type JobStatus =
  | 'pending'
  | 'gathering_data'
  | 'analyzing'
  | 'generating_report'
  | 'complete'
  | 'failed';

export type AnalysisJob = Omit<Schemas['AnalysisJob'], 'status'> & {
  status: JobStatus;
};

// --- Reports ---
export type Report = Schemas['Report'];

// --- Watchlist ---
export type WatchlistItem = Schemas['WatchlistItem'];

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
//
// All generated. `ChartData` is the contract with `_build_chart_data()` in the
// orchestrator; the nested aliases exist because components take the pieces as
// props.
export type ChartData = Schemas['ChartData'];
export type PricePoint = Schemas['PricePoint'];
export type BarDataPoint = Schemas['BarDataPoint'];
export type SentimentSlice = Schemas['SentimentSlice'];
export type PeerComparison = Schemas['PeerMetricComparison'];
export type RecommendationFactor = Schemas['RecommendationFactor'];

// --- API Errors ---
export interface ApiError {
  detail: string;
}
