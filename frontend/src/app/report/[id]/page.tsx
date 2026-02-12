'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import api from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import type { Report } from '@/types';

export default function ReportPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const params = useParams();
  const reportId = params.id as string;

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

  if (authLoading || loading) {
    return (
      <div className="bg-gray-900 text-white min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-gray-400">Loading report...</div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 text-white min-h-screen p-4 md:p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold">Analysis Report</h1>
          <Link
            href="/dashboard"
            className="text-gray-400 hover:text-white text-sm transition"
          >
            &larr; Back to Dashboard
          </Link>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/50 text-red-400 p-4 rounded-lg">
            {error}
          </div>
        )}

        {report && (
          <article className="bg-gray-800 p-6 md:p-8 rounded-lg prose prose-invert prose-sm md:prose-base max-w-none">
            <ReactMarkdown>{report.content}</ReactMarkdown>
          </article>
        )}
      </div>
    </div>
  );
}
