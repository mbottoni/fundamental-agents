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
                               +-------------+-------------+
                               |      |      |      |      |
                              D.G.  F.M.   N.S.   Val.   Syn.
                            Agent  Agent  Agent  Agent  Agent
```

### Agent Pipeline

The **Orchestrator** coordinates five specialized agents in sequence:

| Agent | Role | Data Source |
|-------|------|-------------|
| **Data Gathering** | Fetches financial statements, price history, company profile, news | Financial Modeling Prep, NewsAPI |
| **Financial Metrics** | Computes P/E, D/E, ROE, Current Ratio | Raw financial data |
| **News Sentiment** | VADER-based sentiment analysis on recent articles | News articles |
| **Valuation** | DCF model with WACC, projected FCF, terminal value | Financial data + profile |
| **Synthesis** | Generates a markdown report with recommendation | All agent outputs |

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
│   │   │   ├── news_sentiment_agent.py
│   │   │   ├── valuation_agent.py
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
| `GET` | `/api/v1/auth/me` | Current user profile | Yes |
| `POST` | `/api/v1/analysis/` | Start analysis job | Yes |
| `GET` | `/api/v1/analysis/{id}` | Poll job status | Yes |
| `GET` | `/api/v1/analysis/` | List user's jobs | Yes |
| `GET` | `/api/v1/reports/{id}` | Get report content | Yes |
| `POST` | `/api/v1/stripe/create-checkout-session` | Start checkout | Yes |
| `POST` | `/api/v1/stripe/webhook` | Stripe events | No |
| `GET` | `/health` | Health check | No |

### Job Status Flow

```
pending -> gathering_data -> analyzing -> generating_report -> complete
                                                            -> failed
```

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
  id         INTEGER PK
  user_id    INTEGER FK -> users.id
  ticker     VARCHAR
  status     VARCHAR (default: "pending")
  created_at TIMESTAMP
  updated_at TIMESTAMP

reports
  id         INTEGER PK
  content    TEXT
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
