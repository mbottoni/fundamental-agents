'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useSearchParams } from 'next/navigation';
import api from '@/lib/api';

export default function VerifyEmailPage() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token') || '';
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Missing verification token.');
      return;
    }

    (async () => {
      try {
        await api.post('/auth/verify-email', { token });
        setStatus('success');
        setMessage('Your email has been verified!');
      } catch {
        setStatus('error');
        setMessage('Invalid or expired verification link.');
      }
    })();
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      <div className="absolute inset-0">
        <Image src="/mountain.jpg" alt="" fill className="object-cover" priority quality={75} />
        <div className="absolute inset-0 bg-gray-950/60 backdrop-blur-sm" />
      </div>

      <div className="relative z-10 glass-card-strong p-8 sm:p-10 w-full max-w-md mx-4 shadow-2xl text-center">
        {status === 'loading' && (
          <div className="flex flex-col items-center gap-4">
            <div className="w-10 h-10 border-2 border-blue-400/30 border-t-blue-400 rounded-full animate-spin" />
            <p className="text-gray-400">Verifying your email...</p>
          </div>
        )}

        {status === 'success' && (
          <div>
            <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold mb-2">Email Verified!</h2>
            <p className="text-gray-400 text-sm mb-6">{message}</p>
            <Link href="/dashboard" className="btn-primary inline-block">Go to Dashboard</Link>
          </div>
        )}

        {status === 'error' && (
          <div>
            <div className="w-16 h-16 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold mb-2">Verification Failed</h2>
            <p className="text-gray-400 text-sm mb-6">{message}</p>
            <Link href="/login" className="text-blue-400 hover:underline text-sm">Back to login</Link>
          </div>
        )}
      </div>
    </div>
  );
}
