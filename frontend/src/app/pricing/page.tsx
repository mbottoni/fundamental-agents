'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import api from '@/lib/api';
import { loadStripe } from '@stripe/stripe-js';

const stripePublishableKey = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;
const stripePromise = stripePublishableKey ? loadStripe(stripePublishableKey) : null;

/* ── Plan definitions ──────────────────────────────────────── */
const PLANS = [
  { id: 'free', name: 'Free', price: '$0', period: 'per month', highlight: false, cta: 'Get started', analyses: '3 analyses/day' },
  { id: 'premium', name: 'Premium', price: '$20', period: 'per month', highlight: true, cta: 'Subscribe', analyses: 'Unlimited analyses' },
];

/* ── Feature comparison data ───────────────────────────────── */
const FEATURE_SECTIONS = [
  {
    title: 'Stock Analysis',
    subtitle: 'Unlock in-depth stock research with stunning visualizations',
    features: [
      { name: 'Stock Analysis Reports', free: '3/day', premium: 'Unlimited' },
      { name: 'Valuation Analysis (DCF + multiples)', free: true, premium: true },
      { name: 'Growth Analysis', free: true, premium: true },
      { name: 'Financial Health Assessment', free: true, premium: true },
      { name: 'Profitability & Efficiency Analysis', free: true, premium: true },
      { name: 'Technical Indicators (RSI, MACD, Bollinger)', free: true, premium: true },
      { name: 'Risk Assessment (Sharpe, VaR, Beta)', free: true, premium: true },
      { name: 'News Sentiment Analysis', free: true, premium: true },
      { name: 'Interactive Charts & Visualizations', free: true, premium: true },
      { name: 'Investment Recommendation & Thesis', free: true, premium: true },
    ],
  },
  {
    title: 'Portfolio & Watchlist',
    subtitle: 'Track and optimize your investments',
    features: [
      { name: 'Watchlist', free: true, premium: true },
      { name: 'Analysis History & Archive', free: true, premium: true },
      { name: 'Dashboard', free: true, premium: true },
    ],
  },
  {
    title: 'Premium Benefits',
    subtitle: 'Enhanced experience for serious investors',
    features: [
      { name: 'Priority Processing', free: false, premium: true },
      { name: 'Unlimited Daily Analyses', free: false, premium: true },
      { name: 'Email Support', free: false, premium: true },
    ],
  },
];

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
        const { error: stripeError } = await stripe.redirectToCheckout({ sessionId: data.sessionId });
        if (stripeError) setError(stripeError.message || 'An error occurred with payment.');
      }
    } catch {
      setError('Could not initiate checkout. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white text-gray-900">
      {/* ── Navigation ─────────────────────────────────────── */}
      <nav className="border-b border-gray-100 bg-white">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link href="/" className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
              </div>
              <span className="text-lg font-bold tracking-tight">StockAnalyzer</span>
            </Link>
            <div className="flex items-center gap-4">
              <Link href="/dashboard" className="text-sm text-gray-500 hover:text-gray-900 transition font-medium">
                Dashboard
              </Link>
              {!isAuthenticated && (
                <Link href="/register" className="text-sm bg-brand-600 hover:bg-brand-700 text-white px-5 py-2 rounded-lg transition font-semibold">
                  Sign Up
                </Link>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* ── Header ─────────────────────────────────────────── */}
      <div className="pt-16 pb-12 px-6 text-center">
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
          Plans for every Investor
        </h1>
        <p className="text-gray-500 text-lg max-w-xl mx-auto">
          Start free. Upgrade when you need unlimited analyses and priority processing.
        </p>
      </div>

      {/* ── Plan Cards ─────────────────────────────────────── */}
      <div className="max-w-3xl mx-auto px-6 mb-16">
        <div className="grid md:grid-cols-2 gap-6">
          {PLANS.map((plan) => (
            <div
              key={plan.id}
              className={`rounded-2xl p-8 flex flex-col relative ${
                plan.highlight
                  ? 'bg-brand-600 text-white shadow-xl shadow-brand-600/20'
                  : 'bg-white border border-gray-200'
              }`}
            >
              {plan.highlight && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-amber-400 text-amber-900 text-[10px] font-bold uppercase tracking-wider px-4 py-1 rounded-full">
                  Most Popular
                </span>
              )}
              <h2 className="text-xl font-bold mb-1">{plan.name}</h2>
              <p className={`text-sm mb-4 ${plan.highlight ? 'text-blue-100' : 'text-gray-400'}`}>
                {plan.analyses}
              </p>
              <p className="text-4xl font-bold mb-6">
                {plan.price}
                <span className={`text-sm font-normal ml-1 ${plan.highlight ? 'text-blue-200' : 'text-gray-400'}`}>
                  {plan.period}
                </span>
              </p>
              {plan.id === 'free' ? (
                <Link
                  href="/register"
                  className="block text-center font-semibold py-3 rounded-xl border border-gray-200 hover:bg-gray-50 transition"
                >
                  {plan.cta}
                </Link>
              ) : (
                <button
                  onClick={handleCheckout}
                  disabled={isLoading}
                  className="block w-full text-center font-semibold py-3 rounded-xl bg-white text-brand-700 hover:bg-blue-50 transition disabled:opacity-50"
                >
                  {isLoading ? 'Processing...' : plan.cta}
                </button>
              )}
              {error && plan.id === 'premium' && (
                <p className="text-red-200 text-center mt-3 text-sm">{error}</p>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── Feature Comparison Table ───────────────────────── */}
      <div className="max-w-4xl mx-auto px-6 pb-24">
        {/* Table header */}
        <div className="sticky top-0 bg-white z-10 border-b border-gray-200 grid grid-cols-[1fr_120px_120px] items-end py-4">
          <div />
          <div className="text-center">
            <p className="font-bold text-sm">Free</p>
          </div>
          <div className="text-center">
            <p className="font-bold text-sm text-brand-600">Premium</p>
          </div>
        </div>

        {/* Feature sections */}
        {FEATURE_SECTIONS.map((section) => (
          <div key={section.title} className="mb-8">
            <div className="py-4 border-b border-gray-100">
              <h3 className="font-bold text-lg">{section.title}</h3>
              <p className="text-sm text-gray-400">{section.subtitle}</p>
            </div>
            {section.features.map((feature) => (
              <div
                key={feature.name}
                className="grid grid-cols-[1fr_120px_120px] items-center py-3 border-b border-gray-50 hover:bg-gray-50/50 transition-colors"
              >
                <p className="text-sm text-gray-700 pr-4">{feature.name}</p>
                <div className="text-center">
                  <FeatureValue value={feature.free} />
                </div>
                <div className="text-center">
                  <FeatureValue value={feature.premium} highlight />
                </div>
              </div>
            ))}
          </div>
        ))}

        {/* Bottom CTA */}
        <div className="grid md:grid-cols-2 gap-6 mt-12">
          <div className="text-center">
            <p className="text-gray-400 text-sm mb-3">Free version</p>
            <Link href="/register" className="btn-secondary inline-block w-full md:w-auto">
              Get started
            </Link>
          </div>
          <div className="text-center">
            <p className="text-brand-600 text-sm font-medium mb-3">Premium version — $20/month</p>
            <button onClick={handleCheckout} disabled={isLoading} className="btn-primary w-full md:w-auto">
              {isLoading ? 'Processing...' : 'Subscribe now'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Feature Value Display ─────────────────────────────────── */
function FeatureValue({ value, highlight = false }: { value: boolean | string; highlight?: boolean }) {
  if (typeof value === 'string') {
    return <span className={`text-sm font-medium ${highlight ? 'text-brand-600' : 'text-gray-700'}`}>{value}</span>;
  }
  if (value) {
    return (
      <svg className={`w-5 h-5 mx-auto ${highlight ? 'text-brand-600' : 'text-emerald-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
      </svg>
    );
  }
  return (
    <svg className="w-5 h-5 mx-auto text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 12H6" />
    </svg>
  );
}
