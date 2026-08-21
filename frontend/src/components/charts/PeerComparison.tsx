'use client';

import React from 'react';
import Link from 'next/link';
import type { ChartData, PeerComparison as PeerComparisonRow } from '@/types';

/**
 * Where the company's multiples sit against comparable companies.
 *
 * A P/E of 35 is expensive for a utility and cheap for a fast grower, so the
 * absolute number on its own tells the reader very little.
 */

type Peers = NonNullable<ChartData['peers']>;

const fmtRatio = (v: number | null) => (v != null ? v.toFixed(2) : 'N/A');
const fmtPct = (v: number | null) => (v != null ? `${(v * 100).toFixed(1)}%` : 'N/A');

function isMargin(key: string): boolean {
  return key.includes('margin');
}

/**
 * A discount is good for a multiple and bad for a margin, so the colour keys
 * off `lower_is_better` rather than the sign alone.
 */
function verdictTone(row: PeerComparisonRow): string {
  if (row.premium_discount == null) return 'text-gray-500';
  if (Math.abs(row.premium_discount) < 0.1) return 'text-gray-400';
  const favourable = row.lower_is_better ? row.premium_discount < 0 : row.premium_discount > 0;
  return favourable ? 'text-emerald-400' : 'text-amber-400';
}

export default function PeerComparison({ peers }: { peers: Peers }) {
  const rows = peers.comparisons.filter((c) => c.peer_median != null);
  const sector = peers.sector;

  if (!peers.peer_count) {
    return (
      <p className="text-gray-500 text-sm">
        No comparable companies were available for this ticker.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-gray-400">Compared against</span>
        {peers.companies.map((company) => (
          <Link
            key={company.symbol}
            href={`/chart/${company.symbol}`}
            className="text-xs font-mono bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg px-2 py-1 text-blue-300 transition"
            title={company.name || company.symbol || undefined}
          >
            {company.symbol}
          </Link>
        ))}
      </div>

      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 border-b border-white/10">
                <th className="text-left py-2 font-medium">Metric</th>
                <th className="text-right py-2 font-medium">Company</th>
                <th className="text-right py-2 font-medium">Peer median</th>
                <th className="text-right py-2 font-medium">Position</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const format = isMargin(row.key ?? '') ? fmtPct : fmtRatio;
                return (
                  <tr key={row.key} className="border-b border-white/5 last:border-0">
                    <td className="py-2.5 text-gray-300">{row.label}</td>
                    <td className="py-2.5 text-right font-mono text-white">
                      {format(row.company)}
                    </td>
                    <td className="py-2.5 text-right font-mono text-gray-400">
                      {format(row.peer_median)}
                    </td>
                    <td className={`py-2.5 text-right ${verdictTone(row)}`}>{row.verdict}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {(sector.sector_pe != null || sector.industry_pe != null) && (
        <div className="grid sm:grid-cols-2 gap-3">
          {sector.sector_pe != null && (
            <BenchmarkCard
              label={`${sector.sector || 'Sector'} sector P/E`}
              value={sector.sector_pe}
              relative={sector.vs_sector_pe}
            />
          )}
          {sector.industry_pe != null && (
            <BenchmarkCard
              label={`${sector.industry || 'Industry'} P/E`}
              value={sector.industry_pe}
              relative={sector.vs_industry_pe}
            />
          )}
        </div>
      )}

      {peers.summary && <p className="text-sm text-gray-400 leading-relaxed">{peers.summary}</p>}

      {sector.as_of && (
        <p className="text-xs text-gray-600">Sector snapshot as of {sector.as_of}.</p>
      )}
    </div>
  );
}

function BenchmarkCard({
  label,
  value,
  relative,
}: {
  label: string;
  value: number;
  relative: number | null;
}) {
  // `relative` is the company measured against the benchmark, so a negative
  // value means the company is the cheaper of the two.
  const phrase =
    relative == null
      ? null
      : Math.abs(relative) < 0.05
      ? 'the company trades in line'
      : `the company trades ${Math.abs(relative * 100).toFixed(0)}% ${
          relative > 0 ? 'above' : 'below'
        }`;

  return (
    <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-3">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className="text-xl font-bold text-white">{value.toFixed(2)}</p>
      {phrase && <p className="text-xs text-gray-500 mt-1">{phrase}</p>}
    </div>
  );
}
