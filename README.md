# VAALCO Fuel Intelligence Platform

AI-assisted fuel-monitoring and analytics for offshore vessel operations. Ingests
vessel operational reports, runs **deterministic** Python analysis (fuel vs.
DP-workload model, DP efficiency, maintenance, fluids, HSE), and uses a frontier
LLM **only to explain** the findings, flag issues, and estimate financial impact
for non-technical staff.

> **Load-bearing design rule:** the math is done in Python; the LLM never
> computes numbers, it only interprets what the code already calculated. This
> separation is intentional and must not be collapsed.

## Architecture

A scalable, event-driven system built to handle thousands of report files across
many vessels.

```
Frontend (Next.js, EN/FR) ── Vercel
        │  HTTPS + Supabase JWT
        ▼
API (FastAPI) ── Render (always-on)
        │                 │ enqueue                 ▲ query
        │                 ▼                          │
        │        Queue (Supabase pgmq) ──▶ Workers ── Modal (elastic)
        │                                   parser→analysis→signals→intelligence
        ▼                                          │
Supabase ── Postgres (system of record) · Storage (raw xlsx + reports) · Auth (RLS)
        │
        ▼
Notifications ── Resend (email) + Twilio (SMS, optional), severity-gated
```

| Layer | Tech | Home |
|-------|------|------|
| Frontend | Next.js + next-intl (English/French) | Vercel |
| API | FastAPI (async) | Render |
| Workers | Modal functions (event-driven, autoscaling) | Modal |
| Data | Postgres + Storage + Auth (row-level security) | Supabase |
| LLM | Provider-abstracted (Claude default, OpenAI swappable) | — |
| Email/SMS | Resend + Twilio | — |

## Repository layout

```
core/        Deterministic analysis core (parser, analysis, signals,
             intelligence, report, notify) + provider-abstracted LLM client.
             Preserved from the original build; math/prompts unchanged.
apps/api/    FastAPI service (Render): /ask chat tool-loop, /signals, /reports.
apps/web/    Next.js frontend (Vercel): dashboards, Ask chat, Signals, EN/FR.
workers/     Modal functions: ingest + analyze report files at scale.
db/          Supabase SQL migrations (schema, RLS, storage buckets).
infra/       Dockerfiles, render.yaml, deploy config.
legacy/      Original single-file monolith, kept for reference.
docs/        Architecture notes and the original project README.
reports/     Sample vessel reports (test fixtures).
```

## Local development

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # fill in your keys
# API:
uvicorn apps.api.main:app --reload --port 8000
# Frontend:
cd apps/web && npm install && npm run dev
```

## Configuration

All secrets are read from environment variables (see `.env.example`). Nothing
sensitive is committed. In the cloud, set them in each platform's secret manager
(Render env, Modal secrets, Vercel env, GitHub Actions secrets).

## Deployment

CI/CD via GitHub Actions on push to `main`. See `infra/` and `.github/workflows/`.
