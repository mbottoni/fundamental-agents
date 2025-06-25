'use client';

import React from 'react';
import { useAuth } from '@/hooks/useAuth';
import api from '@/lib/api';
import { loadStripe } from '@stripe/stripe-js';

// Make sure to replace with your actual public key
const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || '');

const PricingPage = () => {
  const { token } = useAuth();
  
  const handleCheckout = async (priceId: string) => {
    try {
      const { data } = await api.post('/stripe/create-checkout-session', { price_id: priceId }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const stripe = await stripePromise;
      if (stripe) {
        await stripe.redirectToCheckout({ sessionId: data.sessionId });
      }
    } catch (error) {
      console.error('Checkout error:', error);
    }
  };

  return (
    <div className="bg-gray-900 text-white min-h-screen flex flex-col items-center justify-center p-8">
      <h1 className="text-4xl font-bold mb-8">Pricing Plans</h1>
      <div className="bg-gray-800 p-8 rounded-lg shadow-lg w-full max-w-sm">
        <h2 className="text-2xl font-semibold text-center mb-4">Premium</h2>
        <p className="text-5xl font-bold text-center mb-6">$20<span className="text-lg text-gray-400">/mo</span></p>
        <ul className="text-gray-400 space-y-2 mb-8">
          <li>✓ Unlimited Stock Analysis</li>
          <li>✓ Full PDF Reports</li>
          <li>✓ Priority Support</li>
        </ul>
        <button
          onClick={() => handleCheckout('your_premium_price_id')} // Replace with your actual Price ID from Stripe
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-lg transition duration-300"
        >
          Subscribe
        </button>
      </div>
    </div>
  );
};

export default PricingPage; 