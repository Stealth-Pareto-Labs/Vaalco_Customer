"""
main.py — FastAPI backend for the VAALCO Fuel Intelligence Platform.
====================================================================
Wraps the deterministic core (unchanged) behind an async HTTP API:

  POST /auth/login          shared-access-code -> Bearer token
  GET  /health              liveness
  GET  /status              data state + provider (for the UI status dot)
  POST /ask                 chatbot tool-loop -> answer + trace + charts   [auth]
  GET  /signals/latest      run the engine now (no save)                   [auth]
  POST /signals/run         run + save (optionally deliver)                [auth]
  GET  /signals/history     saved runs, newest first                       [auth]
  GET  /signals/run/{id}    one saved run                                  [auth]
  POST /signals/send        deliver a saved/fresh report                   [auth]
  GET  /signals/preview/{id}  branded HTML report (token via ?token=)
  POST /internal/refresh    reload analysis from the store (workers call this)

Data is loaded from Supabase (daily_records) at startup; in file mode it falls
back to parsing the local reports/ folder — identical to the original app.
"""

import os
import sys
import threading
from contextlib import asynccontextmanager

# --- make the shared core importable (flat module layout) ---
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO, "core"))

# --- load .env for local dev (no-op in the cloud where env vars are set) ---
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_REPO, ".env"))
except Exception:
    pass

from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

import config              # noqa: E402
import analysis            # noqa: E402
import claude_client       # noqa: E402
import intelligence        # noqa: E402
import report as report_mod  # noqa: E402
import notify              # noqa: E402
import store               # noqa: E402
import auth                # local module (apps/api/auth.py)

_lock = threading.Lock()
_state = {"days": 0}


def refresh_data():
    """(Re)load day records into the analysis core from the active backend."""
    with _lock:
        recs = store.load_daily_records()
        if recs is None:                       # file mode -> parse the folder
            import parser
            recs = parser.parse_folder(config.REPORTS_DIR)
        analysis.load(recs)
        _state["days"] = analysis.day_count()
    return _state["days"]


def ensure_loaded():
    """Lazy self-heal: load data if this (possibly cold) container has none.
    Makes every worker correct regardless of ASGI lifespan timing."""
    if analysis.day_count() == 0:
        try:
            refresh_data()
        except Exception as e:
            print(f"  ! ensure_loaded failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        refresh_data()
    except Exception as e:      # never block startup on data load
        print(f"  ! initial data load failed: {e}")
    yield


app = FastAPI(title="VAALCO Fuel Intelligence API", version="1.0.0", lifespan=lifespan)

_origins = [o.strip() for o in os.environ.get("FRONTEND_ORIGIN", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------
def require_auth(authorization: str = Header(default="")):
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    data = auth.verify_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return data


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class LoginBody(BaseModel):
    code: str


class AskBody(BaseModel):
    message: str
    history: list = []


class RunBody(BaseModel):
    trigger: str = "manual"
    deliver: bool = False


class SendBody(BaseModel):
    run_id: str | None = None


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"ok": True, "provider": config.LLM_PROVIDER, "model": config.MODEL}


@app.get("/status")
def status():
    ensure_loaded()
    return {
        "api_key": config.api_key_present(),
        "provider": config.LLM_PROVIDER,
        "days": analysis.day_count(),
        "new_reports": [],
    }


@app.post("/auth/login")
def login(body: LoginBody):
    if not auth.check_access_code(body.code):
        raise HTTPException(status_code=401, detail="Invalid access code")
    return {"token": auth.issue_token(), "expires_in": auth._TTL_SECONDS}


# ---------------------------------------------------------------------------
# Ask (chatbot)
# ---------------------------------------------------------------------------
@app.post("/ask")
def ask(body: AskBody, user=Depends(require_auth)):
    ensure_loaded()
    return claude_client.answer_question(body.message, body.history)


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------
@app.get("/signals/latest")
def signals_latest(user=Depends(require_auth)):
    ensure_loaded()
    return intelligence.run(trigger="view: console open")


@app.post("/signals/run")
def signals_run(body: RunBody, user=Depends(require_auth)):
    ensure_loaded()
    run = intelligence.run(trigger=body.trigger)
    store.save_run(run)
    delivery = notify.deliver(run) if body.deliver else None
    return {"run_id": run["run_id"], "run": run, "delivery": delivery}


@app.get("/signals/history")
def signals_history(user=Depends(require_auth)):
    return store.list_runs()


@app.get("/signals/run/{run_id}")
def signals_get(run_id: str, user=Depends(require_auth)):
    run = store.load_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.post("/signals/send")
def signals_send(body: SendBody, user=Depends(require_auth)):
    ensure_loaded()
    run = store.load_run(body.run_id) if body.run_id else None
    if not run:
        run = intelligence.run(trigger="manual: send from console")
        store.save_run(run)
    delivery = notify.deliver(run)
    return {"run_id": run["run_id"], "delivery": delivery}


@app.get("/signals/preview/{run_id}", response_class=HTMLResponse)
def signals_preview(run_id: str, token: str = ""):
    # Browser navigation can't send an Authorization header, so preview accepts
    # the token as a query param.
    if not auth.verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    run = store.load_run(run_id)
    if not run:
        run = intelligence.run(trigger="preview")
        store.save_run(run)
    return HTMLResponse(report_mod.render_html(run))


# ---------------------------------------------------------------------------
# Internal (workers) — reload analysis after new ingestion
# ---------------------------------------------------------------------------
@app.post("/internal/refresh")
def internal_refresh(x_worker_secret: str = Header(default="")):
    if x_worker_secret != (config.SESSION_SECRET or ""):
        raise HTTPException(status_code=403, detail="forbidden")
    return {"days": refresh_data()}
