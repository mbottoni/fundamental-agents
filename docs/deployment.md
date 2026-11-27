# Deployment

How this project is deployed: one server running Docker Compose, shipped by GitHub Actions on every push to `main`.

Production is a single server running `docker-compose.prod.yml`: the API, the analysis worker, the Next.js frontend, Postgres 17 and Caddy, which obtains and renews the HTTPS certificate.

## Deploying

**Deploying is `git push origin main`.** The CI workflow (`.github/workflows/ci.yml`) then runs:

| Job | What it does |
|-----|--------------|
| `backend-test` | The test suite, with a PostgreSQL service for the tests only PostgreSQL can run (queue locking, exact schema drift) |
| `frontend-build` | Lint and build |
| `types-check` | Regenerates the frontend's API types and fails if the committed file is stale |
| `images` | Builds both images, then runs `ops/smoke-test.sh`: the real compose file behind Caddy, with production settings. Pushes to GHCR only from `main`, and only if the smoke test passed |
| `deploy` | Copies `docker-compose.prod.yml`, `Caddyfile` and `ops/backup.sh` to the server, pulls the new images, restarts the stack, and fails the run unless `/healthz` reports `ok` **for the commit just deployed** |

The `deploy` job is skipped until the `DEPLOY_URL` variable is set, so the repository can be worked on before a server exists.

The images are `ghcr.io/mbottoni/fundamental-agents-api` and `ghcr.io/mbottoni/fundamental-agents-web`, tagged with the commit sha and `latest`. The API and the worker are the same image.

### What the smoke test checks

`ops/smoke-test.sh <tag> [expected-version]` starts the stack from a scratch directory laid out like the server and requires:

- `/healthz` through Caddy to report `ok`: database reachable, migrations applied, worker alive;
- the version reported to be the commit that was built;
- `/` to answer, `/api/*` to reach the backend, `/docs` and `/openapi.json` not to;
- an account to register and sign in (Caddy, API and Postgres in one request);
- `next/image` to return a resized image;
- every app container to run as a non-root user;
- no `localhost:8000` in the frontend bundle.

Run it by hand after `make prod-build` with `make smoke`.

## Rolling back, or deploying without a commit

Actions → *Deploy a chosen version* → *Run workflow*, and enter the full commit sha of a green run on `main`. Or:

```bash
gh workflow run deploy.yml -f image_tag=<sha>
```

It runs the images CI already built for that commit, with that commit's compose file and Caddyfile, and applies the same health check. Images from the last three days stay on the server, so a recent rollback downloads nothing.

**It does not roll the database back.** Migrations only run forward. An older image on a newer schema starts: the app leaves a database newer than itself alone, and `/healthz` reports `"migrations": "ahead"`, which counts as healthy. It works as long as the revisions in between only added things. Before rolling back across a revision that removed or renamed something, read `backend/alembic/versions/` between the two commits.

## What lives where

| Thing | Location |
|-------|----------|
| Code, compose file, Caddyfile | this repository |
| `DEPLOY_HOST`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS` | GitHub Actions secrets |
| `DEPLOY_URL` (the site's origin; the health check uses it) | GitHub Actions variable |
| App secrets, `SITE_ADDRESS`, the database password | `/opt/fundamental-agents/.env.prod` on the server |
| Database | `fundamental-agents_pgdata` Docker volume on the server |
| Database dumps | `/opt/fundamental-agents/backups/` on the server, and the bucket once configured |
| TLS certificates | `fundamental-agents_caddy_data` Docker volume on the server |

## Setting up a new server

1. Ubuntu 24.04 with Docker. Firewall open on 22, 80 and 443 only. Docker publishes ports past `ufw`, which is why only Caddy has a `ports:` entry in the compose file; use the provider's cloud firewall as well.
2. A `deploy` user in the `docker` group, owning `/opt/fundamental-agents`:

   ```bash
   adduser --disabled-password --gecos "" deploy
   usermod -aG docker deploy
   install -d -o deploy -g deploy /opt/fundamental-agents
   install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
   ```

3. A key pair for deploys. The private half becomes the `DEPLOY_SSH_KEY` secret; the public half goes in `/home/deploy/.ssh/authorized_keys`:

   ```bash
   ssh-keygen -t ed25519 -N "" -C "github-deploy" -f deploy_key
   ssh-keyscan -t ed25519 <server address>     # this output is DEPLOY_KNOWN_HOSTS
   ```

4. `/opt/fundamental-agents/.env.prod`, mode 600, owned by `deploy`. Start from `.env.prod.example`. The stack needs at least:

   ```bash
   SITE_ADDRESS=example.com
   FRONTEND_URL=https://example.com
   SECRET_KEY=<python3 -c "import secrets; print(secrets.token_urlsafe(64))">
   POSTGRES_PASSWORD=<openssl rand -hex 24>
   FINANCIAL_MODELING_PREP_API_KEY=...
   NEWS_API_KEY=...
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   PREMIUM_EMAILS=
   REGISTRATION_MODE=invite
   REGISTRATION_ALLOWLIST=you@example.com
   ```

   `POSTGRES_PASSWORD` is placed inside the database URL, so keep it to letters and digits. Use Stripe **test** keys until the go-live checklist is done.

5. Point the name's `A` record at the server. Caddy asks for the certificate on the first request, so the name must resolve first.
6. In GitHub: the three `DEPLOY_*` secrets, the `DEPLOY_URL` variable (`https://example.com`), and an environment named `production`.
7. Push to `main`, or run the `CI` workflow by hand.

The first start creates the database and applies every migration. Then run one real analysis: the test suite stubs every provider call, so this is the first time the deployed code talks to the market-data provider.

When the domain changes, update `SITE_ADDRESS`, `FRONTEND_URL`, `DEPLOY_URL` and the Stripe webhook endpoint together.

## Settings

Read from `.env.prod`. The app refuses to start without the first five.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | -- | Signs access, refresh, reset and verification tokens. At least 32 characters |
| `FINANCIAL_MODELING_PREP_API_KEY` | Yes | -- | Market data. The current plan allows 250 requests a day; an analysis costs about eleven |
| `NEWS_API_KEY` | Yes | -- | Headlines for the sentiment stage |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Yes | -- | Stripe. The webhook endpoint is `https://<domain>/api/v1/stripe/webhook` |
| `POSTGRES_PASSWORD` | Yes | -- | Used by the `db` service and to build `DATABASE_URL` for the API and worker |
| `SITE_ADDRESS` | Yes | -- | The hostname Caddy serves. No scheme |
| `FRONTEND_URL` | Yes in practice | `http://localhost:3000` | The site's origin. Links in emails and Stripe return URLs are built from it; left at the default, they point at localhost |
| `STRIPE_LIVE` | No | `false` | Set to `true` only with live keys. The app refuses to start if this and the key disagree, so test keys are a decision and a live key cannot slip in |
| `STRIPE_PREMIUM_PRICE_ID` | For payments | -- | The Stripe Price of the premium plan. Without it checkout answers 503 |
| `PREMIUM_EMAILS` | Optional | empty | Comma-separated addresses that always get premium, once the address is verified. Without email configured, verify it by hand (see *What production refuses*) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAILS_FROM_ADDRESS` | Optional | -- | Outgoing email. Unset, nothing is sent: no verification, no password reset. See *What production refuses* for verifying by hand |
| `ANTHROPIC_API_KEY` | Optional | -- | Turns on the written summary at the top of each report |
| `SENTRY_DSN` | Optional | -- | Error tracking. Unset means off |
| `REGISTRATION_MODE` | Set it | `open` | `open`, `invite` (only the addresses in `REGISTRATION_ALLOWLIST`) or `closed`. Start a new deployment on `invite` |
| `REGISTRATION_ALLOWLIST` | With `invite` | empty | Comma-separated addresses allowed to sign up |
| `FREE_TIER_DAILY_ANALYSES` | No | `3` | Daily analyses for a free account |
| `RATE_LIMIT_PER_MINUTE` | No | `30` | Requests a minute per signed-in user, or per address when signed out |
| `ANALYSIS_REUSE_HOURS` | No | `12` | A completed analysis of a ticker is reused, for anyone, for this long |
| `ANALYSIS_WORKER_CONCURRENCY` | No | `2` | Analyses the worker runs at once. Each is about eleven provider requests |
| `ALERT_SWEEP_MINUTES` | No | `60` | How often watchlists are checked for alerts. The compose file sets 0 on the worker so only the API sweeps |
| `LOG_LEVEL` | No | `INFO` | |
| `REDIS_URL` | No | -- | Not needed with one API process |

Set by the compose file, not by hand: `ENVIRONMENT=production`, `DATABASE_URL`, `ANALYSIS_WORKER_INLINE=false`, and `IMAGE_TAG`, which each deploy appends to `.env.prod` so a reboot brings back the deployed version.

### What production refuses

With `ENVIRONMENT=production` the API and the worker stop at start-up, naming every problem at once, if:

- `FRONTEND_URL` is not an `https://` origin;
- `SECRET_KEY` is a placeholder from an example file;
- `DATABASE_URL` points at SQLite;
- `STRIPE_SECRET_KEY` is a live key without `STRIPE_LIVE=true`, or the reverse.

Production also serves no `/docs`, `/redoc` or `/openapi.json`, allows no localhost CORS origin, and never writes an unsent email to the log: those emails carry working reset and verification links. Without email configured, verify an account by hand:

```bash
$C exec api python -m app.manage verify you@example.com
$C exec api python -m app.manage users
```

## Operating it

On the server, from `/opt/fundamental-agents`:

```bash
C="docker compose -f docker-compose.prod.yml --env-file .env.prod"
$C ps                         # what is running, and whether it is healthy
$C logs -f api worker         # the app's logs
$C exec db psql -U app app    # the database
curl -s https://<domain>/healthz
```

`/healthz` answers 200 with `"status": "ok"` or `"degraded"` and says which part is wrong:

| Field | Values |
|-------|--------|
| `database` | `true` / `false` |
| `migrations` | `current`, `behind` (the API has not migrated it; look at the API's log), `ahead` (a rollback) |
| `worker` | `ok`, `stale` (not seen for 90 seconds), `missing` (never seen: is the `worker` container running?) |
| `version` | the commit the running image was built from |

With no worker, every analysis stays `pending`. `$C up -d worker` starts it; jobs that were claimed by a worker that died are picked up again once their lease expires (five minutes).

## Backups

The `backup` service (`ops/backup.sh`) runs `pg_dump` every night at 03:00 UTC into `/opt/fundamental-agents/backups/` on the server, keeps the newest 14, and takes one at start-up if there is none from today. Each dump is written under a temporary name and checked with `pg_restore --list` before it is kept, so an interrupted dump never looks like a finished one.

The database holds accounts, subscription state and the `AnalysisSnapshot` history: what the model recommended and the price at that moment. Those rows cannot be rebuilt afterwards.

**These dumps are on the same server as the database.** They cover a bad migration or a mistaken delete, not the loss of the server. For an off-box copy, create a bucket on S3-compatible storage and add to `.env.prod`:

```bash
BACKUP_S3_BUCKET=fundamental-agents-backups
BACKUP_S3_ENDPOINT=https://<account id>.r2.cloudflarestorage.com
BACKUP_S3_ACCESS_KEY_ID=...
BACKUP_S3_SECRET_ACCESS_KEY=...
# BACKUP_S3_PROVIDER=Cloudflare   # or AWS, Backblaze, Other
```

then `$C up -d backup`. Every later dump is uploaded too, and copies older than 60 days are removed.

```bash
$C exec backup sh /backup.sh once      # take a dump now
$C exec backup sh /backup.sh verify    # restore the newest dump into a scratch database and compare
$C logs backup                         # what ran, and any UPLOAD FAILED / BACKUP FAILED
```

The first dump after a brand-new deploy can be of an empty database, taken before the API had created the tables. Run `once` after the first deploy, or wait for 03:00.

**To restore for real** (this replaces the live data; stop everything that writes first):

```bash
$C stop api worker
$C exec backup sh -c 'dropdb app && createdb app && pg_restore --no-owner -d app /backups/<file>.dump'
$C start api worker
```

CI takes a dump and restores it on every run, as part of the smoke test.

## Running the production stack locally

```bash
cp .env.prod.example .env.prod     # then set SITE_ADDRESS=:80 and FRONTEND_URL=http://localhost:8080
make prod-up                       # builds both images, starts the stack on :8080
make prod-up PROD_PORT=18080       # if 8080 is taken
make smoke                         # the checks CI runs, against the images just built
make prod-down
```

`SITE_ADDRESS=:80` makes Caddy serve plain HTTP and ask for no certificate.

## Uptime check

`.github/workflows/uptime.yml` asks `<DEPLOY_URL>/healthz` for a healthy answer every five minutes, from GitHub's network. Three failed attempts over about a minute open an issue labelled `outage`, assigned to the repository owner, so GitHub sends an email. While the site stays down it adds one comment an hour; the first healthy check records the recovery time and closes the issue. It does nothing until `DEPLOY_URL` is set.

It is a floor, not a full monitor: GitHub often runs scheduled workflows several minutes late, and stops scheduling them after 60 days without a commit. To test the alert:

```bash
gh workflow run uptime.yml -f url=https://example.invalid/healthz
```

## Not set up yet

Tracked in the [roadmap](https://github.com/mbottoni/fundamental-agents/issues/54): off-box backup storage, and a daily budget for provider requests. Until then, keep `REGISTRATION_MODE=invite` and Stripe test keys.
