"""
Peer Comparison Agent
=====================
Places the company's multiples next to those of comparable businesses and its
sector.

A P/E of 35 is neither expensive nor cheap on its own: it is expensive for a
utility and cheap for a company growing 40% a year. Absolute multiples were
being scored against fixed thresholds, which systematically penalised every
company in a highly rated industry and flattered every company in a cheap one.

Both sides of the comparison come from the same provider endpoint, so the
company is measured exactly the way its peers are rather than having our own
computed figures set against theirs.
"""

import logging
import statistics
from typing import Any, Optional

logger = logging.getLogger("stock_analyzer.agents.peer_comparison")


class Comparison:
    """One metric compared against the peer group."""

    def __init__(self, key: str, label: str, lower_is_better: bool) -> None:
        self.key = key
        self.label = label
        self.lower_is_better = lower_is_better
        self.company: Optional[float] = None
        self.peer_median: Optional[float] = None
        self.premium_discount: Optional[float] = None
        self.percentile: Optional[float] = None

    @property
    def complete(self) -> bool:
        return self.company is not None and self.peer_median is not None

    def verdict(self) -> str:
        """Plain-language reading of where the company sits."""
        if self.premium_discount is None:
            return "not comparable"
        if abs(self.premium_discount) < 0.10:
            return "in line with peers"
        direction = "above" if self.premium_discount > 0 else "below"
        return f"{abs(self.premium_discount):.0%} {direction} the peer median"

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "company": round(self.company, 2) if self.company is not None else None,
            "peer_median": round(self.peer_median, 2) if self.peer_median is not None else None,
            "premium_discount": (
                round(self.premium_discount, 4) if self.premium_discount is not None else None
            ),
            "percentile": round(self.percentile, 2) if self.percentile is not None else None,
            "lower_is_better": self.lower_is_better,
            "verdict": self.verdict(),
        }


class PeerComparisonAgent:
    """Compares a company's multiples against its peers and sector."""

    # (metric key, TTM field, label, lower is better)
    METRICS: list[tuple[str, str, str, bool]] = [
        ("pe_ratio", "priceToEarningsRatioTTM", "P/E", True),
        ("pb_ratio", "priceToBookRatioTTM", "P/B", True),
        ("ps_ratio", "priceToSalesRatioTTM", "P/S", True),
        ("p_fcf", "priceToFreeCashFlowRatioTTM", "P/FCF", True),
        ("net_margin", "netProfitMarginTTM", "Net Margin", False),
        ("operating_margin", "operatingProfitMarginTTM", "Operating Margin", False),
        ("de_ratio", "debtToEquityRatioTTM", "Debt/Equity", True),
    ]

    # Multiples that make sense only when positive; a negative P/E means the
    # company is loss-making, not that it is cheap.
    POSITIVE_ONLY = {"pe_ratio", "pb_ratio", "ps_ratio", "p_fcf"}

    # Which comparisons feed the relative valuation score, and how heavily.
    VALUATION_WEIGHTS = {"pe_ratio": 0.40, "ps_ratio": 0.20, "pb_ratio": 0.15, "p_fcf": 0.25}
    # A discount or premium this large or greater is a full-strength signal.
    FULL_SIGNAL_GAP = 0.40

    MIN_PEERS = 2

    # ── helpers ───────────────────────────────────────────────

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number == number else None  # reject NaN

    def _usable(self, key: str, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        if key in self.POSITIVE_ONLY and value <= 0:
            return None
        return value

    @staticmethod
    def _percentile(value: float, population: list[float], lower_is_better: bool) -> float:
        """
        Where the company sits within the peer group, as 0-100 where higher is
        better. For a multiple that means cheaper; for a margin, fatter.
        """
        if not population:
            return 50.0
        if lower_is_better:
            better = sum(1 for p in population if value < p)
        else:
            better = sum(1 for p in population if value > p)
        return 100.0 * better / len(population)

    # ── comparison building ───────────────────────────────────

    def _compare(
        self, company_ratios: dict, peer_ratios: dict[str, dict]
    ) -> list[Comparison]:
        comparisons: list[Comparison] = []

        for key, field, label, lower_is_better in self.METRICS:
            comparison = Comparison(key, label, lower_is_better)
            comparison.company = self._usable(key, self._as_float(company_ratios.get(field)))

            peer_values = [
                value
                for value in (
                    self._usable(key, self._as_float(ratios.get(field)))
                    for ratios in peer_ratios.values()
                )
                if value is not None
            ]

            if len(peer_values) >= self.MIN_PEERS:
                comparison.peer_median = statistics.median(peer_values)
                if comparison.company is not None and comparison.peer_median:
                    comparison.premium_discount = (
                        comparison.company - comparison.peer_median
                    ) / abs(comparison.peer_median)
                    comparison.percentile = self._percentile(
                        comparison.company, peer_values, lower_is_better
                    )

            comparisons.append(comparison)

        return comparisons

    def _relative_valuation_score(self, comparisons: list[Comparison]) -> Optional[float]:
        """
        Blend the valuation multiples into a single -1..+1 score, where
        positive means cheap relative to the peer group.
        """
        components: list[tuple[float, float]] = []
        for comparison in comparisons:
            weight = self.VALUATION_WEIGHTS.get(comparison.key)
            if weight is None or comparison.premium_discount is None:
                continue
            # A discount (negative premium) is a positive signal.
            signal = -comparison.premium_discount / self.FULL_SIGNAL_GAP
            components.append((max(-1.0, min(1.0, signal)), weight))

        if not components:
            return None
        total_weight = sum(w for _, w in components)
        return sum(s * w for s, w in components) / total_weight

    def _sector_comparison(
        self, company_pe: Optional[float], sector_valuation: dict
    ) -> dict[str, Any]:
        """Company P/E against the sector and industry snapshots."""
        result: dict[str, Any] = {
            "sector": sector_valuation.get("sector"),
            "industry": sector_valuation.get("industry"),
            "sector_pe": self._as_float(sector_valuation.get("sector_pe")),
            "industry_pe": self._as_float(sector_valuation.get("industry_pe")),
            "as_of": sector_valuation.get("date"),
        }

        for scope in ("sector", "industry"):
            benchmark = result.get(f"{scope}_pe")
            if company_pe and company_pe > 0 and benchmark and benchmark > 0:
                result[f"vs_{scope}_pe"] = round((company_pe - benchmark) / benchmark, 4)
            else:
                result[f"vs_{scope}_pe"] = None

        return result

    def _summary(
        self, comparisons: list[Comparison], score: Optional[float], peer_count: int
    ) -> str:
        if score is None:
            return "Not enough comparable data to place this company against its peers."

        if score > 0.25:
            stance = "trades at a discount to its peer group"
        elif score < -0.25:
            stance = "trades at a premium to its peer group"
        else:
            stance = "trades broadly in line with its peer group"

        quality = next(
            (c for c in comparisons if c.key == "operating_margin" and c.premium_discount is not None),
            None,
        )
        if quality is not None:
            better = "more" if quality.premium_discount > 0 else "less"
            return (
                f"Against {peer_count} peers the company {stance}, and is {better} profitable "
                f"than the median on operating margin."
            )
        return f"Against {peer_count} peers the company {stance}."

    # ── main entry point ──────────────────────────────────────

    def run(self, raw_data: dict, metrics: Optional[dict] = None) -> dict[str, Any]:
        """Compare the company against its peers and sector."""
        peers_payload = raw_data.get("peers") or {}
        peer_ratios: dict[str, dict] = peers_payload.get("ratios") or {}
        companies = peers_payload.get("companies") or []
        sector_valuation = raw_data.get("sector_valuation") or {}

        company_ratios = ((raw_data.get("ttm") or {}).get("ratios")) or {}
        if not company_ratios and metrics:
            # Fall back to our own computed figures. Less exact, since the
            # peers' come from the provider, but better than no comparison.
            valuation_group = (metrics.get("groups") or {}).get("valuation", {})
            company_ratios = {
                "priceToEarningsRatioTTM": valuation_group.get("pe_ratio"),
                "priceToBookRatioTTM": valuation_group.get("pb_ratio"),
                "priceToSalesRatioTTM": valuation_group.get("ps_ratio"),
            }

        comparisons = self._compare(company_ratios, peer_ratios)
        complete = [c for c in comparisons if c.premium_discount is not None]
        score = self._relative_valuation_score(comparisons)

        company_pe = self._usable(
            "pe_ratio", self._as_float(company_ratios.get("priceToEarningsRatioTTM"))
        )
        sector = self._sector_comparison(company_pe, sector_valuation)

        result = {
            "peer_count": len(peer_ratios),
            "peers": [
                {
                    "symbol": company.get("symbol"),
                    "name": company.get("companyName"),
                    "market_cap": company.get("mktCap"),
                }
                for company in companies
                if company.get("symbol") in peer_ratios
            ],
            "comparisons": [c.as_dict() for c in comparisons],
            "sector": sector,
            "relative_valuation_score": round(score, 3) if score is not None else None,
            "summary": self._summary(comparisons, score, len(peer_ratios)),
        }

        if not peer_ratios:
            result["error"] = "No comparable companies were available for this ticker."

        logger.info(
            "Peer comparison complete: %d peers, %d comparable metrics, relative score %s",
            len(peer_ratios), len(complete), result["relative_valuation_score"],
        )
        return result
