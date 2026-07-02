# Deployment — as built

Everything is deployed and verified end-to-end (2026-07-02).

## Live URLs

| Surface | URL |
|---------|-----|
| Web app (Vercel) | https://vaalco-fuel-intelligence.vercel.app |
| API (Modal) | https://team-work--vaalco-api-fastapi-app.modal.run |
| Ingestion webhook (Modal) | https://team-work--vaalco-workers-ingest-webhook.modal.run |
| Supabase project | https://bluokagtcjcqkaflbtjw.supabase.co |
| GitHub repo | https://github.com/Stealth-Pareto-Labs/Vaalco_Customer |

**Demo login:** access code `Vaalco123` (env `ACCESS_CODE`).

## Platform map

- **Vercel** — Next.js frontend (`apps/web`). Project `cortif-ai/vaalco-fuel-intelligence`.
  Build-time env: `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
- **Modal** — two apps in workspace `team-work`:
  - `vaalco-api` — the FastAPI app as an always-warm ASGI endpoint (`workers/modal_api.py`, `min_containers=1`).
  - `vaalco-workers` — ingestion functions `ingest_report`, `ingest_many`, and the `ingest_webhook` endpoint (`workers/modal_app.py`).
  - Both read the Modal secret **`vaalco-secrets`** (recreate with `python infra/create_modal_secret.py`).
- **Supabase** — Postgres (system of record), Storage (`raw-reports`, `intelligence-runs`), Auth + RLS. Schema in `db/migrations/`.
- **Claude Sonnet 5** — every LLM call (Ask chat + Signals prose). Provider-abstracted in `core/llm.py`.
- **Resend** — transactional email (`core/notify.py`). Live send pending sender-domain verification.

## Why Modal (not Render) for the API

The plan targeted Render for the API, but Render's GitHub App had no access to the
`Stealth-Pareto-Labs` org repo (account-linkage issue). Rather than block on that, the
FastAPI app runs on Modal as an always-warm ASGI app — keeping all Python deploys on one
platform. The Render blueprint (`infra/render.yaml`, `infra/render_create.py`) remains for
a future switch: grant Render's GitHub App access to the repo, run `python infra/render_create.py`,
and repoint `NEXT_PUBLIC_API_BASE_URL`.

## Data path note (important)

Supabase's direct DB host is **IPv6-only** and the connection pooler is not enabled for
this project, so serverless (Modal, IPv4) cannot open a Postgres socket. Runtime persistence
therefore uses the **PostgREST HTTP API** (`core/store.py`, service-role key, IPv4). Schema
migrations (DDL) are applied with `db/apply_migrations.py` from a machine with IPv6
(e.g. a laptop or CI).

## Redeploy

CI/CD (`.github/workflows/deploy.yml`) auto-deploys on push to `main`
(GitHub secrets: `MODAL_TOKEN_ID/SECRET`, `VERCEL_TOKEN/ORG_ID/PROJECT_ID`).

Manual:
```bash
# API + workers
modal deploy workers/modal_api.py
modal deploy workers/modal_app.py
# frontend
cd apps/web && vercel deploy --prod
# schema (from an IPv6-capable machine)
python db/apply_migrations.py
# seed sample reports into Storage + DB
python scripts/seed_storage.py
```

## Verified

- Deterministic engine is **byte-identical** local vs deployed (counts + every signal's
  id/priority/category/title/evidence match exactly).
- Ask chat returns grounded numbers (e.g. the 22nd: 20,800 L, +2,255 L over the 18,545 L
  model expectation) via Claude Sonnet 5.
- Auth (access code → HS256 token), CORS from the Vercel origin, and the full browser
  login flow all pass.

## Follow-ups

- Verify the Resend sender domain to enable live email delivery (currently the safe
  outbox-simulate fallback + `notifications_log` audit row).
- Optional: rotate the previously-exposed OpenAI key / Gmail app password (removed from code).
- Optional: move to real Supabase Auth (profiles + RLS already in the schema) beyond the
  shared demo code.
