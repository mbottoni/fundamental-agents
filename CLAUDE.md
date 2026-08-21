# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Everything routes through the `Makefile` (Docker Compose based). `make help` lists all targets.

```bash
make up                # build + start backend:8000, frontend:3000, postgres (host port 5433)
make up-d              # same, detached
make logs-backend      # tail one service
make shell-backend     # bash into the backend container
make restart-backend   # after dependency/env changes (code is bind-mounted + uvicorn --reload)
```

Tests (backend only — there is no frontend test suite):

```bash
make test-backend                          # pytest inside the container
make test-local                            # cd backend && pytest  (needs local deps)
cd backend && pytest tests/test_auth.py                              # one file
cd backend && pytest tests/test_auth.py::TestRegistration::test_x    # one test
cd backend && pytest -k "free_tier"                                  # by name
```

The agent tests (`test_valuation`, `test_risk`, `test_metrics`, `test_recommendation`, `test_peer_comparison`, `test_sentiment`, `test_data_gathering`, `test_synthesis`) are pure and fast — no network, no database. `conftest.py` still loads the app, so they need the full dependency set installed.

Frontend checks (what CI runs — `.github/workflows/deploy.yml`):

```bash
cd frontend && npm run lint && npm run build
```

Database:

```bash
make migrate                                  # alembic upgrade head
make migrate-create MSG="add foo"             # autogenerate a revision
make db-tables / db-users / db-jobs           # quick psql inspections
make shell-db                                 # psql -U user -d stock-analyzer
```

Production stack (Caddy + gunicorn, needs `.env.prod`): `make prod-up` / `prod-down` / `prod-logs`.

## Architecture

**Stack:** FastAPI + SQLAlchemy 2 + Pydantic v2 (Python 3.11) / Next.js 13 App Router + TypeScript + Tailwind / PostgreSQL. Data comes from Financial Modeling Prep (FMP) and NewsAPI.

### The analysis pipeline

`POST /api/v1/analysis/` reuses a recent completed analysis where it can, and otherwise creates an `AnalysisJob` and schedules `run_analysis_background` as a FastAPI `BackgroundTask` (no Celery/queue). That task opens its **own** session via `get_standalone_session()` — request-scoped `get_db()` sessions are already closed by then — and runs `Orchestrator.run_analysis`.

`backend/app/agents/orchestrator.py` is the spine. Each agent is a stateless class with a single `run()` that takes and returns plain dicts; they never touch the DB:

1. `DataGatheringAgent` — FMP statements/prices/TTM ratios/profile/segments/dividends + a benchmark series + NewsAPI articles → `raw_data`. The eleven requests are fanned out across a thread pool, retried with backoff on 429/5xx, and cached in-process per endpoint (`TTLCache`). The profile is fetched first because the news query needs the company name.
2. `FinancialMetricsAgent` — ~30 ratios nested under `metrics["groups"][...]`, computed from annual statements then overlaid with TTM figures where FMP supplies them (`metrics["ttm_metrics"]` lists which)
3. `TechnicalAnalysisAgent` — RSI, MACD, MAs, Bollinger, momentum
4. `RiskAssessmentAgent` — volatility, Sharpe/Sortino, VaR, drawdown over a trailing 252-session window, plus beta regressed against SPY
5. `NewsSentimentAgent` — VADER with a finance lexicon, relevance filtering, and recency weighting
6. `ValuationAgent` — two-stage FCFF DCF: discount unlevered FCF at WACC, then bridge to equity via `EV − debt + cash`. Returns a sensitivity grid, not just a point estimate
7. `PeerComparisonAgent` — multiples against the peer median and the sector/industry P/E snapshots. Both sides come from FMP's `ratios-ttm` so the comparison is like for like; feeds a relative valuation score into the recommendation
8. `EarningsAgent` — next report date and the recent surprise record; an imminent report lowers confidence
9. `RecommendationEngine` (`recommendation.py`) — scores six weighted factors into the buy/hold/sell call; run by the orchestrator, not by an agent
10. `NarrativeAgent` — the only model call in the pipeline. Explains the conclusions in prose; disabled without `ANTHROPIC_API_KEY`, and never fatal
11. `SynthesisReportingAgent` — renders the markdown report from all of the above

**Where to be careful:** the DCF must keep its equity bridge and its guard rails (negative FCF, the WACC-vs-terminal-growth spread, negative equity value) — each exists because removing it produces confident nonsense. The recommendation is capped by the valuation factor so quality and growth cannot outvote price entirely.

The orchestrator writes job status at each stage (`pending → gathering_data → analyzing → generating_report → complete | failed`); the frontend dashboard polls `GET /api/v1/analysis/{id}` every 4s. Exceptions are caught and turned into a user-facing `error_message` on the job via `Orchestrator._failure_message`; raise `DataUnavailableError` with an explanatory message for anything the user could act on. Jobs left mid-flight by a restart are failed at startup by `_reap_interrupted_jobs`.

Reuse happens at two levels inside `start_analysis`, both bounded by `ANALYSIS_REUSE_HOURS` and both skipped when `force=true`: the user's own recent analysis is returned as-is, and failing that any user's recent analysis of the ticker is **copied** into a new job for the requester (`_reuse_existing_analysis`). Nothing in a report depends on who asked for it, so rebuilding one would spend eleven provider requests to produce an identical document. Rows are copied, never shared — `Report.job_id` is unique and every ownership check keys off the job's owner. A reused analysis still counts against the free-tier daily cap; exempting it would spend no quota but would turn the free tier into unlimited analyses for any popular ticker.

Each completed analysis also writes an `AnalysisSnapshot` — the recommendation, score and price at that moment. It backs `/api/v1/history/*` (per-ticker history, past-call performance, leaderboard) and the watchlist alerts, and cannot be reconstructed after the fact.

**Two outputs per job:** the markdown `Report.content`, and `Report.chart_data`, a JSON **string** built by `Orchestrator._build_chart_data()`. That dict is the contract for the report page's Recharts components — its shape must stay in sync with `ChartData` in `frontend/src/types/index.ts`. It is serialized in `crud.create_report` and deserialized by a `field_validator` on `schemas.Report`.

When adding an agent: write the class with `run()`, instantiate it in `Orchestrator.__init__`, call it in `run_analysis`, and thread its output into both `_build_chart_data` and `SynthesisReportingAgent.run`. If it produces something the recommendation should weigh, add a factor in `recommendation.py` rather than special-casing it in the report.

**Background work:** a periodic asyncio task in `lifespan` sweeps every watchlist for alerts (`ALERT_SWEEP_MINUTES`, 0 disables). It runs the blocking evaluation in a worker thread and survives its own failures.

**Verifying against the live API:** unit tests stub all HTTP, so FMP field names and endpoint paths are only checked by running the pipeline for real. `Orchestrator(...).data_agent.run(ticker)` plus the agents, with no DB, is enough to catch a renamed field — that is how the `dividends` endpoint 404 and the zero-interest-coverage issue were found.

### API layer

One module per resource in `app/api/v1/endpoints_*.py`, each exporting `router`, wired up with a prefix in `app/main.py`. Auth is JWT via `Depends(get_current_user)` from `app/api/deps.py`.

**Every provider-backed endpoint must require auth.** Without it the deployment is an open proxy to a paid market-data key; `tests/test_endpoint_auth.py` walks the route list, so a new unauthenticated one fails CI.

All FMP traffic goes through `app/core/market_data.py` — retries with backoff on 429/5xx, per-endpoint TTL caching, and an optional Redis backend via `REDIS_URL`. Do not add a local `_fmp()` helper to an endpoint module.

**FMP gotchas:**
- The app targets the `/stable` API (`https://financialmodelingprep.com/stable`), which takes `?symbol=AAPL` query params, not the legacy `/api/v3/{path}/AAPL` form.
- Out-of-plan endpoints answer with **HTTP 200 and a plain-text body**, not an error status. The client detects those (`PLAN_RESTRICTED`) so a feature can say it needs a different plan instead of rendering "no results". `company-screener` and `batch-quote` are restricted on the current plan, and `earnings` caps `limit` at 5.

### Auth, tiers, and payments

- Access token + refresh token, both HS256 (`app/core/security.py`); `generate_timed_token`/`verify_timed_token` back email verification and password reset (emails are logged to console when SMTP is unset).
- `get_current_user` has a deliberate side effect: emails listed in `settings.PREMIUM_EMAILS` are force-upgraded to `subscription_status = "active"` on every request.
- Free tier is capped at `FREE_TIER_DAILY_ANALYSES` (default 3) — enforced in `endpoints_analysis.start_analysis` via `crud.count_user_analyses_today`, returning 429. The frontend duplicates the number as `FREE_ANALYSIS_LIMIT` in `dashboard/page.tsx`.
- Stripe subscription status is updated through the webhook in `endpoints_stripe.py`.

### Schema management

Models use `TableNameMixin` (auto `__tablename__` = lowercase class name + "s") and `TimestampMixin` from `app/db/base_class.py`; every model must be imported in `app/db/base.py` so `Base.metadata` and Alembic autogenerate see it.

The startup `lifespan` calls `Base.metadata.create_all()` **and** `_run_auto_migrations()` in `main.py`, a hand-rolled "add column if missing" block. `alembic/versions/` is currently empty, so that block is what actually keeps deployed databases current. Adding a column to an existing table means either a real Alembic revision or another entry there.

### Frontend

- Never call `axios` directly — import the configured singleton from `@/lib/api`. It attaches the bearer token from `localStorage` and, on 401, refreshes the token once while queueing concurrent failures; a failed refresh forces logout and redirect to `/login`.
- Surface API errors with `getErrorMessage` from `@/lib/errors` (it flattens both FastAPI `detail` strings and Pydantic validation arrays).
- Auth state lives in the `useAuth` context (`src/hooks/useAuth.tsx`); pages are client components that redirect to `/login` when `!isLoading && !isAuthenticated`.
- Two visual modes share one stylesheet: app pages (dashboard, report, chart) are dark and use the `.glass-card` / `.input-field` / `.text-gradient` component classes in `src/styles/globals.css`; marketing pages (landing, pricing) are light and use `.btn-primary` / `.btn-secondary` with the `brand-*` palette.

## Configuration

`app/core/config.py` is a `pydantic-settings` model with **no defaults** for `SECRET_KEY` (≥32 chars), `DATABASE_URL`, the two API keys, and the two Stripe keys — a missing one raises at import time, before FastAPI starts. The root `.env` is what `docker-compose` feeds to the backend container; `backend/.env` is for running outside Docker.

`tests/conftest.py` therefore sets those env vars via `os.environ.setdefault` **before** importing the app, then swaps in an in-memory SQLite engine through `app.dependency_overrides[get_db]`. Keep those two blocks ahead of any app import when editing test setup.

## Notes

`README.md` predates the current code: it documents 5 agents (there are 7) and omits the dashboard, watchlist, compare, screener, chart, and market endpoints. Prefer the source.
