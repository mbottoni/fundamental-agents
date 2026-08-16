"""
Orchestrator
============
Coordinates the multi‑agent analysis pipeline:

  1. Data Gathering      → raw financial data, prices, profile, news
  2. Financial Metrics   → 30+ fundamental ratios & growth metrics
  3. Technical Analysis  → RSI, MACD, MAs, Bollinger, volume, momentum
  4. Risk Assessment     → volatility, Sharpe, Sortino, VaR, drawdown
  5. News Sentiment      → VADER compound scores on recent articles
  6. Valuation (DCF)     → intrinsic value per share
  7. Peer Comparison     → multiples against comparable companies and sector
  8. Recommendation      → weighted factor score → buy/hold/sell
  9. Synthesis Report    → comprehensive markdown report
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from .. import crud, models
from .data_gathering_agent import DataGatheringAgent
from .earnings_agent import EarningsAgent
from .financial_metrics_agent import FinancialMetricsAgent
from .news_sentiment_agent import NewsSentimentAgent
from .peer_comparison_agent import PeerComparisonAgent
from .recommendation import RecommendationEngine
from .risk_assessment_agent import RiskAssessmentAgent
from .synthesis_reporting_agent import SynthesisReportingAgent
from .technical_analysis_agent import TechnicalAnalysisAgent
from .valuation_agent import ValuationAgent

logger = logging.getLogger("stock_analyzer.orchestrator")

# Max price points to send to the frontend for charts
CHART_PRICE_LIMIT = 120


class DataUnavailableError(Exception):
    """Raised when the inputs an analysis needs could not be retrieved."""

class Orchestrator:
    """
    Coordinates the multi‑agent analysis pipeline.

    Pipeline stages update the job status in the database so the
    frontend can display real‑time progress.
    """

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker.upper()
        self.data_agent = DataGatheringAgent()
        self.metrics_agent = FinancialMetricsAgent()
        self.technical_agent = TechnicalAnalysisAgent()
        self.risk_agent = RiskAssessmentAgent()
        self.sentiment_agent = NewsSentimentAgent()
        self.valuation_agent = ValuationAgent()
        self.peer_agent = PeerComparisonAgent()
        self.earnings_agent = EarningsAgent()
        self.recommendation_engine = RecommendationEngine()
        self.synthesis_agent = SynthesisReportingAgent()

    def _build_chart_data(
        self,
        raw_data: dict,
        metrics: dict,
        technical: dict,
        risk: dict,
        sentiment: dict,
        valuation: dict,
        assessment: dict,
        peers: dict,
        earnings: dict,
    ) -> dict[str, Any]:
        """
        Build a structured dict for the frontend charting components.
        Keeps only the data needed for visualizations (not the full raw dump).
        """
        prices = raw_data.get("prices", [])
        profile = raw_data.get("profile") or {}

        # Price history (newest first → reverse for chronological charts)
        price_series = [
            {"date": p["date"], "close": p["close"], "high": p.get("high"), "low": p.get("low"), "volume": p.get("volume")}
            for p in prices[:CHART_PRICE_LIMIT]
            if p.get("date") and p.get("close")
        ]
        price_series.reverse()

        # Moving averages as overlay on the same chart
        ma = technical.get("moving_averages", {})

        # Bollinger bands
        bb = technical.get("bollinger_bands", {})

        # Build profitability bar chart data
        prof = metrics.get("groups", {}).get("profitability", {})
        profitability_bars = [
            {"name": "Gross Margin", "value": _pct(prof.get("gross_margin"))},
            {"name": "Op. Margin", "value": _pct(prof.get("operating_margin"))},
            {"name": "Net Margin", "value": _pct(prof.get("net_margin"))},
            {"name": "ROE", "value": _pct(prof.get("roe"))},
            {"name": "ROA", "value": _pct(prof.get("roa"))},
            {"name": "ROIC", "value": _pct(prof.get("roic"))},
        ]

        # Valuation comparison
        val = metrics.get("groups", {}).get("valuation", {})
        valuation_bars = [
            {"name": "P/E", "value": val.get("pe_ratio")},
            {"name": "P/B", "value": val.get("pb_ratio")},
            {"name": "P/S", "value": val.get("ps_ratio")},
            {"name": "EV/EBITDA", "value": val.get("ev_ebitda")},
            {"name": "PEG", "value": val.get("peg_ratio")},
        ]

        # Sentiment donut
        sentiment_donut = [
            {"name": "Positive", "value": sentiment.get("positive_articles_count", 0), "color": "#34d399"},
            {"name": "Neutral", "value": sentiment.get("neutral_articles_count", 0), "color": "#9ca3af"},
            {"name": "Negative", "value": sentiment.get("negative_articles_count", 0), "color": "#f87171"},
        ]

        # Growth bars
        growth = metrics.get("groups", {}).get("growth", {})
        growth_bars = [
            {"name": "Revenue", "value": _pct(growth.get("revenue_growth"))},
            {"name": "Net Income", "value": _pct(growth.get("net_income_growth"))},
            {"name": "EPS", "value": _pct(growth.get("eps_growth"))},
        ]

        return {
            "ticker": self.ticker,
            "company_name": profile.get("companyName", "Unknown"),
            "current_price": prices[0].get("close") if prices else None,
            "price_series": price_series,
            "moving_averages": {
                "sma_20": ma.get("sma_20"),
                "sma_50": ma.get("sma_50"),
                "sma_200": ma.get("sma_200"),
            },
            "bollinger_bands": bb,
            "rsi": technical.get("rsi"),
            "macd": technical.get("macd", {}),
            "atr": technical.get("atr"),
            "volume_profile": technical.get("volume_profile", {}),
            "momentum": technical.get("momentum", {}),
            "trend_signals": technical.get("trend_signals", []),
            "support_resistance": technical.get("support_resistance", {}),
            "profitability": profitability_bars,
            "valuation_multiples": valuation_bars,
            "sentiment": sentiment_donut,
            "sentiment_score": sentiment.get("average_sentiment_compound", 0),
            "growth": growth_bars,
            "risk": {
                "rating": risk.get("risk_rating", "unknown"),
                "annual_volatility": risk.get("annual_volatility"),
                "sharpe_ratio": risk.get("sharpe_ratio"),
                "sortino_ratio": risk.get("sortino_ratio"),
                "max_drawdown_pct": risk.get("max_drawdown_pct"),
                "beta": risk.get("beta"),
                "var_95": risk.get("var_historical_95"),
                "annualized_return": risk.get("annualized_return"),
                "window_start": risk.get("window_start"),
                "window_end": risk.get("window_end"),
            },
            "dcf": {
                "intrinsic_value": valuation.get("dcf_intrinsic_value_per_share"),
                "wacc": valuation.get("wacc"),
                "current_price": prices[0].get("close") if prices else None,
                "value_low": (valuation.get("sensitivity") or {}).get("low"),
                "value_high": (valuation.get("sensitivity") or {}).get("high"),
                "net_debt": valuation.get("net_debt"),
                "status": valuation.get("status"),
                "error": valuation.get("error"),
            },
            "liquidity": metrics.get("groups", {}).get("liquidity", {}),
            "leverage": metrics.get("groups", {}).get("leverage", {}),
            "revenue_segments": self._build_revenue_segments(raw_data),
            "dividend_history": self._build_dividend_history(raw_data),
            "peers": {
                "peer_count": peers.get("peer_count", 0),
                "companies": peers.get("peers", []),
                "comparisons": peers.get("comparisons", []),
                "sector": peers.get("sector", {}),
                "relative_valuation_score": peers.get("relative_valuation_score"),
                "summary": peers.get("summary"),
            },
            "earnings": earnings,
            "recommendation": {
                "call": assessment.get("recommendation"),
                "composite_score": assessment.get("composite_score"),
                "confidence": assessment.get("confidence"),
                "rationale": assessment.get("rationale"),
                "coverage": assessment.get("coverage"),
                "factors": assessment.get("factors", []),
            },
        }

    @staticmethod
    def _build_revenue_segments(raw_data: dict) -> dict:
        """Extract revenue segment data for pie/bar charts."""
        segments = raw_data.get("revenue_segments", {})
        result: dict[str, Any] = {"product": [], "geographic": []}

        # Product segments - FMP returns list of dicts per year
        product_data = segments.get("product", [])
        if product_data and isinstance(product_data, list) and len(product_data) > 0:
            latest = product_data[0] if isinstance(product_data[0], dict) else {}
            for k, v in latest.items():
                if k not in ("date", "symbol") and v is not None:
                    try:
                        result["product"].append({"name": k, "value": float(v)})
                    except (TypeError, ValueError):
                        pass

        # Geographic segments
        geo_data = segments.get("geographic", [])
        if geo_data and isinstance(geo_data, list) and len(geo_data) > 0:
            latest = geo_data[0] if isinstance(geo_data[0], dict) else {}
            for k, v in latest.items():
                if k not in ("date", "symbol") and v is not None:
                    try:
                        result["geographic"].append({"name": k, "value": float(v)})
                    except (TypeError, ValueError):
                        pass

        return result

    @staticmethod
    def _build_dividend_history(raw_data: dict) -> list[dict]:
        """Extract dividend history for charts."""
        divs = raw_data.get("dividend_history", [])
        return [
            {"date": d.get("date", ""), "dividend": d.get("dividend", 0)}
            for d in divs
            if d.get("date") and d.get("dividend")
        ]

    def run_analysis(self, db: Session, job: models.AnalysisJob) -> None:
        """Execute the full analysis pipeline and persist results."""
        logger.info("Starting analysis pipeline for %s (job %d)", self.ticker, job.id)

        try:
            # ── Step 1: Gather raw data ──────────────────────
            crud.update_job_status(db, job_id=job.id, status="gathering_data")
            raw_data = self.data_agent.run(self.ticker)

            if not raw_data or not raw_data.get("profile"):
                raise DataUnavailableError(
                    f"No company profile was returned for '{self.ticker}'. Check that the "
                    "ticker symbol is correct and listed on a supported exchange."
                )

            if not raw_data.get("prices"):
                raise DataUnavailableError(
                    f"No price history was returned for '{self.ticker}', so the technical "
                    "and risk analysis cannot run. This is usually a temporary data "
                    "provider issue — please try again shortly."
                )

            statements = raw_data.get("financials") or {}
            if not statements.get("income_statement"):
                raise DataUnavailableError(
                    f"No financial statements were returned for '{self.ticker}'. Funds, "
                    "ETFs and some foreign listings do not publish the statements this "
                    "analysis depends on."
                )

            # ── Step 2: Run analysis agents ──────────────────
            crud.update_job_status(db, job_id=job.id, status="analyzing")

            metrics = self.metrics_agent.run(raw_data)
            technical = self.technical_agent.run(raw_data)
            risk = self.risk_agent.run(raw_data)
            sentiment = self.sentiment_agent.run(
                raw_data.get("news", []),
                ticker=self.ticker,
                company_name=(raw_data.get("profile") or {}).get("companyName"),
            )
            valuation = self.valuation_agent.run(raw_data)
            peers = self.peer_agent.run(raw_data, metrics)
            earnings = self.earnings_agent.run(raw_data)

            # ── Step 3: Score the investment case ────────────
            prices = raw_data.get("prices") or []
            assessment = self.recommendation_engine.evaluate(
                metrics=metrics,
                valuation=valuation,
                technical=technical,
                risk=risk,
                sentiment=sentiment,
                current_price=prices[0].get("close") if prices else None,
                peers=peers,
                earnings=earnings,
            )

            # ── Step 4: Synthesize the report ────────────────
            crud.update_job_status(db, job_id=job.id, status="generating_report")

            report_content = self.synthesis_agent.run(
                raw_data=raw_data,
                metrics=metrics,
                sentiment=sentiment,
                valuation=valuation,
                technical=technical,
                risk=risk,
                assessment=assessment,
                peers=peers,
                earnings=earnings,
            )

            # ── Step 5: Build structured chart data ──────────
            chart_data = self._build_chart_data(
                raw_data, metrics, technical, risk, sentiment, valuation, assessment, peers,
                earnings,
            )

            # ── Step 5: Save & finalize ──────────────────────
            report = crud.create_report(
                db, content=report_content, job_id=job.id, chart_data=chart_data,
            )

            # A small structured record of the conclusion and the price it was
            # reached at. Neither the history view nor any assessment of past
            # calls can be reconstructed after the fact.
            try:
                crud.create_snapshot(
                    db,
                    user_id=job.user_id,
                    job_id=job.id,
                    ticker=self.ticker,
                    assessment=assessment,
                    price=prices[0].get("close") if prices else None,
                    dcf_value=valuation.get("dcf_intrinsic_value_per_share"),
                    risk_rating=risk.get("risk_rating"),
                )
            except Exception as e:  # noqa: BLE001 - never fail a finished report
                logger.error("Could not record snapshot for job %d: %s", job.id, e)

            crud.update_job_status(db, job_id=job.id, status="complete")

            logger.info(
                "Analysis pipeline complete for %s (job %d, report %d)",
                self.ticker, job.id, report.id,
            )

        except Exception as e:
            logger.error(
                "Analysis pipeline failed for %s (job %d): %s",
                self.ticker, job.id, e,
                exc_info=True,
            )
            crud.update_job_status(
                db, job_id=job.id, status="failed", error_message=self._failure_message(e),
            )

    def _failure_message(self, error: Exception) -> str:
        """
        Translate an exception into something the user can act on.

        A bare "failed" leaves no way to tell a mistyped ticker from an expired
        API key or a provider outage.
        """
        if isinstance(error, DataUnavailableError):
            return str(error)
        if isinstance(error, ValueError):
            return str(error)
        return (
            f"The analysis of {self.ticker} could not be completed due to an unexpected "
            "error. Please try again; if it keeps failing, the data provider may be "
            "unavailable."
        )


def _pct(v: Any) -> float | None:
    """Convert decimal ratio to percentage for chart display."""
    if v is not None:
        try:
            return round(float(v) * 100, 2)
        except (TypeError, ValueError):
            pass
    return None
