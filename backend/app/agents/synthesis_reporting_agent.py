import logging
from datetime import date
from typing import Any, Optional, Union

logger = logging.getLogger("stock_analyzer.agents.synthesis")

Number = Union[int, float]


class SynthesisReportingAgent:
    """Synthesizes analysis results into a formatted markdown report."""

    # Valuation thresholds for recommendations
    STRONG_BUY_THRESHOLD = 0.20
    BUY_THRESHOLD = 0.05
    SELL_THRESHOLD = -0.05
    STRONG_SELL_THRESHOLD = -0.20

    def _format_currency(self, value: Any) -> str:
        if isinstance(value, (int, float)):
            return f"${value:,.2f}"
        return "N/A"

    def _format_ratio(self, value: Any) -> str:
        if isinstance(value, (int, float)):
            return f"{value:.2f}"
        return "N/A"

    def _format_percentage(self, value: Any) -> str:
        if isinstance(value, (int, float)):
            return f"{value * 100:.2f}%"
        return "N/A"

    def _generate_conclusion(
        self, current_price: Optional[Number], dcf_value: Optional[Number]
    ) -> str:
        if not isinstance(current_price, (int, float)) or not isinstance(dcf_value, (int, float)):
            return "A conclusive investment thesis could not be determined due to insufficient data."

        diff = (dcf_value - current_price) / current_price

        if diff > self.STRONG_BUY_THRESHOLD:
            recommendation = "strong buy"
            rationale = f"the stock appears to be significantly undervalued by {diff:.0%}"
        elif diff > self.BUY_THRESHOLD:
            recommendation = "buy"
            rationale = f"the stock appears to be undervalued by {diff:.0%}"
        elif diff < self.STRONG_SELL_THRESHOLD:
            recommendation = "strong sell"
            rationale = f"the stock appears to be significantly overvalued by {-diff:.0%}"
        elif diff < self.SELL_THRESHOLD:
            recommendation = "sell"
            rationale = f"the stock appears to be overvalued by {-diff:.0%}"
        else:
            recommendation = "hold"
            rationale = "the stock appears to be fairly valued"

        return (
            f"Based on the DCF analysis, the recommendation is a **{recommendation}**. "
            f"At a current price of {self._format_currency(current_price)}, {rationale} "
            f"compared to its intrinsic value of {self._format_currency(dcf_value)}."
        )

    def run(
        self,
        raw_data: dict,
        metrics: dict,
        sentiment: dict,
        valuation: dict,
    ) -> str:
        """Generate the final markdown report from all analysis results."""
        logger.info("Generating synthesis report")

        ticker = raw_data.get("ticker", "N/A").upper()
        profile = raw_data.get("profile") or {}
        company_name = profile.get("companyName", "Unknown Company")
        prices = raw_data.get("prices", [])
        current_price = prices[0].get("close") if prices else None

        sections: list[str] = []

        # --- Header ---
        sections.append(f"# Financial Analysis Report: {company_name} ({ticker})")
        sections.append(f"**Date:** {date.today().strftime('%Y-%m-%d')}")
        sections.append(
            f"**Industry:** {profile.get('industry', 'N/A')} | "
            f"**Sector:** {profile.get('sector', 'N/A')}"
        )
        sections.append(f"**Current Stock Price:** {self._format_currency(current_price)}")

        # --- Valuation Summary ---
        sections.append("## Valuation Summary")
        dcf_value = valuation.get("dcf_intrinsic_value_per_share")
        sections.append(f"- **Intrinsic Value (DCF):** {self._format_currency(dcf_value)}")

        if isinstance(current_price, (int, float)) and isinstance(dcf_value, (int, float)):
            upside = ((dcf_value - current_price) / current_price) * 100
            sections.append(f"- **Upside/Downside:** {self._format_ratio(upside)}%")

        if valuation.get("wacc"):
            sections.append(f"- **WACC:** {self._format_percentage(valuation['wacc'])}")

        if valuation.get("error"):
            sections.append(f"- *Note: {valuation['error']}*")

        # --- Investment Thesis ---
        sections.append("## Investment Thesis")
        sections.append(self._generate_conclusion(current_price, dcf_value))

        # --- Key Financial Metrics ---
        sections.append("## Key Financial Metrics")
        sections.append(f"- **P/E Ratio:** {self._format_ratio(metrics.get('pe_ratio'))}")
        sections.append(f"- **Debt-to-Equity Ratio:** {self._format_ratio(metrics.get('de_ratio'))}")
        sections.append(f"- **Return on Equity (ROE):** {self._format_percentage(metrics.get('roe'))}")
        sections.append(f"- **Current Ratio:** {self._format_ratio(metrics.get('current_ratio'))}")

        # --- Market Sentiment ---
        sections.append("## Market Sentiment Analysis")
        avg_sentiment = sentiment.get("average_sentiment_compound", 0)
        sections.append(
            f"- **Average News Sentiment (Compound Score):** {self._format_ratio(avg_sentiment)}"
        )

        if avg_sentiment > 0.05:
            sentiment_summary = "Overall sentiment is positive."
        elif avg_sentiment < -0.05:
            sentiment_summary = "Overall sentiment is negative."
        else:
            sentiment_summary = "Overall sentiment is neutral."

        analyzed_count = sentiment.get("analyzed_articles_count", 0)
        sections.append(f"- **Summary:** {sentiment_summary} Based on {analyzed_count} recent news articles.")
        sections.append(
            f"- **Breakdown:** {sentiment.get('positive_articles_count', 0)} positive, "
            f"{sentiment.get('negative_articles_count', 0)} negative, "
            f"{sentiment.get('neutral_articles_count', 0)} neutral"
        )

        # --- Disclaimer ---
        sections.append(
            "\n---\n"
            "*Disclaimer: This report is generated by an automated AI system and is for "
            "informational purposes only. It does not constitute financial advice. "
            "Please conduct your own research before making any investment decisions.*"
        )

        report = "\n\n".join(sections)
        logger.info("Synthesis report generated (%d characters)", len(report))
        return report
