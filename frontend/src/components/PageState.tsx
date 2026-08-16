'use client';

import React from 'react';

/**
 * Shared loading, error and empty states.
 *
 * Several pages swallowed failures into an empty list, so a provider outage
 * rendered a blank page that read as "there is nothing here".
 */

export function Spinner({ className = '' }: { className?: string }) {
  return (
    <div
      role="status"
      aria-label="Loading"
      className={`animate-spin h-8 w-8 border-[3px] border-blue-500 border-t-transparent rounded-full ${className}`}
    />
  );
}

export function LoadingBlock({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 gap-3">
      <Spinner />
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  );
}

export function ErrorBlock({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
      <p className="text-red-300 mb-3">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-sm bg-red-500/20 hover:bg-red-500/30 text-red-200 border border-red-500/40 rounded-lg px-4 py-2 transition"
        >
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyBlock({ message }: { message: string }) {
  return <p className="text-gray-500 text-center py-8">{message}</p>;
}

/**
 * Picks the right state for a panel: an error beats a spinner, and an empty
 * result is only "empty" once the request has actually succeeded.
 */
export function PanelState({
  loading,
  error,
  isEmpty,
  emptyMessage,
  onRetry,
  children,
}: {
  loading: boolean;
  error?: string;
  isEmpty?: boolean;
  emptyMessage?: string;
  onRetry?: () => void;
  children: React.ReactNode;
}) {
  if (error) return <ErrorBlock message={error} onRetry={onRetry} />;
  if (loading) return <LoadingBlock />;
  if (isEmpty) return <EmptyBlock message={emptyMessage || 'Nothing to show.'} />;
  return <>{children}</>;
}
