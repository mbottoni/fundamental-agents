"""
Synthesis Reporting Agent
=========================
Combines outputs from all analysis agents into a professional
markdown report. The report intentionally duplicates key numbers
from the structured ``chart_data`` so the reader can understand
the report even without the visual charts.
"""

import logging
from datetime import date
from typing import Any, Optional, Union

logger = logging.getLogger("stock_analyzer.agents.synthesis")

Number = Union[int, float]


class SynthesisReportingAgent:
    """Synthesizes all agent results into a comprehensive markdown report."""

    # ── formatting helpers ─────────────────────────────────────

    @staticmethod
    def _fc(v: Any) -> str:
        """Format currency."""
        if isinstance(v, (int, float)):
            return f"${v:,.2f}"
        return "N/A"

    @staticmethod
    def _fr(v: Any, decimals: int = 2) -> str:
        """Format ratio."""
        if isinstance(v, (int, float)):
            return f"{v:.{decimals}f}"
        return "N/A"

    @staticmethod
    def _fp(v: Any) -> str:
        """Format percentage from decimal (0.25 → 25.00%)."""
        if isinstance(v, (int, float)):
            return f"{v * 100:.2f}%"
        return "N/A"

    @staticmethod
    def _fp_raw(v: Any) -> str:
        """Format value that is already a percentage."""
        if isinstance(v, (int, float)):
            return f"{v:.2f}%"
        return "N/A"

    @staticmethod
    def _fn(v: Any) -> str:
        """Format large numbers with abbreviation."""
        if not isinstance(v, (int, float)):
            return "N/A"
        v = float(v)
        for unit, thresh in [("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)]:
            if abs(v) >= thresh:
                return f"${v / thresh:,.2f}{unit}"
        return f"${v:,.0f}"

    # ── recommendation engine ──────────────────────────────────

    def _generate_recommendation(
        self,
        current_price: Optional[Number],
        dcf_value: Optional[Number],
        risk: dict,
        technical: dict,
    ) -> tuple[str, str, int]:
        """Return (recommendation, rationale, confidence_score)."""
        base_confidence = 50
        signals: list[str] = []

        # DCF valuation signal
        if isinstance(current_price, (int, float)) and isinstance(dcf_value, (int, float)) and current_price > 0:
            diff_pct = ((dcf_value - current_price) / current_price)
            if diff_pct > 0.20:
                rec = "Strong Buy"
                signals.append(f"significantly undervalued by {diff_pct:.0%}")
                base_confidence += 20
            elif diff_pct > 0.05:
                rec = "Buy"
                signals.append(f"undervalued by {diff_pct:.0%}")
                base_confidence += 10
            elif diff_pct < -0.20:
                rec = "Strong Sell"
                signals.append(f"significantly overvalued by {-diff_pct:.0%}")
                base_confidence += 15
            elif diff_pct < -0.05:
                rec = "Sell"
                signals.append(f"overvalued by {-diff_pct:.0%}")
                base_confidence += 5
            else:
                rec = "Hold"
                signals.append("fairly valued")
        else:
            rec = "Hold"
            signals.append("insufficient valuation data")

        # Risk adjustment
        risk_rating = risk.get("risk_rating", "unknown")
        if risk_rating in ("very_high", "high"):
            base_confidence -= 10
            signals.append(f"{risk_rating.replace('_', ' ')} risk profile")
        elif risk_rating == "low":
            base_confidence += 5

        # Technical signals boost
        trend_signals = technical.get("trend_signals", [])
        bullish = sum(1 for s in trend_signals if "bullish" in s.lower())
        bearish = sum(1 for s in trend_signals if "bearish" in s.lower())
        if bullish > bearish:
            base_confidence += 5
            signals.append(f"{bullish} bullish technical signals")
        elif bearish > bullish:
            base_confidence -= 5
            signals.append(f"{bearish} bearish technical signals")

        confidence = max(10, min(95, base_confidence))
        rationale = "; ".join(signals)
        return rec, rationale, confidence

    # ── report builder ─────────────────────────────────────────

    def run(
        self,
        raw_data: dict,
        metrics: dict,
        sentiment: dict,
        valuation: dict,
        technical: dict | None = None,
        risk: dict | None = None,
    ) -> str:
        """Generate the final markdown report."""
        logger.info("Generating synthesis report")

        technical = technical or {}
        risk = risk or {}

        ticker = raw_data.get("ticker", "N/A").upper()
        profile = raw_data.get("profile") or {}
        company_name = profile.get("companyName", "Unknown Company")
        prices = raw_data.get("prices", [])
        current_price = prices[0].get("close") if prices else None
        dcf_value = valuation.get("dcf_intrinsic_value_per_share")

        groups = metrics.get("groups", {})
        val_m = groups.get("valuation", {})
        prof_m = groups.get("profitability", {})
        liq_m = groups.get("liquidity", {})
        lev_m = groups.get("leverage", {})
        eff_m = groups.get("efficiency", {})
        growth_m = groups.get("growth", {})
        cf_m = groups.get("cash_flow", {})
        div_m = groups.get("dividends", {})

        ma = technical.get("moving_averages", {})
        rsi = technical.get("rsi")
        macd = technical.get("macd", {})
        bb = technical.get("bollinger_bands", {})
        sr = technical.get("support_resistance", {})
        momentum = technical.get("momentum", {})

        rec, rationale, confidence = self._generate_recommendation(
            current_price, dcf_value, risk, technical,
        )

        S: list[str] = []

        # ── Header ──
        S.append(f"# {company_name} ({ticker}) — Analysis Report")
        S.append(f"**Date:** {date.today().strftime('%B %d, %Y')}")
        S.append(
            f"**Sector:** {profile.get('sector', 'N/A')} — "
            f"**Industry:** {profile.get('industry', 'N/A')}"
        )

        # ── Executive Summary ──
        S.append("## Executive Summary")
        S.append(
            f"Current price: **{self._fc(current_price)}** | "
            f"DCF Intrinsic Value: **{self._fc(dcf_value)}** | "
            f"Recommendation: **{rec}** (confidence {confidence}%)"
        )
        S.append(f"\n*{rationale.capitalize()}.*")

        # ── Valuation Analysis ──
        S.append("## Valuation Analysis")
        if isinstance(current_price, (int, float)) and isinstance(dcf_value, (int, float)) and current_price > 0:
            upside = ((dcf_value - current_price) / current_price) * 100
            S.append(f"- **Upside / Downside:** {upside:+.1f}%")
        if valuation.get("wacc"):
            S.append(f"- **WACC:** {self._fp(valuation['wacc'])}")
        if valuation.get("error"):
            S.append(f"- *Note: {valuation['error']}*")

        S.append("\n**Valuation Multiples:**")
        S.append(f"| Metric | Value |")
        S.append(f"|--------|-------|")
        S.append(f"| P/E Ratio | {self._fr(val_m.get('pe_ratio'))} |")
        S.append(f"| P/B Ratio | {self._fr(val_m.get('pb_ratio'))} |")
        S.append(f"| P/S Ratio | {self._fr(val_m.get('ps_ratio'))} |")
        S.append(f"| EV/EBITDA | {self._fr(val_m.get('ev_ebitda'))} |")
        S.append(f"| PEG Ratio | {self._fr(val_m.get('peg_ratio'))} |")

        # ── Financial Health ──
        S.append("## Financial Health")
        S.append("### Profitability")
        S.append(f"| Metric | Value |")
        S.append(f"|--------|-------|")
        S.append(f"| Gross Margin | {self._fp(prof_m.get('gross_margin'))} |")
        S.append(f"| Operating Margin | {self._fp(prof_m.get('operating_margin'))} |")
        S.append(f"| Net Margin | {self._fp(prof_m.get('net_margin'))} |")
        S.append(f"| ROE | {self._fp(prof_m.get('roe'))} |")
        S.append(f"| ROA | {self._fp(prof_m.get('roa'))} |")
        S.append(f"| ROIC | {self._fp(prof_m.get('roic'))} |")

        S.append("### Liquidity & Leverage")
        S.append(f"| Metric | Value |")
        S.append(f"|--------|-------|")
        S.append(f"| Current Ratio | {self._fr(liq_m.get('current_ratio'))} |")
        S.append(f"| Quick Ratio | {self._fr(liq_m.get('quick_ratio'))} |")
        S.append(f"| Debt/Equity | {self._fr(lev_m.get('de_ratio'))} |")
        S.append(f"| Interest Coverage | {self._fr(lev_m.get('interest_coverage'))} |")

        S.append("### Efficiency")
        S.append(f"- **Asset Turnover:** {self._fr(eff_m.get('asset_turnover'))}")
        S.append(f"- **Inventory Turnover:** {self._fr(eff_m.get('inventory_turnover'))}")

        # ── Growth & Cash Flow ──
        S.append("## Growth & Cash Flow")
        S.append(f"| Metric | Value |")
        S.append(f"|--------|-------|")
        S.append(f"| Revenue Growth (YoY) | {self._fp(growth_m.get('revenue_growth'))} |")
        S.append(f"| Net Income Growth | {self._fp(growth_m.get('net_income_growth'))} |")
        S.append(f"| EPS Growth | {self._fp(growth_m.get('eps_growth'))} |")
        S.append(f"| FCF Yield | {self._fp(cf_m.get('fcf_yield'))} |")
        S.append(f"| FCF / Share | {self._fc(cf_m.get('fcf_per_share'))} |")
        S.append(f"| OCF / Net Income | {self._fr(cf_m.get('ocf_to_net_income'))} |")
        if div_m.get("dividend_yield"):
            S.append(f"| Dividend Yield | {self._fp(div_m.get('dividend_yield'))} |")
            S.append(f"| Payout Ratio | {self._fr(div_m.get('payout_ratio'))} |")

        # ── Technical Analysis ──
        S.append("## Technical Analysis")
        S.append("### Moving Averages & Trend")
        S.append(f"- SMA 20: {self._fc(ma.get('sma_20'))} | SMA 50: {self._fc(ma.get('sma_50'))} | SMA 200: {self._fc(ma.get('sma_200'))}")
        S.append(f"- EMA 12: {self._fc(ma.get('ema_12'))} | EMA 26: {self._fc(ma.get('ema_26'))}")

        S.append("### Oscillators")
        S.append(f"- **RSI (14):** {self._fr(rsi)}")
        S.append(f"- **MACD:** {self._fr(macd.get('macd_line'), 4)} | Signal: {self._fr(macd.get('signal_line'), 4)} | Histogram: {self._fr(macd.get('macd_histogram'), 4)}")

        S.append("### Bollinger Bands")
        S.append(f"- Upper: {self._fc(bb.get('bb_upper'))} | Middle: {self._fc(bb.get('bb_middle'))} | Lower: {self._fc(bb.get('bb_lower'))}")
        S.append(f"- Bandwidth: {self._fp_raw(bb.get('bb_bandwidth'))}")

        if technical.get("atr"):
            S.append(f"- **ATR (14):** {self._fc(technical['atr'])}")

        S.append("### Support & Resistance")
        S.append(f"- 52-Week High: {self._fc(sr.get('resistance_52w'))} | Low: {self._fc(sr.get('support_52w'))}")
        S.append(f"- 20-Day High: {self._fc(sr.get('resistance_20d'))} | Low: {self._fc(sr.get('support_20d'))}")

        S.append("### Momentum")
        S.append(f"- 5-Day ROC: {self._fp_raw(momentum.get('roc_5d'))} | 20-Day: {self._fp_raw(momentum.get('roc_20d'))} | 60-Day: {self._fp_raw(momentum.get('roc_60d'))}")

        trend_signals = technical.get("trend_signals", [])
        if trend_signals:
            S.append("\n**Trend Signals:**")
            for sig in trend_signals:
                S.append(f"- {sig}")

        # ── Risk Assessment ──
        S.append("## Risk Assessment")
        rating = risk.get("risk_rating", "unknown").replace("_", " ").title()
        S.append(f"**Overall Risk Rating: {rating}**")
        S.append(f"| Metric | Value |")
        S.append(f"|--------|-------|")
        S.append(f"| Annual Volatility | {self._fp_raw(risk.get('annual_volatility', 0) * 100 if risk.get('annual_volatility') else None)} |")
        S.append(f"| Sharpe Ratio | {self._fr(risk.get('sharpe_ratio'), 3)} |")
        S.append(f"| Sortino Ratio | {self._fr(risk.get('sortino_ratio'), 3)} |")
        S.append(f"| Max Drawdown | {self._fp_raw(risk.get('max_drawdown_pct'))} |")
        S.append(f"| Beta | {self._fr(risk.get('beta'), 3)} |")
        S.append(f"| VaR (95%, Daily) | {self._fp_raw(risk.get('var_historical_95'))} |")

        # ── Market Sentiment ──
        S.append("## Market Sentiment")
        avg_sent = sentiment.get("average_sentiment_compound", 0)
        if avg_sent > 0.05:
            sent_label = "Positive"
        elif avg_sent < -0.05:
            sent_label = "Negative"
        else:
            sent_label = "Neutral"

        S.append(f"**Overall Sentiment: {sent_label}** (compound score: {self._fr(avg_sent, 3)})")
        analyzed = sentiment.get("analyzed_articles_count", 0)
        pos = sentiment.get("positive_articles_count", 0)
        neg = sentiment.get("negative_articles_count", 0)
        neu = sentiment.get("neutral_articles_count", 0)
        S.append(f"- Analyzed **{analyzed}** recent news articles")
        S.append(f"- {pos} positive | {neu} neutral | {neg} negative")

        # ── Investment Thesis ──
        S.append("## Investment Thesis & Recommendation")
        S.append(f"### Recommendation: {rec}")
        S.append(f"**Confidence Score: {confidence}%**")
        S.append(f"\n{rationale.capitalize()}.")

        # ── Disclaimer ──
        S.append("\n---")
        S.append(
            "*Disclaimer: This report is generated by an automated AI system and is for "
            "informational purposes only. It does not constitute financial advice. "
            "Always conduct your own due diligence before making investment decisions.*"
        )

        report = "\n\n".join(S)
        logger.info("Synthesis report generated (%d chars, %d sections)", len(report), len(S))
        return report
