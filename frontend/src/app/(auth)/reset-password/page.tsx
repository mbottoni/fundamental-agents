'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useSearchParams } from 'next/navigation';
import api from '@/lib/api';
import { getErrorMessage } from '@/lib/errors';

export default function ResetPasswordPage() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token') || '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    setIsSubmitting(true);
    try {
      await api.post('/auth/reset-password', { token, new_password: password });
      setSuccess(true);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to reset password. The link may have expired.'));
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

      <div className="relative z-10 glass-card-strong p-8 sm:p-10 w-full max-w-md mx-4 shadow-2xl">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold">{success ? 'Password Reset!' : 'Set New Password'}</h2>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-xl mb-5 text-center text-sm">
            {error}
          </div>
        )}

        {success ? (
          <div className="text-center">
            <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 p-4 rounded-xl text-sm mb-6">
              Your password has been reset successfully.
            </div>
            <Link href="/login" className="btn-primary inline-block">Sign In</Link>
          </div>
        ) : !token ? (
          <div className="text-center">
            <p className="text-red-400 text-sm mb-4">Invalid or missing reset token.</p>
            <Link href="/forgot-password" className="text-blue-400 hover:underline text-sm">Request a new reset link</Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="password" className="block text-gray-400 mb-1.5 text-sm font-medium">New Password</label>
              <input type="password" id="password" value={password} onChange={(e) => setPassword(e.target.value)}
                className="input-field" required minLength={8} disabled={isSubmitting} />
            </div>
            <div>
              <label htmlFor="confirm" className="block text-gray-400 mb-1.5 text-sm font-medium">Confirm Password</label>
              <input type="password" id="confirm" value={confirm} onChange={(e) => setConfirm(e.target.value)}
                className="input-field" required minLength={8} disabled={isSubmitting} />
            </div>
            <button type="submit" className="w-full btn-primary text-center" disabled={isSubmitting}>
              {isSubmitting ? 'Resetting...' : 'Reset Password'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
