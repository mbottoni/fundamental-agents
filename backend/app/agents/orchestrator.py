import logging

from sqlalchemy.orm import Session

from .. import crud, models
from .data_gathering_agent import DataGatheringAgent
from .financial_metrics_agent import FinancialMetricsAgent
from .news_sentiment_agent import NewsSentimentAgent
from .synthesis_reporting_agent import SynthesisReportingAgent
from .valuation_agent import ValuationAgent

logger = logging.getLogger("stock_analyzer.orchestrator")


class Orchestrator:
    """
    Coordinates the multi-agent analysis pipeline.

    Pipeline:
    1. Data Gathering  -> raw financial data
    2. Financial Metrics -> P/E, D/E, ROE, etc.
    3. News Sentiment   -> sentiment scores
    4. Valuation (DCF)  -> intrinsic value
    5. Synthesis         -> final markdown report
    """

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker.upper()
        self.data_agent = DataGatheringAgent()
        self.metrics_agent = FinancialMetricsAgent()
        self.sentiment_agent = NewsSentimentAgent()
        self.valuation_agent = ValuationAgent()
        self.synthesis_agent = SynthesisReportingAgent()

    def run_analysis(self, db: Session, job: models.AnalysisJob) -> None:
        """Execute the full analysis pipeline and persist results."""
        logger.info("Starting analysis pipeline for %s (job %d)", self.ticker, job.id)

        try:
            # Step 1: Gather raw data
            crud.update_job_status(db, job_id=job.id, status="gathering_data")
            raw_data = self.data_agent.run(self.ticker)

            if not raw_data or not raw_data.get("profile"):
                raise ValueError(
                    f"Could not retrieve essential data for ticker '{self.ticker}'. "
                    "Verify the ticker symbol is correct."
                )

            # Step 2: Run analysis agents in sequence
            crud.update_job_status(db, job_id=job.id, status="analyzing")

            metrics = self.metrics_agent.run(raw_data)
            sentiment = self.sentiment_agent.run(raw_data.get("news", []))
            valuation = self.valuation_agent.run(raw_data)

            # Step 3: Synthesize the final report
            crud.update_job_status(db, job_id=job.id, status="generating_report")

            report_content = self.synthesis_agent.run(
                raw_data=raw_data,
                metrics=metrics,
                sentiment=sentiment,
                valuation=valuation,
            )

            # Step 4: Save report and update job status
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
