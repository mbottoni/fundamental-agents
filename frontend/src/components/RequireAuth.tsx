'use client';

import React, { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';

/**
 * Gate a page behind a login.
 *
 * The guard was copy-pasted into three pages and missing from five others,
 * which were reachable logged-out and then broke on the first API call once
 * the backend started requiring a token.
 */
export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      // Preserve where the user was going so login can return them to it.
      const next = pathname ? `?next=${encodeURIComponent(pathname)}` : '';
      router.replace(`/login${next}`);
    }
  }, [isAuthenticated, isLoading, pathname, router]);

  if (isLoading) {
    return (
      <div className="bg-gray-950 text-white min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-gray-400">Loading…</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    // The redirect is already in flight; rendering nothing avoids a flash of
    // page content the viewer is not entitled to.
    return null;
  }

  return <>{children}</>;
}
