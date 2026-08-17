import type { AxiosError } from 'axios';

interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/**
 * Extract a human-readable error message from an Axios error.
 *
 * Handles both:
 * - FastAPI HTTPException: { detail: "some string" }
 * - Pydantic validation: { detail: [{ msg: "...", loc: [...] }, ...] }
 */
export function getErrorMessage(err: unknown, fallback = 'An unexpected error occurred.'): string {
  const axiosError = err as AxiosError<{ detail: string | ValidationError[] }>;
  const detail = axiosError?.response?.data?.detail;

  if (!detail) return fallback;

  // HTTPException returns a plain string
  if (typeof detail === 'string') return detail;

  // Pydantic validation returns an array of error objects
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((e) => e.msg).join(' ');
  }

  return fallback;
}
