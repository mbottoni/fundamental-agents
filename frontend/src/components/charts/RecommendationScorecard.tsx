'use client';

import React from 'react';
import type { ChartData, RecommendationFactor } from '@/types';

/**
 * The factor breakdown behind the buy/hold/sell call.
 *
 * The backend scores six weighted factors and records every driver, but the
 * result only ever appeared as a line of markdown, so the reasoning behind the
 * headline recommendation was invisible.
 */

type Recommendation = NonNullable<ChartData['recommendation']>;

const CALL_STYLES: Record<string, { text: string; bg: string; ring: string }> = {
  'strong buy': { text: 'text-emerald-300', bg: 'bg-emerald-500/15', ring: 'ring-emerald-500/40' },
  buy: { text: 'text-emerald-400', bg: 'bg-emerald-500/10', ring: 'ring-emerald-500/30' },
  hold: { text: 'text-gray-300', bg: 'bg-gray-500/10', ring: 'ring-gray-500/30' },
  sell: { text: 'text-red-400', bg: 'bg-red-500/10', ring: 'ring-red-500/30' },
  'strong sell': { text: 'text-red-300', bg: 'bg-red-500/15', ring: 'ring-red-500/40' },
};

function scoreColor(score: number): string {
  if (score >= 0.5) return 'bg-emerald-400';
  if (score >= 0.15) return 'bg-emerald-500/70';
  if (score > -0.15) return 'bg-gray-500';
  if (score > -0.5) return 'bg-red-500/70';
  return 'bg-red-400';
}

/** A -1..+1 score drawn as a bar running out from a centre line. */
function ScoreBar({ score }: { score: number }) {
  const magnitude = Math.min(Math.abs(score), 1) * 50;
  const positive = score >= 0;

  return (
    <div className="relative h-2 w-full rounded-full bg-white/5" aria-hidden="true">
      <div className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-white/20" />
      <div
        className={`absolute top-0 h-full rounded-full ${scoreColor(score)}`}
        style={{
          left: positive ? '50%' : `${50 - magnitude}%`,
          width: `${magnitude}%`,
        }}
      />
    </div>
  );
}

function FactorRow({ factor }: { factor: RecommendationFactor }) {
  const unavailable = factor.score === null;

  return (
    <div className="py-3 border-b border-white/5 last:border-0">
      <div className="flex items-baseline justify-between gap-4 mb-2">
        <div className="flex items-baseline gap-2 min-w-0">
          <span className="font-medium text-white truncate">{factor.label}</span>
          <span className="text-xs text-gray-500 shrink-0">
            {((factor.weight ?? 0) * 100).toFixed(0)}% weight
          </span>
        </div>
        <span
          className={`font-mono text-sm shrink-0 ${
            unavailable
              ? 'text-gray-600'
              : factor.score! > 0
              ? 'text-emerald-400'
              : factor.score! < 0
              ? 'text-red-400'
              : 'text-gray-400'
          }`}
        >
          {unavailable ? 'no data' : `${factor.score! > 0 ? '+' : ''}${factor.score!.toFixed(2)}`}
        </span>
      </div>

      {!unavailable && <ScoreBar score={factor.score!} />}

      {factor.drivers.length > 0 && (
        <p className="mt-2 text-xs text-gray-500 leading-relaxed">
          {factor.drivers.join(' · ')}
        </p>
      )}
    </div>
  );
}

export default function RecommendationScorecard({
  recommendation,
}: {
  recommendation: Recommendation;
}) {
  const call = (recommendation.call || 'hold').toLowerCase();
  const style = CALL_STYLES[call] || CALL_STYLES.hold;
  const score = recommendation.composite_score ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-6">
        <div className={`rounded-2xl px-6 py-4 ring-1 ${style.bg} ${style.ring}`}>
          <p className={`text-3xl font-bold uppercase tracking-wide ${style.text}`}>
            {call}
          </p>
          {recommendation.confidence != null && (
            <p className="text-sm text-gray-400 mt-1">
              {recommendation.confidence}% confidence
            </p>
          )}
        </div>

        <div className="min-w-[12rem] flex-1">
          <div className="flex items-baseline justify-between mb-2">
            <span className="text-sm text-gray-400">Composite score</span>
            <span className="font-mono text-lg text-white">
              {score > 0 ? '+' : ''}
              {score.toFixed(2)}
            </span>
          </div>
          <ScoreBar score={score} />
          <div className="flex justify-between text-[10px] text-gray-600 mt-1">
            <span>−1.0</span>
            <span>0</span>
            <span>+1.0</span>
          </div>
        </div>
      </div>

      {recommendation.rationale && (
        <p className="text-sm text-gray-300 leading-relaxed">{recommendation.rationale}.</p>
      )}

      <div>
        {recommendation.factors.map((factor) => (
          <FactorRow key={factor.key} factor={factor} />
        ))}
      </div>

      {recommendation.coverage != null && recommendation.coverage < 1 && (
        <p className="text-xs text-gray-500">
          {(recommendation.coverage * 100).toFixed(0)}% of the scoring model had data
          available; missing factors had their weight redistributed across the rest.
        </p>
      )}
    </div>
  );
}
