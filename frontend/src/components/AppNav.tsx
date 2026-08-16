'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import api from '@/lib/api';

/**
 * The application's navigation bar.
 *
 * Eight pages each carried their own copy of this markup, so links added to
 * one never appeared in the others.
 */

const NAV_LINKS = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/market', label: 'Market' },
  { href: '/screener', label: 'Screener' },
  { href: '/compare', label: 'Compare' },
  { href: '/lists', label: 'Lists' },
];

// How often the badge refreshes. The sweep itself runs server-side; this is
// just how quickly the count catches up.
const UNREAD_POLL_MS = 120_000;

export function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2.5}
            d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
          />
        </svg>
      </div>
      <span className="text-lg font-bold">StockAnalyzer</span>
    </Link>
  );
}

export default function AppNav() {
  const pathname = usePathname();
  const { isAuthenticated, user, logout } = useAuth();
  const [unread, setUnread] = useState(0);

  const fetchUnread = useCallback(async () => {
    try {
      const { data } = await api.get<{ unread_count: number }>('/alerts/?unread_only=true');
      setUnread(data.unread_count);
    } catch {
      // The badge is decoration; a failure here should not disrupt navigation.
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;
    fetchUnread();
    const timer = setInterval(fetchUnread, UNREAD_POLL_MS);
    return () => clearInterval(timer);
  }, [isAuthenticated, fetchUnread]);

  return (
    <nav className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-lg sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 flex justify-between items-center h-16">
        <div className="flex items-center gap-8">
          <Logo />
          <div className="hidden md:flex items-center gap-6">
            {NAV_LINKS.map((link) => {
              const active = pathname === link.href || pathname?.startsWith(`${link.href}/`);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={active ? 'page' : undefined}
                  className={`text-sm transition ${
                    active ? 'text-white font-medium' : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-4">
          {isAuthenticated ? (
            <>
              <Link
                href="/alerts"
                className="relative text-sm text-gray-400 hover:text-white transition"
              >
                Alerts
                {unread > 0 && (
                  <span className="absolute -top-2 -right-3 bg-blue-600 text-white text-[10px] font-bold rounded-full min-w-[1.1rem] h-[1.1rem] px-1 flex items-center justify-center">
                    {unread > 9 ? '9+' : unread}
                  </span>
                )}
              </Link>
              {user?.subscription_status !== 'active' && (
                <Link
                  href="/pricing"
                  className="hidden sm:inline text-sm text-yellow-300 hover:text-yellow-200 transition"
                >
                  Upgrade
                </Link>
              )}
              <span className="hidden lg:inline text-sm text-gray-500 truncate max-w-[16rem]">
                {user?.email}
              </span>
              <button
                onClick={logout}
                className="bg-gray-800 hover:bg-gray-700 text-white font-medium py-1.5 px-3 rounded-lg transition text-sm border border-gray-700"
              >
                Log Out
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-sm text-gray-400 hover:text-white transition">
                Log In
              </Link>
              <Link
                href="/register"
                className="bg-blue-600 hover:bg-blue-500 text-white font-medium py-1.5 px-3 rounded-lg transition text-sm"
              >
                Sign Up
              </Link>
            </>
          )}
        </div>
      </div>

      {/* The link row collapses on narrow screens, so repeat it below. */}
      <div className="md:hidden border-t border-gray-800/70 px-6 py-2 flex gap-5 overflow-x-auto">
        {NAV_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="text-sm text-gray-400 hover:text-white whitespace-nowrap transition"
          >
            {link.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
