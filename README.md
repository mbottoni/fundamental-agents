# Stock Analyzer AI

A multi-agent AI platform for fundamental stock analysis. Input a ticker, get an institutional-grade investment report -- powered by specialized agents that gather data, compute metrics, analyze sentiment, and model valuations.

## Architecture

```
                         +-----------+
                         |  Frontend |  Next.js 13 (App Router)
                         |  :3000    |  TypeScript, Tailwind CSS
                         +-----+-----+
                               |
                          REST API
                               |
                         +-----+-----+
                         |  Backend  |  FastAPI, SQLAlchemy
                         |  :8000    |  Python 3.11
                         +-----+-----+
                               |
                 +-------------+-------------+
                 |                           |
           +-----+-----+             +------+------+
           | PostgreSQL |             | Orchestrator|
           |   :5432    |             +------+------+
           +------------+                    |
                     +---------+----+----+----+---------+
                     |         |    |    |    |         |
                    D.G.     F.M.  T.A. R.A. N.S.     Val.
                   Agent    Agent Agent Agent Agent   Agent
                     |         |    |    |    |         |
                     +---------+----+-+--+----+---------+
                                      |
                              Recommendation
                                 Engine
                                      |
                                 Synthesis
                                   Agent
```

### Agent Pipeline

The **Orchestrator** coordinates specialized agents, then scores the result:

| Agent | Role | Data Source |
|-------|------|-------------|
| **Data Gathering** | Financial statements, TTM ratios, price history, company profile, dividends, benchmark series, news -- fetched concurrently, retried on throttling, cached per endpoint | Financial Modeling Prep, NewsAPI |
| **Financial Metrics** | ~30 ratios across valuation, profitability, liquidity, leverage, efficiency, growth and cash flow, on a trailing-twelve-month basis where available | Raw financial data |
| **Technical Analysis** | RSI, MACD, moving averages, Bollinger bands, ATR, momentum, support/resistance | Price history |
| **Risk Assessment** | Volatility, Sharpe, Sortino, VaR and drawdown over a trailing 252-session window; beta regressed against SPY | Price history + benchmark |
| **News Sentiment** | VADER with a financial lexicon, relevance filtering and recency weighting | News articles |
| **Valuation** | Two-stage FCFF DCF discounted at WACC, bridged to equity value, with a WACC x terminal-growth sensitivity grid | Financial data + profile |
| **Peer Comparison** | Multiples against the peer median and sector/industry P/E, with premium/discount and percentile rank | Financial Modeling Prep |
| **Earnings** | Next report date, consensus estimate, and the recent surprise record | Financial Modeling Prep |
| **Recommendation** | Scores six weighted factors -- valuation, quality, financial health, growth, momentum, sentiment -- into a buy/hold/sell call, capped by valuation | All agent outputs |
| **Narrative** *(optional)* | Plain-English summary of the conclusions; disabled without an `ANTHROPIC_API_KEY` | All agent outputs |
| **Synthesis** | Markdown report with a scorecard showing every factor's score and drivers | All agent outputs |

Factors without data are dropped and their weight redistributed, so a company
with no usable DCF is still assessed on everything else. Confidence reflects
how much of the model had data behind it and how much the factors agree.

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 13, React 18, TypeScript, Tailwind CSS, Axios |
| Backend | FastAPI, SQLAlchemy, Pydantic v2, Python 3.11 |
| Database | PostgreSQL 13 |
| Auth | JWT (python-jose), bcrypt (passlib) |
| Payments | Stripe (checkout sessions, webhooks) |
| HTTP Client | httpx (backend), Axios (frontend) |
| NLP | NLTK VADER |
| Infrastructure | Docker, Docker Compose, GitHub Actions |

## Project Structure

```
agents_invest/
├── backend/
│   ├── app/
│   │   ├── agents/              # Multi-agent pipeline
│   │   │   ├── orchestrator.py
│   │   │   ├── data_gathering_agent.py
│   │   │   ├── financial_metrics_agent.py
│   │   │   ├── technical_analysis_agent.py
│   │   │   ├── risk_assessment_agent.py
│   │   │   ├── news_sentiment_agent.py
│   │   │   ├── valuation_agent.py
│   │   │   ├── peer_comparison_agent.py
│   │   │   ├── recommendation.py
│   │   │   └── synthesis_reporting_agent.py
│   │   ├── api/                 # REST API layer
│   │   │   ├── deps.py          # Auth dependencies
│   │   │   └── v1/
│   │   │       ├── endpoints_auth.py
│   │   │       ├── endpoints_analysis.py
│   │   │       ├── endpoints_reports.py
│   │   │       └── endpoints_stripe.py
│   │   ├── core/                # Config, DB, security
│   │   ├── crud/                # Database operations
│   │   ├── models/              # SQLAlchemy models
│   │   └── schemas/             # Pydantic schemas
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/                 # Next.js App Router pages
│       │   ├── (auth)/          # Login, Register
│       │   ├── dashboard/       # Main analysis interface
│       │   ├── pricing/         # Subscription plans
│       │   └── report/[id]/     # Report viewer
│       ├── hooks/useAuth.tsx    # Auth context & hook
│       ├── lib/api.ts           # Axios client with interceptors
│       └── types/index.ts       # Shared TypeScript types
├── docker-compose.yml
├── Makefile
└── .env.example
```

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- API keys for [Financial Modeling Prep](https://financialmodelingprep.com/) and [NewsAPI](https://newsapi.org/)

### Setup

```bash
# 1. Clone the repository
git clone <repo-url> && cd agents_invest

# 2. Create your environment file
cp .env.example .env
# Edit .env and fill in your API keys and a secure SECRET_KEY

# 3. Start all services
make up

# 4. Open the app
# Frontend: http://localhost:3000
# Backend API docs: http://localhost:8000/docs
# Health check: http://localhost:8000/health
```

### Generate a SECRET_KEY

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

## API Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/api/v1/auth/register` | Create a new account | No |
| `POST` | `/api/v1/auth/login` | Get access token | No |
| `POST` | `/api/v1/auth/refresh` | Exchange a refresh token | No |
| `GET` | `/api/v1/auth/me` | Current user profile | Yes |
| `POST` | `/api/v1/auth/verify-email` | Confirm an email address | No |
| `POST` | `/api/v1/auth/forgot-password` | Request a reset link | No |
| `POST` | `/api/v1/auth/reset-password` | Set a new password | No |
| `POST` | `/api/v1/analysis/` | Start analysis job | Yes |
| `GET` | `/api/v1/analysis/{id}` | Poll job status | Yes |
| `GET` | `/api/v1/analysis/` | List user's jobs | Yes |
| `GET` | `/api/v1/reports/{id}` | Get report content | Yes |
| `GET` | `/api/v1/dashboard/*` | Quotes, stats, search | Yes |
| `GET`/`POST`/`PATCH`/`DELETE` | `/api/v1/watchlist/*` | Manage watchlist | Yes |
| `GET` | `/api/v1/compare/` | Compare tickers | Yes |
| `GET` | `/api/v1/screener/*` | Screen by criteria | Yes |
| `GET` | `/api/v1/chart/{ticker}` | Prices + indicators | Yes |
| `GET` | `/api/v1/market/*` | Movers, sectors, lists | Yes |
| `POST` | `/api/v1/stripe/create-checkout-session` | Start checkout | Yes |
| `POST` | `/api/v1/stripe/webhook` | Stripe events | No |
| `GET` | `/api/v1/history/{ticker}` | Analysis history for a ticker | Yes |
| `GET` | `/api/v1/history/` | How past calls have performed | Yes |
| `GET` | `/api/v1/history/leaderboard` | Analysed tickers ranked by score | Yes |
| `GET`/`POST` | `/api/v1/alerts/*` | Watchlist alerts | Yes |
| `GET` | `/health` | Health check | No |

### Job Status Flow

```
pending -> gathering_data -> analyzing -> generating_report -> complete
                                                            -> failed
```

A failed job carries an `error_message` explaining why, and failed jobs do not
count against the free tier's daily allowance. Jobs interrupted by a server
restart are failed on the next startup rather than left polling forever.

## Database Schema

```
users
  id                  INTEGER PK
  email               VARCHAR UNIQUE
  hashed_password     VARCHAR
  stripe_customer_id  VARCHAR UNIQUE (nullable)
  subscription_status VARCHAR (default: "free")
  created_at          TIMESTAMP
  updated_at          TIMESTAMP

analysisjobs
  id            INTEGER PK
  user_id       INTEGER FK -> users.id
  ticker        VARCHAR
  status        VARCHAR (default: "pending")
  error_message TEXT (nullable, set when status is "failed")
  created_at    TIMESTAMP
  updated_at    TIMESTAMP

reports
  id         INTEGER PK
  content    TEXT
  chart_data TEXT (JSON: chart series + recommendation scorecard)
  job_id     INTEGER FK -> analysisjobs.id (UNIQUE)
  created_at TIMESTAMP
  updated_at TIMESTAMP
```

## Environment Variables

See [`.env.example`](.env.example) for the full list. Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | JWT signing key (min 32 chars) |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `FINANCIAL_MODELING_PREP_API_KEY` | Yes | FMP API key |
| `NEWS_API_KEY` | Yes | NewsAPI key |
| `STRIPE_SECRET_KEY` | Yes | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Yes | Stripe webhook signing secret |
| `STRIPE_PREMIUM_PRICE_ID` | No | Stripe price ID for premium plan |
| `FRONTEND_URL` | No | Frontend origin for CORS (default: `http://localhost:3000`) |

## License

This project is for educational and personal use.
