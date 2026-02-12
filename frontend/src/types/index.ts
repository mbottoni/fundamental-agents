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
  job_id: number;
  created_at: string;
}

// --- API Errors ---
export interface ApiError {
  detail: string;
}
