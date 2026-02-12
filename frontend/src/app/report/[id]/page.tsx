'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import api from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import type { Report } from '@/types';

export default function ReportPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeSection, setActiveSection] = useState('');
  const params = useParams();
  const reportId = params.id as string;

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (!reportId || !isAuthenticated) return;

    const fetchReport = async () => {
      try {
        const response = await api.get<Report>(`/reports/${reportId}`);
        setReport(response.data);
      } catch {
        setError('Failed to fetch report. It may not exist or you may not have access.');
      } finally {
        setLoading(false);
      }
    };

    fetchReport();
  }, [reportId, isAuthenticated]);

  // Extract sections from markdown for the sidebar nav
  const sections = React.useMemo(() => {
    if (!report?.content) return [];
    const headingRegex = /^## (.+)$/gm;
    const found: { id: string; title: string }[] = [];
    let match;
    while ((match = headingRegex.exec(report.content)) !== null) {
      const title = match[1].trim();
      const id = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
      found.push({ id, title });
    }
    return found;
  }, [report?.content]);

  // Scroll spy
  useEffect(() => {
    if (sections.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      { rootMargin: '-20% 0px -70% 0px' }
    );

    sections.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [sections, report]);

  const handlePrint = useCallback(() => {
    window.print();
  }, []);

  if (authLoading || loading) {
    return (
      <div className="bg-gray-950 text-white min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full" />
          <span className="text-gray-400">Loading report...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-950 text-white min-h-screen">
      {/* ── Top Bar ────────────────────────────────────────── */}
      <nav className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-sm sticky top-0 z-50 print:hidden">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-14">
            <div className="flex items-center gap-4">
              <Link
                href="/dashboard"
                className="text-gray-400 hover:text-white transition flex items-center gap-1.5 text-sm"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                Dashboard
              </Link>
              <span className="text-gray-700">|</span>
              <span className="text-gray-300 font-medium text-sm">Report #{reportId}</span>
            </div>
            <div className="flex items-center gap-3">
              {report && (
                <>
                  <span className="text-gray-500 text-xs">
                    Generated {new Date(report.created_at).toLocaleString()}
                  </span>
                  <button
                    onClick={handlePrint}
                    className="text-gray-400 hover:text-white transition text-sm flex items-center gap-1.5"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0110.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18m0 0l.229 2.523a1.125 1.125 0 01-1.12 1.227H7.231c-.662 0-1.18-.568-1.12-1.227L6.34 18m11.318 0h1.091A2.25 2.25 0 0021 15.75V9.456c0-1.081-.768-2.015-1.837-2.175a48.055 48.055 0 00-1.913-.247M6.34 18H5.25A2.25 2.25 0 013 15.75V9.456c0-1.081.768-2.015 1.837-2.175a48.041 48.041 0 011.913-.247m10.5 0a48.536 48.536 0 00-10.5 0m10.5 0V3.375c0-.621-.504-1.125-1.125-1.125h-8.25c-.621 0-1.125.504-1.125 1.125v3.659M18.75 9.456l-.22-3.003" />
                    </svg>
                    Print
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* ── Error ──────────────────────────────────────────── */}
      {error && (
        <div className="max-w-4xl mx-auto px-4 pt-8">
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 p-4 rounded-xl">
            {error}
          </div>
        </div>
      )}

      {/* ── Layout: sidebar + content ──────────────────────── */}
      {report && (
        <div className="max-w-screen-2xl mx-auto flex">
          {/* Sidebar - Table of Contents */}
          <aside className="hidden lg:block w-64 flex-shrink-0 print:hidden">
            <div className="sticky top-20 px-6 py-8">
              <p className="text-xs uppercase tracking-wider text-gray-500 font-semibold mb-4">Table of Contents</p>
              <nav className="space-y-0.5">
                {sections.map(({ id, title }) => (
                  <a
                    key={id}
                    href={`#${id}`}
                    className={`block text-sm py-1.5 px-3 rounded-md transition ${
                      activeSection === id
                        ? 'bg-blue-500/10 text-blue-400 font-medium'
                        : 'text-gray-500 hover:text-gray-300'
                    }`}
                  >
                    {title}
                  </a>
                ))}
              </nav>
            </div>
          </aside>

          {/* Main content */}
          <main className="flex-1 min-w-0 px-4 sm:px-6 lg:px-8 py-8">
            <article className="bg-gray-900 border border-gray-800 rounded-xl p-6 md:p-10 prose prose-invert prose-sm md:prose-base max-w-none
              prose-headings:scroll-mt-20
              prose-h1:text-2xl prose-h1:md:text-3xl prose-h1:font-bold prose-h1:bg-gradient-to-r prose-h1:from-blue-400 prose-h1:to-cyan-400 prose-h1:bg-clip-text prose-h1:text-transparent prose-h1:pb-2
              prose-h2:text-xl prose-h2:md:text-2xl prose-h2:font-semibold prose-h2:text-white prose-h2:border-b prose-h2:border-gray-800 prose-h2:pb-3 prose-h2:mt-10
              prose-h3:text-lg prose-h3:font-medium prose-h3:text-gray-200 prose-h3:mt-6
              prose-strong:text-white
              prose-li:text-gray-300 prose-li:marker:text-gray-600
              prose-p:text-gray-300
              prose-hr:border-gray-800
            ">
              <ReactMarkdown
                components={{
                  h2: ({ children, ...props }) => {
                    const text = typeof children === 'string' ? children : String(children);
                    const id = text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
                    return <h2 id={id} {...props}>{children}</h2>;
                  },
                }}
              >
                {report.content}
              </ReactMarkdown>
            </article>

            {/* Footer actions */}
            <div className="flex justify-between items-center mt-6 print:hidden">
              <Link
                href="/dashboard"
                className="text-gray-400 hover:text-white transition text-sm"
              >
                &larr; Back to Dashboard
              </Link>
              <button
                onClick={handlePrint}
                className="bg-gray-800 hover:bg-gray-700 text-white text-sm px-4 py-2 rounded-lg transition"
              >
                Print / Export PDF
              </button>
            </div>
          </main>
        </div>
      )}
    </div>
  );
}
