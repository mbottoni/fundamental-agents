# Improvement Plan

Working backlog from the review of 2026-08-16. Ordered so that each phase
unblocks the next: quota and auth first (they cost money today), then the
robustness work, then the UI that surfaces what the backend already produces,
then new features.

Mark items `[x]` as they land. Each item should ship with tests and a commit.

---

## Phase 1 — Stop the bleeding (security & quota)

- [x] **1.1 Shared FMP client.** Extract `TTLCache` + retry/backoff from
  `DataGatheringAgent` into `app/core/market_data.py`. Five endpoint modules
  each define a private `_fmp()` with no retries and no caching.
- [x] **1.2 Authenticate market-data endpoints.** `/dashboard/quote`,
  `/quote-batch`, `/search`, `/chart/{ticker}`, `/market/*`, `/screener/*`,
  `/compare/` currently take no auth — the backend is an open proxy to a paid
  FMP key, and the whole app works logged out.
- [x] **1.3 Fix or remove `/quote-batch`.** It calls FMP's `batch-quote`,
  which is restricted on the current plan, so it always 502s. Reimplement as
  concurrent single quotes.
- [x] **1.4 Bound the chart history request.** `/chart/{ticker}` pulls the
  full history then trims in Python; pass `from`/`to` like the pipeline does.
- [x] **1.5 Route interactive endpoints through the cache.** Market movers and
  sector performance are identical for every user and re-fetched per page view.

## Phase 2 — Backend robustness

- [x] **2.1 API-layer tests.** Chart, market, screener, compare, watchlist,
  dashboard and Stripe have no coverage. Webhook first — it is the money path.
- [x] **2.2 Harden the Stripe webhook.** `int(client_ref_id)` 500s on
  malformed input; `invoice.payment_failed` only logs, so a failed payment
  leaves a subscription active indefinitely.
- [x] **2.3 Reuse same-day analyses.** A repeat request for the same ticker
  re-runs the whole pipeline and burns both quota and the user's allowance.
- [x] **2.4 Optional Redis cache backend.** *(landed with 1.1)* The in-process cache is per worker;
  production runs four, so the cache and the rate limiter both fragment.
- [x] **2.5 Alembic baseline.** `versions/` is empty; the schema is maintained
  by the hand-rolled `_run_auto_migrations()` in `main.py`.

## Phase 3 — Frontend

- [x] **3.1 Shared app shell.** Eight pages hand-roll their own header;
  `components/ui/` is empty.
- [x] **3.2 `RequireAuth` wrapper.** The guard is copy-pasted into three pages
  and missing from five.
- [x] **3.3 Recommendation scorecard UI.** `chart_data.recommendation` is
  persisted on every report and appears only as markdown text.
- [x] **3.4 Peer comparison UI.** Same for `chart_data.peers`.
- [x] **3.5 DCF sensitivity range.** `value_low`/`value_high` are in the
  payload; the chart draws a single bar.
- [x] **3.6 Error states.** `market/page.tsx` swallows every failure into an
  empty page; market and lists have no error state at all.
- [x] **3.7 Free-tier limit from the API** instead of a hardcoded constant.
- [x] **3.8 Polling backoff and timeout.** Currently every 4s forever.
- [~] **3.9 Split the report page** into `components/charts/`. Scorecard and
  peer comparison extracted; the twelve chart components remain inline.

## Phase 4 — New features

- [x] **4.1 Analysis snapshots.** Store the composite score, recommendation and
  price at analysis time. Cheap now, impossible retroactively, and the
  precondition for 4.2 and 4.3.
- [x] **4.2 Score history and diffs.** How a ticker's score and call moved
  between runs.
- [x] **4.3 Track past calls.** How earlier recommendations actually performed
  — what makes the confidence figure credible rather than asserted.
- [ ] **4.4 Watchlist alerts.** The model and endpoints exist but do nothing.
  Scheduled re-analysis plus a threshold alert is the retention hook.
- [ ] **4.5 PDF export.** The report is the product; make it shareable.
- [x] **4.6 Earnings-date awareness.** Flag "reports in N days" on a report.
- [ ] **4.7 Screen by composite score.** Rank a sector by our own factor model.
- [ ] **4.8 LLM narrative.** There is no LLM anywhere in this project despite
  the name; every agent now emits clean structured data, so a written summary
  over it is straightforward. Must stay optional and config-gated.

---

## Notes

- Unit tests stub all HTTP, so FMP field names are only verified by running the
  pipeline live. Do that before claiming an integration works.
- Commit per item or per coherent group; push to `main`.
