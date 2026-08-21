"""
Analysis worker
===============
Claims queued analyses and runs the pipeline.

Runs either as its own process (`python -m app.worker`, which is what the
production stack does) or inside the API process as a background task
(`ANALYSIS_WORKER_INLINE=true`, the default for local development so that
`make up` still needs only one container).

Only the separate process survives a deploy: an inline worker dies with the API
it lives in. Its jobs are not lost either way — the lease expires and whichever
worker comes up next reclaims them — but a standalone worker keeps working
through an API restart instead of stopping.

Concurrency is capped at ANALYSIS_WORKER_CONCURRENCY. That cap is the point:
each analysis fans out around eleven provider requests, so unbounded parallelism
walks straight into the provider's rate limit and the daily quota.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from .agents.orchestrator import Orchestrator
from .core.config import logger as root_logger, settings
from .core.db import SessionLocal
from .services import job_queue

logger = logging.getLogger("stock_analyzer.worker")


def _run_one(job_id: int, ticker: str) -> None:
    """
    Run a single analysis to completion.

    Each job gets its own session: this runs on a worker thread, and a Session
    is not safe to share across threads.
    """
    db = SessionLocal()
    stop_heartbeat = threading.Event()

    def beat() -> None:
        """
        Keep the lease alive while the pipeline runs.

        A full analysis can outlast the lease, and without this it would look
        abandoned and be picked up a second time while still running.
        """
        hb = SessionLocal()
        try:
            while not stop_heartbeat.wait(settings.ANALYSIS_LEASE_SECONDS / 3):
                try:
                    job_queue.heartbeat(hb, job_id)
                except Exception as e:  # noqa: BLE001 - a missed beat is not fatal
                    logger.warning("Heartbeat failed for job %d: %s", job_id, e)
        finally:
            hb.close()

    heartbeat_thread = threading.Thread(
        target=beat, name=f"heartbeat-{job_id}", daemon=True
    )
    heartbeat_thread.start()

    try:
        from . import crud

        job = crud.get_analysis_job(db, job_id)
        if job is None:
            logger.error("Claimed job %d vanished before it could run", job_id)
            return

        Orchestrator(ticker).run_analysis(db=db, job=job)

        db.refresh(job)
        if job.status == "failed":
            # The orchestrator records a user-facing reason and stops. Retrying
            # is still worthwhile: most of its failures are provider timeouts.
            requeued = job_queue.requeue_or_fail(
                db, job_id, job.error_message or "The analysis could not be completed."
            )
            if not requeued:
                logger.info("Job %d finished as failed", job_id)
        else:
            job_queue.release(db, job_id)
    except Exception as e:  # noqa: BLE001 - one bad job must not stop the worker
        logger.error("Job %d raised: %s", job_id, e, exc_info=True)
        try:
            job_queue.requeue_or_fail(
                db,
                job_id,
                f"The analysis of {ticker} could not be completed. Please try again.",
            )
        except Exception:  # noqa: BLE001
            logger.error("Could not record the outcome of job %d", job_id)
    finally:
        stop_heartbeat.set()
        db.close()


class Worker:
    """Polls the queue and runs what it finds, up to a fixed concurrency."""

    def __init__(self, concurrency: Optional[int] = None) -> None:
        self.concurrency = concurrency or settings.ANALYSIS_WORKER_CONCURRENCY
        self.worker_id = job_queue.worker_identity()
        self._stop = threading.Event()
        self._in_flight = 0
        self._lock = threading.Lock()

    def stop(self) -> None:
        self._stop.set()

    def _finished(self, _future) -> None:
        with self._lock:
            self._in_flight -= 1

    def _has_capacity(self) -> bool:
        with self._lock:
            return self._in_flight < self.concurrency

    def run_once(self, executor: ThreadPoolExecutor) -> bool:
        """Claim and dispatch at most one job. True if one was picked up."""
        if not self._has_capacity():
            return False

        db = SessionLocal()
        try:
            job = job_queue.claim_next_job(db, worker_id=self.worker_id)
            if job is None:
                return False
            job_id, ticker = job.id, job.ticker
        except Exception as e:  # noqa: BLE001 - a failed claim must not stop polling
            logger.error("Could not claim a job: %s", e, exc_info=True)
            return False
        finally:
            db.close()

        with self._lock:
            self._in_flight += 1
        executor.submit(_run_one, job_id, ticker).add_done_callback(self._finished)
        return True

    def run_forever(self) -> None:
        logger.info(
            "Analysis worker %s started (concurrency=%d, poll=%ss)",
            self.worker_id, self.concurrency, settings.ANALYSIS_POLL_SECONDS,
        )
        last_reclaim = 0.0
        with ThreadPoolExecutor(
            max_workers=self.concurrency, thread_name_prefix="analysis"
        ) as executor:
            while not self._stop.is_set():
                try:
                    now = time.monotonic()
                    # Sweep for jobs whose worker died, at the lease interval.
                    if now - last_reclaim > settings.ANALYSIS_LEASE_SECONDS:
                        last_reclaim = now
                        db = SessionLocal()
                        try:
                            job_queue.reclaim_expired_jobs(db)
                        finally:
                            db.close()

                    # Drain what is available before sleeping again.
                    while self.run_once(executor) and not self._stop.is_set():
                        pass
                except Exception as e:  # noqa: BLE001 - the loop must not die
                    logger.error("Worker loop error: %s", e, exc_info=True)

                self._stop.wait(settings.ANALYSIS_POLL_SECONDS)

        logger.info("Analysis worker %s stopped", self.worker_id)


def main() -> None:
    root_logger.info("Starting standalone analysis worker...")
    worker = Worker()
    try:
        worker.run_forever()
    except KeyboardInterrupt:
        worker.stop()


if __name__ == "__main__":
    main()
