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
  7. Synthesis Report    → comprehensive markdown report
"""

import logging

from sqlalchemy.orm import Session

from .. import crud, models
from .data_gathering_agent import DataGatheringAgent
from .financial_metrics_agent import FinancialMetricsAgent
from .news_sentiment_agent import NewsSentimentAgent
from .risk_assessment_agent import RiskAssessmentAgent
from .synthesis_reporting_agent import SynthesisReportingAgent
from .technical_analysis_agent import TechnicalAnalysisAgent
from .valuation_agent import ValuationAgent

logger = logging.getLogger("stock_analyzer.orchestrator")


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
        self.synthesis_agent = SynthesisReportingAgent()

    def run_analysis(self, db: Session, job: models.AnalysisJob) -> None:
        """Execute the full analysis pipeline and persist results."""
        logger.info("Starting analysis pipeline for %s (job %d)", self.ticker, job.id)

        try:
            # ── Step 1: Gather raw data ──────────────────────
            crud.update_job_status(db, job_id=job.id, status="gathering_data")
            raw_data = self.data_agent.run(self.ticker)

            if not raw_data or not raw_data.get("profile"):
                raise ValueError(
                    f"Could not retrieve essential data for ticker '{self.ticker}'. "
                    "Verify the ticker symbol is correct."
                )

            # ── Step 2: Run analysis agents ──────────────────
            crud.update_job_status(db, job_id=job.id, status="analyzing")

            metrics = self.metrics_agent.run(raw_data)
            technical = self.technical_agent.run(raw_data)
            risk = self.risk_agent.run(raw_data)
            sentiment = self.sentiment_agent.run(raw_data.get("news", []))
            valuation = self.valuation_agent.run(raw_data)

            # ── Step 3: Synthesize the report ────────────────
            crud.update_job_status(db, job_id=job.id, status="generating_report")

            report_content = self.synthesis_agent.run(
                raw_data=raw_data,
                metrics=metrics,
                sentiment=sentiment,
                valuation=valuation,
                technical=technical,
                risk=risk,
            )

            # ── Step 4: Save & finalize ──────────────────────
            report = crud.create_report(db, content=report_content, job_id=job.id)
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
            crud.update_job_status(db, job_id=job.id, status="failed")
