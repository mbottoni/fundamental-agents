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

logger = logging.getLogger("stock_analyzer.agents.synthesis")

Number = Union[int, float]


class SynthesisReportingAgent:
    """Synthesizes all analysis results into a formatted markdown report."""

    # ── formatting helpers ─────────────────────────────────────

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

    # ── conclusion logic ──────────────────────────────────────

    def _generate_recommendation(
        self,
        current_price: Optional[Number],
        dcf_value: Optional[Number],
        risk_rating: str,
        rsi: Optional[float],
        trend_signals: list[str],
    ) -> tuple[str, str, int]:
        """
        Returns (recommendation, rationale, confidence_score 1-100).
        """
        # Start with valuation‑based recommendation
        if not isinstance(current_price, (int, float)) or not isinstance(dcf_value, (int, float)):
            return (
                "hold",
                "Insufficient data for a conclusive valuation‑based recommendation.",
                30,
            )

        diff = (dcf_value - current_price) / current_price
        confidence = 50

        if diff > self.STRONG_BUY_THRESHOLD:
            rec, reason = "strong buy", f"significantly undervalued by {diff:.0%}"
            confidence = 75
        elif diff > self.BUY_THRESHOLD:
            rec, reason = "buy", f"undervalued by {diff:.0%}"
            confidence = 65
        elif diff < self.STRONG_SELL_THRESHOLD:
            rec, reason = "strong sell", f"significantly overvalued by {-diff:.0%}"
            confidence = 75
        elif diff < self.SELL_THRESHOLD:
            rec, reason = "sell", f"overvalued by {-diff:.0%}"
            confidence = 65
        else:
            rec, reason = "hold", "fairly valued"
            confidence = 55

        # Adjust confidence based on risk and technicals
        if risk_rating == "very_high":
            confidence -= 15
        elif risk_rating == "high":
            confidence -= 10

        bullish_signals = sum(1 for s in trend_signals if "bullish" in s.lower())
        bearish_signals = sum(1 for s in trend_signals if "bearish" in s.lower())
        if rec in ("buy", "strong buy") and bullish_signals > bearish_signals:
            confidence += 10
        elif rec in ("sell", "strong sell") and bearish_signals > bullish_signals:
            confidence += 10
        elif rec in ("buy", "strong buy") and bearish_signals > bullish_signals:
            confidence -= 10

        if rsi is not None:
            if rsi > 70 and rec in ("buy", "strong buy"):
                confidence -= 10  # overbought contradicts buy
            elif rsi < 30 and rec in ("sell", "strong sell"):
                confidence -= 10  # oversold contradicts sell

        confidence = max(10, min(confidence, 95))

        return rec, reason, confidence

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
        self, rec: str, reason: str, confidence: int, risk_rating: str,
        current_price: Optional[Number], dcf_value: Optional[Number],
        metrics: dict, technical: dict,
    ) -> str:
        lines = ["## Executive Summary", ""]
        lines.append(
            f"**Recommendation: {rec.upper()}** (Confidence: {confidence}%)"
        )
        lines.append(f"- **Valuation:** The stock appears to be {reason}.")
        lines.append(f"- **Risk Level:** {risk_rating.replace('_', ' ').title()}")

        rsi = technical.get("rsi")
        if rsi is not None:
            lines.append(f"- **RSI:** {self._fr(rsi)} ({'overbought' if rsi > 70 else 'oversold' if rsi < 30 else 'neutral'})")

        pe = metrics.get("pe_ratio")
        if pe is not None:
            lines.append(f"- **P/E Ratio:** {self._fr(pe)}")

        return "\n".join(lines)

    def _section_valuation(self, valuation: dict, metrics: dict) -> str:
        lines = ["## Valuation Analysis", ""]

        dcf = valuation.get("dcf_intrinsic_value_per_share")
        wacc = valuation.get("wacc")
        lines.append("### DCF Model")
        lines.append(f"- **Intrinsic Value (DCF):** {self._fc(dcf)}")
        if wacc:
            lines.append(f"- **WACC:** {self._fp(wacc)}")
        if valuation.get("latest_fcf"):
            lines.append(f"- **Latest Free Cash Flow:** {self._fc(valuation['latest_fcf'])}")
        if valuation.get("error"):
            lines.append(f"- *Note: {valuation['error']}*")

        lines.append("")
        lines.append("### Relative Valuation (Multiples)")

        val_group = metrics.get("groups", {}).get("valuation", {})
        for label, key in [
            ("P/E Ratio", "pe_ratio"), ("P/B Ratio", "pb_ratio"),
            ("P/S Ratio", "ps_ratio"), ("EV/EBITDA", "ev_ebitda"),
            ("PEG Ratio", "peg_ratio"),
        ]:
            v = val_group.get(key) or metrics.get(key)
            lines.append(f"- **{label}:** {self._fr(v)}")

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

        lines.append("")
        lines.append("### Volatility")
        lines.append(f"- **Annual Volatility:** {self._fp(risk.get('annual_volatility'))}")
        lines.append(f"- **Daily Volatility:** {self._fp(risk.get('daily_volatility'))}")
        lines.append(f"- **Beta:** {self._fr(risk.get('beta'), 3)}")

        lines.append("")
        lines.append("### Drawdown")
        lines.append(f"- **Max Drawdown:** {self._fp_raw(risk.get('max_drawdown_pct'))}")

        lines.append("")
        lines.append("### Risk‑Adjusted Returns")
        lines.append(f"- **Sharpe Ratio:** {self._fr(risk.get('sharpe_ratio'), 3)}")
        lines.append(f"- **Sortino Ratio:** {self._fr(risk.get('sortino_ratio'), 3)}")
        lines.append(f"- **Risk‑Adjusted Return:** {self._fr(risk.get('risk_adjusted_return'), 3)}")

        lines.append("")
        lines.append("### Value at Risk (Daily, 95% Confidence)")
        lines.append(f"- **Historical VaR:** {self._fp_raw(risk.get('var_historical_95'))}")
        lines.append(f"- **Parametric VaR:** {self._fp_raw(risk.get('var_parametric_95'))}")

        if risk.get("error"):
            lines.append(f"\n*Note: {risk['error']}*")

        return "\n".join(lines)

    def _section_sentiment(self, sentiment: dict) -> str:
        lines = ["## Market Sentiment", ""]

        avg = sentiment.get("average_sentiment_compound", 0)
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
        lines.append(f"- **Compound Score:** {self._fr(avg)}")
        lines.append(f"- **Articles Analyzed:** {analyzed}")
        lines.append(f"- **Breakdown:** {positive} positive, {negative} negative, {neutral} neutral")

        return "\n".join(lines)

    def _section_thesis(self, rec: str, reason: str, confidence: int,
                        current_price: Optional[Number], dcf_value: Optional[Number]) -> str:
        lines = ["## Investment Thesis", ""]
        lines.append(
            f"Based on a comprehensive analysis combining DCF valuation, relative multiples, "
            f"technical indicators, risk metrics, and news sentiment, the recommendation is "
            f"a **{rec.upper()}** with **{confidence}% confidence**."
        )
        if isinstance(current_price, (int, float)) and isinstance(dcf_value, (int, float)):
            diff_pct = ((dcf_value - current_price) / current_price) * 100
            direction = "upside" if diff_pct > 0 else "downside"
            lines.append(
                f"\nAt a current price of {self._fc(current_price)}, the DCF model estimates "
                f"an intrinsic value of {self._fc(dcf_value)}, implying **{abs(diff_pct):.1f}% {direction}** potential."
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
        rsi = technical.get("rsi")
        trend_signals = technical.get("trend_signals", [])

        rec, reason, confidence = self._generate_recommendation(
            current_price, dcf_value, risk_rating, rsi, trend_signals,
        )

        sections = [
            self._section_header(profile, ticker, current_price),
            self._section_executive_summary(rec, reason, confidence, risk_rating, current_price, dcf_value, metrics, technical),
            self._section_valuation(valuation, metrics),
            self._section_financial_health(metrics),
            self._section_growth(metrics),
            self._section_technical(technical),
            self._section_risk(risk),
            self._section_sentiment(sentiment),
            self._section_thesis(rec, reason, confidence, current_price, dcf_value),
            (
                "\n---\n\n"
                "*Disclaimer: This report is generated by an automated AI system and is for "
                "informational purposes only. It does not constitute financial advice. "
                "Always conduct your own research and consult a licensed financial advisor "
                "before making investment decisions.*"
            ),
        ]

        report = "\n\n".join(sections)
        logger.info("Synthesis report generated (%d characters, recommendation=%s, confidence=%d%%)",
                     len(report), rec, confidence)
        return report
