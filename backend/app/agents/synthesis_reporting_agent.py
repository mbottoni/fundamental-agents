"""
Synthesis Reporting Agent
=========================
Generates a comprehensive, professional‑grade markdown report that
combines outputs from every analysis agent:
  1. Executive Summary
  2. Company Overview
  3. Valuation (DCF + multiples)
  4. Financial Health (profitability, liquidity, leverage, efficiency)
  5. Growth Analysis
  6. Technical Analysis (indicators + signals)
  7. Risk Assessment
  8. Market Sentiment
  9. Investment Thesis & Recommendation
  10. Disclaimer
"""

import logging
from datetime import date
from typing import Any, Optional, Union

from .recommendation import RecommendationEngine

logger = logging.getLogger("stock_analyzer.agents.synthesis")

Number = Union[int, float]


class SynthesisReportingAgent:
    """Synthesizes all analysis results into a formatted markdown report."""

    def __init__(self, recommendation_engine: Optional[RecommendationEngine] = None) -> None:
        self.recommendation_engine = recommendation_engine or RecommendationEngine()

    # ── formatters ────────────────────────────────────────────

    def _fc(self, value: Any) -> str:
        """Format currency."""
        if isinstance(value, (int, float)):
            if abs(value) >= 1_000_000_000:
                return f"${value / 1_000_000_000:,.2f}B"
            if abs(value) >= 1_000_000:
                return f"${value / 1_000_000:,.2f}M"
            return f"${value:,.2f}"
        return "N/A"

    def _fr(self, value: Any, decimals: int = 2) -> str:
        """Format ratio."""
        if isinstance(value, (int, float)):
            return f"{value:.{decimals}f}"
        return "N/A"

    def _fp(self, value: Any) -> str:
        """Format as percentage (input is decimal: 0.10 → 10.00%)."""
        if isinstance(value, (int, float)):
            return f"{value * 100:.2f}%"
        return "N/A"

    def _fp_raw(self, value: Any) -> str:
        """Format already‑percentage value (input is 10.0 → 10.00%)."""
        if isinstance(value, (int, float)):
            return f"{value:.2f}%"
        return "N/A"

    def _fn(self, value: Any) -> str:
        """Format large number."""
        if isinstance(value, (int, float)):
            if abs(value) >= 1_000_000_000:
                return f"{value / 1_000_000_000:,.2f}B"
            if abs(value) >= 1_000_000:
                return f"{value / 1_000_000:,.2f}M"
            if abs(value) >= 1_000:
                return f"{value / 1_000:,.1f}K"
            return f"{value:,.0f}"
        return "N/A"

    # ── section builders ──────────────────────────────────────

    def _section_header(self, profile: dict, ticker: str, current_price: Optional[Number]) -> str:
        company = profile.get("companyName", "Unknown Company")
        industry = profile.get("industry", "N/A")
        sector = profile.get("sector", "N/A")
        exchange = profile.get("exchangeFullName", "N/A")
        return "\n\n".join([
            f"# Financial Analysis Report: {company} ({ticker})",
            f"**Report Date:** {date.today().strftime('%B %d, %Y')}",
            f"**Industry:** {industry} | **Sector:** {sector} | **Exchange:** {exchange}",
            f"**Current Price:** {self._fc(current_price)}",
        ])

    def _section_executive_summary(
        self, assessment: dict, risk_rating: str,
        current_price: Optional[Number], dcf_value: Optional[Number],
        metrics: dict, technical: dict,
    ) -> str:
        lines = ["## Executive Summary", ""]
        lines.append(
            f"**Recommendation: {assessment['recommendation'].upper()}** "
            f"(Confidence: {assessment['confidence']}%)"
        )
        lines.append(
            f"- **Composite Score:** {assessment['composite_score']:+.2f} on a −1 to +1 scale, "
            f"{assessment['rationale']}"
        )
        if isinstance(current_price, (int, float)) and isinstance(dcf_value, (int, float)):
            upside = (dcf_value - current_price) / current_price
            lines.append(f"- **DCF Upside:** {upside:+.0%} vs. {self._fc(current_price)}")
        lines.append(f"- **Risk Level:** {risk_rating.replace('_', ' ').title()}")

        rsi = technical.get("rsi")
        if rsi is not None:
            lines.append(f"- **RSI:** {self._fr(rsi)} ({'overbought' if rsi > 70 else 'oversold' if rsi < 30 else 'neutral'})")

        pe = metrics.get("pe_ratio")
        if pe is not None:
            lines.append(f"- **P/E Ratio:** {self._fr(pe)}")

        # Coverage tells the reader how much of the model actually had data.
        lines.append(f"- **Factor Coverage:** {assessment['coverage']:.0%} of the scoring model")

        return "\n".join(lines)

    def _section_scorecard(self, assessment: dict) -> str:
        """The per-factor breakdown behind the recommendation."""
        lines = [
            "## Recommendation Scorecard",
            "",
            "Each factor is scored from −1 (poor) to +1 (strong). Factors without "
            "sufficient data are excluded and their weight redistributed.",
            "",
            "| Factor | Weight | Score | Key Drivers |",
            "|---|---|---|---|",
        ]
        for factor in assessment.get("factors", []):
            score = factor.get("score")
            score_cell = f"{score:+.2f}" if score is not None else "—"
            drivers = "; ".join(factor.get("drivers") or []) or "insufficient data"
            lines.append(
                f"| **{factor['label']}** | {factor['weight']:.0%} | {score_cell} | {drivers} |"
            )

        lines.append("")
        lines.append(
            f"**Composite: {assessment['composite_score']:+.2f}** → "
            f"**{assessment['recommendation'].upper()}**"
        )
        return "\n".join(lines)

    def _sensitivity_table(self, sensitivity: dict) -> list[str]:
        """Render the WACC × terminal-growth grid as a markdown table."""
        wacc_values = sensitivity.get("wacc_values") or []
        growth_values = sensitivity.get("terminal_growth_values") or []
        grid = sensitivity.get("grid") or []
        if not wacc_values or not growth_values or not grid:
            return []

        header = " | ".join(f"g = {g * 100:.1f}%" for g in growth_values)
        lines = [
            "",
            "#### Sensitivity — Value per Share",
            "",
            f"| WACC | {header} |",
            "|" + "---|" * (len(growth_values) + 1),
        ]
        for wacc, row in zip(wacc_values, grid):
            cells = " | ".join(self._fc(v) if v is not None else "n/a" for v in row)
            lines.append(f"| **{wacc * 100:.1f}%** | {cells} |")
        return lines

    def _section_valuation(self, valuation: dict, metrics: dict) -> str:
        lines = ["## Valuation Analysis", ""]

        dcf = valuation.get("dcf_intrinsic_value_per_share")
        wacc = valuation.get("wacc")
        lines.append("### DCF Model")
        if valuation.get("method"):
            lines.append(f"- **Method:** {valuation['method']}")
        lines.append(f"- **Intrinsic Value (DCF):** {self._fc(dcf)}")

        sensitivity = valuation.get("sensitivity") or {}
        if sensitivity.get("low") is not None and sensitivity.get("high") is not None:
            lines.append(
                f"- **Range Across Assumptions:** {self._fc(sensitivity['low'])} – "
                f"{self._fc(sensitivity['high'])}"
            )
        if wacc:
            lines.append(f"- **WACC (discount rate):** {self._fp(wacc)}")
        if valuation.get("terminal_growth_rate") is not None:
            lines.append(f"- **Terminal Growth:** {self._fp(valuation['terminal_growth_rate'])}")
        if valuation.get("fcf_growth_rate") is not None:
            basis = valuation.get("fcf_growth_basis")
            suffix = f" (from {basis})" if basis else ""
            lines.append(f"- **Projected FCF Growth:** {self._fp(valuation['fcf_growth_rate'])}{suffix}")
        if valuation.get("latest_fcf"):
            lines.append(f"- **Latest Free Cash Flow:** {self._fc(valuation['latest_fcf'])}")
        if valuation.get("latest_fcff"):
            lines.append(
                f"- **Latest Unlevered FCF (FCFF):** {self._fc(valuation['latest_fcff'])}"
            )
        if valuation.get("terminal_value_share") is not None:
            lines.append(
                f"- **Terminal Value Share:** {self._fp(valuation['terminal_value_share'])} "
                "of enterprise value"
            )

        # Enterprise → equity bridge, so the reader can see where the
        # per-share number actually comes from.
        if valuation.get("enterprise_value") is not None:
            lines.append("")
            lines.append("#### Enterprise → Equity Bridge")
            lines.append(f"- **Enterprise Value:** {self._fc(valuation['enterprise_value'])}")
            lines.append(f"- **Less: Total Debt:** {self._fc(valuation.get('total_debt'))}")
            lines.append(f"- **Plus: Cash & Equivalents:** {self._fc(valuation.get('cash'))}")
            lines.append(f"- **Equity Value:** {self._fc(valuation.get('equity_value'))}")
            lines.append(f"- **Diluted Shares:** {self._fn(valuation.get('shares_outstanding'))}")

        lines.extend(self._sensitivity_table(sensitivity))

        if valuation.get("error"):
            lines.append("")
            lines.append(f"> **DCF unavailable.** {valuation['error']}")
        for warning in valuation.get("warnings") or []:
            lines.append(f"> *Caveat: {warning}*")

        lines.append("")
        lines.append("### Relative Valuation (Multiples)")
        # Be explicit about the reporting period behind these numbers.
        if metrics.get("ttm_metrics"):
            lines.append("*Trailing twelve months where the provider supplies it.*")
        elif metrics.get("basis"):
            lines.append("*Based on the latest annual filing.*")

        val_group = metrics.get("groups", {}).get("valuation", {})
        for label, key in [
            ("P/E Ratio", "pe_ratio"), ("P/B Ratio", "pb_ratio"),
            ("P/S Ratio", "ps_ratio"), ("EV/EBITDA", "ev_ebitda"),
            ("PEG Ratio", "peg_ratio"),
        ]:
            v = val_group.get(key) or metrics.get(key)
            lines.append(f"- **{label}:** {self._fr(v)}")

        return "\n".join(lines)

    @staticmethod
    def _relative_phrase(relative: Optional[float]) -> str:
        """
        Say which way a comparison runs. "(-25% vs. company)" reads as though
        the benchmark sits below the company, when the sign means the opposite.
        """
        if relative is None:
            return ""
        if abs(relative) < 0.05:
            return " — the company trades in line"
        direction = "above" if relative > 0 else "below"
        return f" — the company trades {abs(relative):.0%} {direction}"

    def _section_earnings(self, earnings: dict) -> str:
        """Upcoming results and the recent surprise record."""
        if not earnings or not earnings.get("available"):
            return ""

        lines = ["## Earnings", ""]

        if earnings.get("next_date"):
            days = earnings.get("days_until")
            timing = f" — in {days} day{'s' if days != 1 else ''}" if days is not None else ""
            lines.append(f"- **Next Report:** {earnings['next_date']}{timing}")
            if earnings.get("is_imminent"):
                lines.append(
                    "> **Results are due shortly.** The figures this analysis rests on are "
                    "about to be replaced, which is reflected in the confidence score."
                )
        if earnings.get("eps_estimate") is not None:
            lines.append(f"- **Consensus EPS:** {self._fr(earnings['eps_estimate'])}")
        if earnings.get("beat_rate") is not None:
            lines.append(
                f"- **Beat Rate:** {self._fp(earnings['beat_rate'])} of the last "
                f"{earnings.get('reports_assessed', 0)} reports"
            )

        surprises = [s for s in earnings.get("recent_surprises", []) if s.get("surprise_pct") is not None]
        if surprises:
            lines.append("")
            lines.append("| Report Date | Actual EPS | Estimated | Surprise |")
            lines.append("|---|---|---|---|")
            for surprise in surprises[:4]:
                lines.append(
                    f"| {surprise['date']} | {self._fr(surprise['eps_actual'])} | "
                    f"{self._fr(surprise['eps_estimated'])} | "
                    f"{self._fp(surprise['surprise_pct'])} |"
                )

        return "\n".join(lines)

    def _section_peers(self, peers: dict) -> str:
        """Company multiples next to the peer group and the wider sector."""
        lines = ["## Peer & Sector Comparison", ""]

        if not peers or peers.get("error"):
            lines.append(
                f"*{(peers or {}).get('error', 'No peer data was available for this ticker.')}*"
            )
            return "\n".join(lines)

        peer_list = peers.get("peers") or []
        if peer_list:
            names = ", ".join(
                f"{p['symbol']}" for p in peer_list if p.get("symbol")
            )
            lines.append(f"**Peer group ({len(peer_list)}):** {names}")
            lines.append("")

        comparisons = [c for c in peers.get("comparisons", []) if c.get("peer_median") is not None]
        if comparisons:
            lines.append("| Metric | Company | Peer Median | Position |")
            lines.append("|---|---|---|---|")
            for comparison in comparisons:
                company = comparison.get("company")
                # Margins read as percentages, multiples as plain numbers.
                is_margin = "margin" in comparison["key"]
                company_cell = (
                    (self._fp(company) if is_margin else self._fr(company))
                    if company is not None
                    else "N/A"
                )
                median_cell = (
                    self._fp(comparison["peer_median"])
                    if is_margin
                    else self._fr(comparison["peer_median"])
                )
                lines.append(
                    f"| **{comparison['label']}** | {company_cell} | {median_cell} | "
                    f"{comparison['verdict']} |"
                )
            lines.append("")

        sector = peers.get("sector") or {}
        sector_lines: list[str] = []
        for scope, label_key, default_label in (
            ("sector", "sector", "Sector"), ("industry", "industry", "Industry"),
        ):
            benchmark = sector.get(f"{scope}_pe")
            if benchmark is None:
                continue
            label = sector.get(label_key) or default_label
            phrase = self._relative_phrase(sector.get(f"vs_{scope}_pe"))
            sector_lines.append(
                f"- **{label} {scope} P/E:** {self._fr(benchmark)}{phrase}"
            )
        if sector_lines:
            lines.append("### Sector Benchmarks")
            lines.extend(sector_lines)
            if sector.get("as_of"):
                lines.append(f"\n*Snapshot as of {sector['as_of']}.*")
            lines.append("")

        if peers.get("summary"):
            lines.append(peers["summary"])

        return "\n".join(lines)

    def _section_financial_health(self, metrics: dict) -> str:
        groups = metrics.get("groups", {})
        lines = ["## Financial Health", ""]

        # Profitability
        lines.append("### Profitability")
        prof = groups.get("profitability", {})
        for label, key in [
            ("Gross Margin", "gross_margin"), ("Operating Margin", "operating_margin"),
            ("Net Margin", "net_margin"), ("ROE", "roe"),
            ("ROA", "roa"), ("ROIC", "roic"),
        ]:
            v = prof.get(key)
            lines.append(f"- **{label}:** {self._fp(v)}")

        # Liquidity
        lines.append("")
        lines.append("### Liquidity")
        liq = groups.get("liquidity", {})
        lines.append(f"- **Current Ratio:** {self._fr(liq.get('current_ratio'))}")
        lines.append(f"- **Quick Ratio:** {self._fr(liq.get('quick_ratio'))}")

        # Leverage
        lines.append("")
        lines.append("### Leverage")
        lev = groups.get("leverage", {})
        lines.append(f"- **Debt‑to‑Equity:** {self._fr(lev.get('de_ratio'))}")
        lines.append(f"- **Interest Coverage:** {self._fr(lev.get('interest_coverage'))}x")

        # Efficiency
        lines.append("")
        lines.append("### Efficiency")
        eff = groups.get("efficiency", {})
        lines.append(f"- **Asset Turnover:** {self._fr(eff.get('asset_turnover'))}")
        lines.append(f"- **Inventory Turnover:** {self._fr(eff.get('inventory_turnover'))}")

        return "\n".join(lines)

    def _section_growth(self, metrics: dict) -> str:
        groups = metrics.get("groups", {})
        growth = groups.get("growth", {})
        cf = groups.get("cash_flow", {})
        div = groups.get("dividends", {})

        lines = ["## Growth & Cash Flow", ""]

        lines.append("### Year‑over‑Year Growth")
        lines.append(f"- **Revenue Growth:** {self._fp(growth.get('revenue_growth'))}")
        lines.append(f"- **Net Income Growth:** {self._fp(growth.get('net_income_growth'))}")
        lines.append(f"- **EPS Growth:** {self._fp(growth.get('eps_growth'))}")

        # Three-year rates say more about the business than a single year that
        # one weak quarter or one-off charge can dominate.
        if any(growth.get(k) is not None for k in
               ("revenue_cagr_3y", "net_income_cagr_3y", "eps_cagr_3y")):
            lines.append("")
            lines.append("### Three‑Year Compound Growth")
            lines.append(f"- **Revenue CAGR:** {self._fp(growth.get('revenue_cagr_3y'))}")
            lines.append(f"- **Net Income CAGR:** {self._fp(growth.get('net_income_cagr_3y'))}")
            lines.append(f"- **EPS CAGR:** {self._fp(growth.get('eps_cagr_3y'))}")

        lines.append("")
        lines.append("### Cash Flow Quality")
        lines.append(f"- **FCF Yield:** {self._fp(cf.get('fcf_yield'))}")
        lines.append(f"- **FCF per Share:** {self._fc(cf.get('fcf_per_share'))}")
        lines.append(f"- **Operating CF / Net Income:** {self._fr(cf.get('ocf_to_net_income'))}")

        lines.append("")
        lines.append("### Dividends")
        lines.append(f"- **Dividend Yield:** {self._fp(div.get('dividend_yield'))}")
        lines.append(f"- **Payout Ratio:** {self._fp(div.get('payout_ratio'))}")

        return "\n".join(lines)

    def _section_technical(self, technical: dict) -> str:
        lines = ["## Technical Analysis", ""]

        # Moving averages
        ma = technical.get("moving_averages", {})
        lines.append("### Moving Averages")
        for label, key in [
            ("SMA 20", "sma_20"), ("SMA 50", "sma_50"), ("SMA 200", "sma_200"),
            ("EMA 12", "ema_12"), ("EMA 26", "ema_26"), ("EMA 50", "ema_50"),
        ]:
            v = ma.get(key)
            lines.append(f"- **{label}:** {self._fc(v)}")

        # Oscillators
        lines.append("")
        lines.append("### Oscillators & Momentum")
        lines.append(f"- **RSI (14):** {self._fr(technical.get('rsi'))}")
        macd = technical.get("macd", {})
        lines.append(f"- **MACD Line:** {self._fr(macd.get('macd_line'), 4)}")
        lines.append(f"- **Signal Line:** {self._fr(macd.get('signal_line'), 4)}")
        lines.append(f"- **MACD Histogram:** {self._fr(macd.get('macd_histogram'), 4)}")

        # Bollinger Bands
        bb = technical.get("bollinger_bands", {})
        lines.append("")
        lines.append("### Bollinger Bands (20, 2)")
        lines.append(f"- **Upper:** {self._fc(bb.get('bb_upper'))}")
        lines.append(f"- **Middle:** {self._fc(bb.get('bb_middle'))}")
        lines.append(f"- **Lower:** {self._fc(bb.get('bb_lower'))}")
        lines.append(f"- **Bandwidth:** {self._fp_raw(bb.get('bb_bandwidth'))}")

        # Support / Resistance
        sr = technical.get("support_resistance", {})
        lines.append("")
        lines.append("### Support & Resistance")
        lines.append(f"- **52‑Week High:** {self._fc(sr.get('resistance_52w'))}")
        lines.append(f"- **52‑Week Low:** {self._fc(sr.get('support_52w'))}")
        lines.append(f"- **20‑Day High:** {self._fc(sr.get('resistance_20d'))}")
        lines.append(f"- **20‑Day Low:** {self._fc(sr.get('support_20d'))}")

        # Momentum
        mom = technical.get("momentum", {})
        lines.append("")
        lines.append("### Price Momentum (Rate of Change)")
        lines.append(f"- **5‑Day:** {self._fp_raw(mom.get('roc_5d'))}")
        lines.append(f"- **20‑Day:** {self._fp_raw(mom.get('roc_20d'))}")
        lines.append(f"- **60‑Day:** {self._fp_raw(mom.get('roc_60d'))}")

        # ATR & Volume
        lines.append("")
        lines.append("### Volatility & Volume")
        lines.append(f"- **ATR (14):** {self._fc(technical.get('atr'))}")
        vol = technical.get("volume_profile", {})
        lines.append(f"- **Avg Volume (20d):** {self._fn(vol.get('avg_volume_20'))}")
        lines.append(f"- **Avg Volume (50d):** {self._fn(vol.get('avg_volume_50'))}")
        lines.append(f"- **Volume Trend:** {(vol.get('volume_trend', 'N/A')).replace('_', ' ').title()}")

        # Signals
        signals = technical.get("trend_signals", [])
        if signals:
            lines.append("")
            lines.append("### Key Signals")
            for sig in signals:
                lines.append(f"- {sig}")

        return "\n".join(lines)

    def _section_risk(self, risk: dict) -> str:
        lines = ["## Risk Assessment", ""]
        rating = risk.get("risk_rating", "unknown")
        lines.append(f"**Overall Risk Rating: {rating.replace('_', ' ').upper()}**")

        # State the measurement window — these statistics are meaningless
        # without knowing how much history they cover.
        if risk.get("window_start") and risk.get("window_end"):
            lines.append(
                f"*Measured over {risk.get('observations', 0)} trading sessions "
                f"({risk['window_start']} → {risk['window_end']}).*"
            )

        lines.append("")
        lines.append("### Volatility")
        lines.append(f"- **Annual Volatility:** {self._fp(risk.get('annual_volatility'))}")
        lines.append(f"- **Daily Volatility:** {self._fp(risk.get('daily_volatility'))}")
        beta_source = risk.get("beta_source")
        beta_suffix = f" ({beta_source})" if beta_source and beta_source != "unavailable" else ""
        lines.append(f"- **Beta:** {self._fr(risk.get('beta'), 3)}{beta_suffix}")

        lines.append("")
        lines.append("### Drawdown")
        lines.append(f"- **Max Drawdown:** {self._fp_raw(risk.get('max_drawdown_pct'))}")

        lines.append("")
        lines.append("### Risk‑Adjusted Returns")
        lines.append(f"- **Annualized Return:** {self._fp(risk.get('annualized_return'))}")
        lines.append(f"- **Sharpe Ratio:** {self._fr(risk.get('sharpe_ratio'), 3)}")
        lines.append(f"- **Sortino Ratio:** {self._fr(risk.get('sortino_ratio'), 3)}")
        lines.append(f"- **Return / Volatility:** {self._fr(risk.get('risk_adjusted_return'), 3)}")

        lines.append("")
        lines.append("### Value at Risk (Daily, 95% Confidence)")
        lines.append(f"- **Historical VaR:** {self._fp_raw(risk.get('var_historical_95'))}")
        lines.append(f"- **Parametric VaR:** {self._fp_raw(risk.get('var_parametric_95'))}")

        if risk.get("error"):
            lines.append(f"\n*Note: {risk['error']}*")

        return "\n".join(lines)

    def _section_sentiment(self, sentiment: dict) -> str:
        lines = ["## Market Sentiment", ""]

        avg = sentiment.get("average_sentiment_compound") or 0
        analyzed = sentiment.get("analyzed_articles_count", 0)
        positive = sentiment.get("positive_articles_count", 0)
        negative = sentiment.get("negative_articles_count", 0)
        neutral = sentiment.get("neutral_articles_count", 0)

        if avg > 0.05:
            mood = "Positive"
        elif avg < -0.05:
            mood = "Negative"
        else:
            mood = "Neutral"

        lines.append(f"- **Overall Mood:** {mood}")
        lines.append(f"- **Compound Score:** {self._fr(avg)} (recency‑weighted)")
        lines.append(f"- **Articles Analyzed:** {analyzed}")
        lines.append(f"- **Breakdown:** {positive} positive, {negative} negative, {neutral} neutral")

        excluded = (sentiment.get("excluded_irrelevant_count") or 0) + (
            sentiment.get("excluded_stale_count") or 0
        )
        if excluded:
            lines.append(f"- **Excluded:** {excluded} article(s) as off‑topic or stale")

        if sentiment.get("most_positive_headline"):
            lines.append(f"- **Most Positive:** *{sentiment['most_positive_headline']}*")
        if sentiment.get("most_negative_headline"):
            lines.append(f"- **Most Negative:** *{sentiment['most_negative_headline']}*")
        if sentiment.get("note"):
            lines.append(f"\n*{sentiment['note']}*")

        return "\n".join(lines)

    def _section_thesis(self, assessment: dict, valuation: dict,
                        current_price: Optional[Number], dcf_value: Optional[Number]) -> str:
        scored = [f for f in assessment.get("factors", []) if f.get("score") is not None]
        names = ", ".join(f["label"].lower() for f in scored) or "no scored factors"

        lines = ["## Investment Thesis", ""]
        lines.append(
            f"Weighing {names}, the composite score is "
            f"**{assessment['composite_score']:+.2f}**, giving a "
            f"**{assessment['recommendation'].upper()}** with "
            f"**{assessment['confidence']}% confidence** — {assessment['rationale']}."
        )
        if isinstance(current_price, (int, float)) and isinstance(dcf_value, (int, float)):
            diff_pct = ((dcf_value - current_price) / current_price) * 100
            direction = "upside" if diff_pct > 0 else "downside"
            sensitivity = valuation.get("sensitivity") or {}
            sentence = (
                f"\nAt a current price of {self._fc(current_price)}, the DCF estimates an "
                f"intrinsic value of {self._fc(dcf_value)}, implying "
                f"**{abs(diff_pct):.1f}% {direction}**"
            )
            if sensitivity.get("low") is not None and sensitivity.get("high") is not None:
                sentence += (
                    f" — though across the assumption grid the model spans "
                    f"{self._fc(sensitivity['low'])} to {self._fc(sensitivity['high'])}"
                )
            lines.append(sentence + ".")
        elif valuation.get("error"):
            lines.append(
                f"\nThe DCF could not be computed ({valuation['error'].rstrip('.')}), so the "
                "recommendation rests on the remaining factors."
            )
        return "\n".join(lines)

    # ── main entry point ──────────────────────────────────────

    def run(
        self,
        raw_data: dict,
        metrics: dict,
        sentiment: dict,
        valuation: dict,
        technical: dict,
        risk: dict,
        assessment: Optional[dict] = None,
        peers: Optional[dict] = None,
        earnings: Optional[dict] = None,
    ) -> str:
        """Generate the final comprehensive markdown report."""
        logger.info("Generating synthesis report")

        technical = technical or {}
        risk = risk or {}

        ticker = raw_data.get("ticker", "N/A").upper()
        profile = raw_data.get("profile") or {}
        prices = raw_data.get("prices", [])
        current_price = prices[0].get("close") if prices else None
        dcf_value = valuation.get("dcf_intrinsic_value_per_share")
        risk_rating = risk.get("risk_rating", "unknown")

        # The orchestrator scores the case so it can also persist the
        # scorecard; standalone callers get it computed here.
        if assessment is None:
            assessment = self.recommendation_engine.evaluate(
                metrics=metrics,
                valuation=valuation,
                technical=technical,
                risk=risk,
                sentiment=sentiment,
                current_price=current_price,
                peers=peers,
                earnings=earnings,
            )

        sections = [
            self._section_header(profile, ticker, current_price),
            self._section_executive_summary(
                assessment, risk_rating, current_price, dcf_value, metrics, technical,
            ),
            self._section_scorecard(assessment),
            self._section_valuation(valuation, metrics),
            self._section_peers(peers or {}),
            self._section_financial_health(metrics),
            self._section_growth(metrics),
            self._section_technical(technical),
            self._section_risk(risk),
            self._section_sentiment(sentiment),
            self._section_earnings(earnings or {}),
            self._section_thesis(assessment, valuation, current_price, dcf_value),
            (
                "\n---\n\n"
                "*Disclaimer: This report is generated by an automated AI system and is for "
                "informational purposes only. It does not constitute financial advice. "
                "Always conduct your own research and consult a licensed financial advisor "
                "before making investment decisions.*"
            ),
        ]

        report = "\n\n".join(sections)
        logger.info(
            "Synthesis report generated (%d characters, recommendation=%s, confidence=%d%%)",
            len(report), assessment["recommendation"], assessment["confidence"],
        )
        return report
