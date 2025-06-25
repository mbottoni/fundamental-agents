from sqlalchemy.orm import Session
from .data_gathering_agent import DataGatheringAgent
from .financial_metrics_agent import FinancialMetricsAgent
from .news_sentiment_agent import NewsSentimentAgent
from .valuation_agent import ValuationAgent
from .synthesis_reporting_agent import SynthesisReportingAgent
from .. import crud, models

class Orchestrator:
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.data_gathering_agent = DataGatheringAgent()
        self.financial_metrics_agent = FinancialMetricsAgent()
        self.news_sentiment_agent = NewsSentimentAgent()
        self.valuation_agent = ValuationAgent()
        self.synthesis_reporting_agent = SynthesisReportingAgent()

    def run_analysis(self, db: Session, job: models.AnalysisJob):
        try:
            # Step 1: Gather raw data
            raw_data = self.data_gathering_agent.run(self.ticker)
            if not raw_data or not raw_data.get('profile'):
                raise ValueError("Could not retrieve essential data for the given ticker.")

            # Step 2: Run analysis agents
            metrics = self.financial_metrics_agent.run(raw_data)
            sentiment = self.news_sentiment_agent.run(raw_data.get('news', []))
            valuation = self.valuation_agent.run(raw_data)

            # Step 3: Synthesize the final report
            final_report_content = self.synthesis_reporting_agent.run(
                raw_data=raw_data,
                metrics=metrics,
                sentiment=sentiment,
                valuation=valuation
            )
            
            # Step 4: Save report to DB
            crud.create_report(db, content=final_report_content, job_id=job.id)
            
            # Step 5: Update job status to complete
            crud.update_job_status(db, job_id=job.id, status="complete")

        except Exception as e:
            # Update job status to failed
            crud.update_job_status(db, job_id=job.id, status="failed")
            # Optionally log the error e
            print(f"Analysis failed for ticker {self.ticker}: {e}") 