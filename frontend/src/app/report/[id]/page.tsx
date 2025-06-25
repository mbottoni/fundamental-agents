'use client';

import React, { useEffect, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import api from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import { useParams } from 'next/navigation';

const ReportPage = () => {
  const { token } = useAuth();
  const [report, setReport] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const params = useParams();
  const { id } = params;

  useEffect(() => {
    if (id) {
      const fetchReport = async () => {
        try {
          const response = await api.get(`/reports/${id}`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          setReport(response.data.content);
        } catch (err: any) {
          setError(err.response?.data?.detail || 'Failed to fetch report.');
        } finally {
          setLoading(false);
        }
      };
      fetchReport();
    }
  }, [id, token]);

  return (
    <div className="bg-gray-900 text-white min-h-screen p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">Analysis Report</h1>
        {loading && <p>Loading report...</p>}
        {error && <p className="text-red-500">{error}</p>}
        {report && (
          <div className="bg-gray-800 p-6 rounded-lg prose prose-invert">
            <ReactMarkdown>{report}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
