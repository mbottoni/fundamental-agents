'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
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
    <div className="min-h-screen relative overflow-hidden">
      {/* Subtle background */}
      <div className="absolute inset-0 opacity-20">
        <Image src="/mountain.jpg" alt="" fill className="object-cover" quality={50} />
      </div>
      <div className="absolute inset-0 bg-gradient-to-b from-gray-950 via-gray-950/95 to-gray-950" />

      {/* Navigation */}
      <nav className="relative z-10 max-w-7xl mx-auto px-6 lg:px-8">
        <div className="flex justify-between items-center h-20">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center border border-white/20">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
            <span className="text-lg font-semibold tracking-tight text-white">StockAnalyzer AI</span>
          </Link>
          <Link href="/dashboard" className="text-sm text-gray-400 hover:text-white transition">
            Dashboard
          </Link>
        </div>
      </nav>

      {/* Content */}
      <div className="relative z-10 max-w-4xl mx-auto px-6 pt-12 pb-24">
        <div className="text-center mb-16">
          <p className="text-sm font-medium tracking-widest uppercase text-gray-500 mb-3">Pricing</p>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
            Simple, transparent pricing.
          </h1>
          <p className="text-gray-400 text-lg max-w-xl mx-auto">
            Start free. Upgrade when you need unlimited analyses and priority processing.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6 max-w-3xl mx-auto">
          {/* Free Plan */}
          <div className="glass-card p-8 flex flex-col">
            <div className="mb-6">
              <h2 className="text-xl font-semibold mb-1">Free</h2>
              <p className="text-gray-500 text-sm">For getting started</p>
            </div>
            <p className="text-5xl font-bold mb-8">
              $0<span className="text-lg text-gray-500 font-normal">/month</span>
            </p>
            <ul className="space-y-3 mb-8 flex-grow">
              <PricingFeature included>3 stock analyses</PricingFeature>
              <PricingFeature included>Full AI-powered reports</PricingFeature>
              <PricingFeature included>30+ financial metrics</PricingFeature>
              <PricingFeature included>Technical analysis</PricingFeature>
              <PricingFeature included>Watchlist</PricingFeature>
              <PricingFeature>Unlimited analyses</PricingFeature>
              <PricingFeature>Priority processing</PricingFeature>
            </ul>
            <Link
              href="/dashboard"
              className="btn-secondary text-center w-full"
            >
              Get Started
            </Link>
          </div>

          {/* Premium Plan */}
          <div className="glass-card p-8 flex flex-col border-blue-500/30 relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-blue-500 to-transparent" />
            <div className="absolute -top-px left-1/2 -translate-x-1/2">
              <span className="bg-blue-500 text-white text-[10px] font-bold uppercase tracking-wider px-4 py-1 rounded-b-lg">
                Most Popular
              </span>
            </div>
            <div className="mb-6 mt-3">
              <h2 className="text-xl font-semibold mb-1">Premium</h2>
              <p className="text-gray-500 text-sm">For serious investors</p>
            </div>
            <p className="text-5xl font-bold mb-8">
              $20<span className="text-lg text-gray-500 font-normal">/month</span>
            </p>
            <ul className="space-y-3 mb-8 flex-grow">
              <PricingFeature included>Unlimited stock analyses</PricingFeature>
              <PricingFeature included>Full AI-powered reports</PricingFeature>
              <PricingFeature included>30+ financial metrics</PricingFeature>
              <PricingFeature included>Technical analysis</PricingFeature>
              <PricingFeature included>Watchlist</PricingFeature>
              <PricingFeature included>Priority processing</PricingFeature>
              <PricingFeature included>Email support</PricingFeature>
            </ul>
            <button
              onClick={handleCheckout}
              className="btn-primary text-center w-full"
              disabled={isLoading}
            >
              {isLoading ? 'Processing...' : 'Subscribe'}
            </button>
            {error && (
              <p className="text-red-400 text-center mt-3 text-sm">{error}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function PricingFeature({
  children,
  included = false,
}: {
  children: React.ReactNode;
  included?: boolean;
}) {
  return (
    <li className={`flex items-center gap-3 text-sm ${included ? 'text-gray-300' : 'text-gray-600'}`}>
      {included ? (
        <svg className="w-4 h-4 text-emerald-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <svg className="w-4 h-4 text-gray-700 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      )}
      {children}
    </li>
  );
}
