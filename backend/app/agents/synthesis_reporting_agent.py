import datetime

class SynthesisReportingAgent:
    def _format_currency(self, value):
        return f"${value:,.2f}" if isinstance(value, (int, float)) else "N/A"

    def _format_ratio(self, value):
        return f"{value:.2f}" if isinstance(value, (int, float)) else "N/A"

    def _generate_conclusion(self, current_price, dcf_value):
        if not isinstance(current_price, (int, float)) or not isinstance(dcf_value, (int, float)):
            return "A conclusive investment thesis could not be determined due to insufficient data."

        diff = (dcf_value - current_price) / current_price
        if diff > 0.20:
            recommendation = "strong buy"
            rationale = f"the stock appears to be significantly undervalued by {diff:.0%}"
        elif diff > 0.05:
            recommendation = "buy"
            rationale = f"the stock appears to be undervalued by {diff:.0%}"
        elif diff < -0.20:
            recommendation = "strong sell"
            rationale = f"the stock appears to be significantly overvalued by {-diff:.0%}"
        elif diff < -0.05:
            recommendation = "sell"
            rationale = f"the stock appears to be overvalued by {-diff:.0%}"
        else:
            recommendation = "hold"
            rationale = "the stock appears to be fairly valued"
        
        return f"Based on the DCF analysis, the recommendation is a **{recommendation}**. At a current price of {self._format_currency(current_price)}, {rationale} compared to its intrinsic value of {self._format_currency(dcf_value)}."

    def run(self, raw_data: dict, metrics: dict, sentiment: dict, valuation: dict):
        report_parts = []
        
        ticker = raw_data.get('ticker', 'N/A').upper()
        profile = raw_data.get('profile', {})
        company_name = profile.get('companyName', 'Unknown Company')
        current_price = raw_data.get('prices', [{}])[0].get('close')
        
        # --- Header ---
        report_parts.append(f"# Financial Analysis Report: {company_name} ({ticker})")
        report_parts.append(f"**Date:** {datetime.date.today().strftime('%Y-%m-%d')}")
        report_parts.append(f"**Industry:** {profile.get('industry', 'N/A')} | **Sector:** {profile.get('sector', 'N/A')}")
        report_parts.append(f"**Current Stock Price:** {self._format_currency(current_price)}")
        
        # --- Valuation Summary ---
        report_parts.append("## Valuation Summary")
        dcf_value = valuation.get('dcf_intrinsic_value_per_share')
        report_parts.append(f"- **Intrinsic Value (DCF):** {self._format_currency(dcf_value)}")
        if isinstance(current_price, (int, float)) and isinstance(dcf_value, (int, float)):
            premium_discount = ((dcf_value - current_price) / current_price) * 100
            report_parts.append(f"- **Upside/Downside:** {self._format_ratio(premium_discount)}%")
        
        # --- Investment Thesis ---
        report_parts.append("## Investment Thesis")
        conclusion = self._generate_conclusion(current_price, dcf_value)
        report_parts.append(conclusion)
        
        # --- Key Financial Metrics ---
        report_parts.append("## Key Financial Metrics")
        pe_ratio = metrics.get('pe_ratio')
        de_ratio = metrics.get('de_ratio')
        report_parts.append(f"- **P/E Ratio:** {self._format_ratio(pe_ratio)}")
        report_parts.append(f"- **Debt-to-Equity Ratio:** {self._format_ratio(de_ratio)}")
        
        # --- Market Sentiment ---
        report_parts.append("## Market Sentiment Analysis")
        avg_sentiment = sentiment.get('average_sentiment_compound', 0)
        report_parts.append(f"- **Average News Sentiment (Compound Score):** {self._format_ratio(avg_sentiment)}")
        if avg_sentiment > 0.05:
            sentiment_summary = "Overall sentiment is positive."
        elif avg_sentiment < -0.05:
            sentiment_summary = "Overall sentiment is negative."
        else:
            sentiment_summary = "Overall sentiment is neutral."
        report_parts.append(f"- **Summary:** {sentiment_summary} Based on {sentiment.get('analyzed_articles_count', 0)} recent news articles.")

        # --- Disclaimer ---
        report_parts.append("\n---\n*Disclaimer: This report is generated by an automated AI system and is for informational purposes only. It does not constitute financial advice. Please conduct your own research before making any investment decisions.*")

        return "\n\n".join(report_parts) 