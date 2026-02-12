'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import api from '@/lib/api';
import { loadStripe } from '@stripe/stripe-js';

const stripePublishableKey = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;
const stripePromise = stripePublishableKey ? loadStripe(stripePublishableKey) : null;

export default function PricingPage() {
  const { isAuthenticated } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleCheckout = async () => {
    if (!isAuthenticated) {
      setError('Please log in to subscribe.');
      return;
    }

    if (!stripePromise) {
      setError('Payment processing is not configured.');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const { data } = await api.post('/stripe/create-checkout-session');
      const stripe = await stripePromise;
      if (stripe) {
        const { error: stripeError } = await stripe.redirectToCheckout({
          sessionId: data.sessionId,
        });
        if (stripeError) {
          setError(stripeError.message || 'An error occurred with payment.');
        }
      }
    } catch {
      setError('Could not initiate checkout. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-gray-900 text-white min-h-screen flex flex-col items-center justify-center p-8">
      <h1 className="text-4xl font-bold mb-2">Pricing Plans</h1>
      <p className="text-gray-400 mb-8">Unlock unlimited analysis with Premium.</p>

      <div className="grid md:grid-cols-2 gap-6 max-w-2xl w-full">
        {/* Free Plan */}
        <div className="bg-gray-800 p-8 rounded-lg border border-gray-700">
          <h2 className="text-2xl font-semibold text-center mb-4">Free</h2>
          <p className="text-5xl font-bold text-center mb-6">
            $0<span className="text-lg text-gray-400">/mo</span>
          </p>
          <ul className="text-gray-400 space-y-2 mb-8 text-sm">
            <li className="flex items-center gap-2">
              <span className="text-green-400">&#10003;</span> 3 Stock Analyses
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">&#10003;</span> Basic Reports
            </li>
          </ul>
          <Link
            href="/dashboard"
            className="block w-full text-center bg-gray-700 hover:bg-gray-600 text-white font-bold py-2 px-4 rounded-lg transition duration-300"
          >
            Get Started
          </Link>
        </div>

        {/* Premium Plan */}
        <div className="bg-gray-800 p-8 rounded-lg border-2 border-blue-500 relative">
          <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-blue-500 text-white text-xs font-bold px-3 py-1 rounded-full">
            POPULAR
          </div>
          <h2 className="text-2xl font-semibold text-center mb-4">Premium</h2>
          <p className="text-5xl font-bold text-center mb-6">
            $20<span className="text-lg text-gray-400">/mo</span>
          </p>
          <ul className="text-gray-400 space-y-2 mb-8 text-sm">
            <li className="flex items-center gap-2">
              <span className="text-green-400">&#10003;</span> Unlimited Stock Analyses
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">&#10003;</span> Full PDF Reports
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-400">&#10003;</span> Priority Support
            </li>
          </ul>
          <button
            onClick={handleCheckout}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white font-bold py-2 px-4 rounded-lg transition duration-300"
            disabled={isLoading}
          >
            {isLoading ? 'Processing...' : 'Subscribe'}
          </button>
          {error && (
            <p className="text-red-400 text-center mt-3 text-sm">{error}</p>
          )}
        </div>
      </div>

      <Link href="/dashboard" className="text-gray-400 hover:text-white mt-8 text-sm transition">
        &larr; Back to Dashboard
      </Link>
    </div>
  );
}
