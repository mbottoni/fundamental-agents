'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import api from '@/lib/api';
import { getErrorMessage } from '@/lib/errors';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      await api.post('/auth/forgot-password', { email });
      setSent(true);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to send reset link.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      <div className="absolute inset-0">
        <Image src="/mountain.jpg" alt="" fill className="object-cover" priority quality={75} />
        <div className="absolute inset-0 bg-gray-950/60 backdrop-blur-sm" />
      </div>

      <Link
        href="/login"
        className="absolute top-6 left-6 z-20 text-white/60 hover:text-white transition flex items-center gap-1.5 text-sm"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back to login
      </Link>

      <div className="relative z-10 glass-card-strong p-8 sm:p-10 w-full max-w-md mx-4 shadow-2xl">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold">Reset Password</h2>
          <p className="text-gray-400 text-sm mt-1">
            {sent ? 'Check your email for a reset link.' : "Enter your email and we'll send you a reset link."}
          </p>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-xl mb-5 text-center text-sm">
            {error}
          </div>
        )}

        {sent ? (
          <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 p-4 rounded-xl text-center text-sm">
            If an account exists with <strong>{email}</strong>, a reset link has been sent.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-gray-400 mb-1.5 text-sm font-medium">Email</label>
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-field"
                placeholder="you@example.com"
                required
                disabled={isSubmitting}
              />
            </div>
            <button type="submit" className="w-full btn-primary text-center" disabled={isSubmitting}>
              {isSubmitting ? 'Sending...' : 'Send Reset Link'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
