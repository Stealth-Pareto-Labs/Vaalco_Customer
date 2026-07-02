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
import signals             # noqa: E402
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


class SettingsBody(BaseModel):
    emails: list[str] = []
    digest_enabled: bool = True
    digest_time: str = "08:00"
    timezone: str = "Africa/Libreville"
    critical_immediate: bool = True


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
# Dashboard — aggregate every deterministic series for the charts.
# Pure aggregation over the existing analysis tools; no analysis logic changes.
# ---------------------------------------------------------------------------
def _is_waste_fluid(name: str) -> bool:
    n = name.lower()
    return any(w in n for w in ("bilge", "sludge", "dirty", "waste", "slop"))


def build_dashboard():
    ov = analysis.dataset_overview()
    if ov.get("error"):
        return {"error": ov["error"], "reports_loaded": 0}

    model = analysis.model_summary()
    price = config.MGO_PRICE_PER_M3

    # Per-day fuel series (actual vs model, deviation, $ impact, DP efficiency)
    fuel_series = []
    for date in ov.get("dates_present", []):
        d = analysis.explain_day(date)
        if d.get("error"):
            continue
        dp = d.get("dp_hours")
        fuel_series.append({
            "date": d["date"],
            "actual_L": d["fuel_actual_L"],
            "expected_L": d["expected_L"],
            "deviation_L": d["deviation_L"],
            "cost_usd": d["deviation_cost_usd"],
            "dp_hours": dp,
            "L_per_dp_hour": round(d["fuel_actual_L"] / dp) if dp else None,
        })

    net_dev = sum(r["deviation_L"] for r in fuel_series)
    net_cost = sum(r["cost_usd"] for r in fuel_series)
    fov = analysis.fuel_overview()

    dpe = analysis.dp_efficiency()
    maint = analysis.maintenance_status()
    machines = [m for m in maint.get("machines", []) if m.get("hours_remaining") is not None]
    machines.sort(key=lambda m: m["hours_remaining"])

    fluids_raw = analysis.fluid_status().get("fluids", {})
    fluids = []
    for name, f in fluids_raw.items():
        bal, cons = f.get("balance"), f.get("consumed")
        waste = _is_waste_fluid(name)
        dte = (round(bal / cons) if (not waste and isinstance(bal, (int, float))
                                     and isinstance(cons, (int, float)) and cons > 0) else None)
        fluids.append({"name": name, "balance": bal, "consumed": cons,
                       "unit": f.get("unit"), "days_to_empty": dte, "is_waste": waste})

    eng = analysis.engine_health()
    hse = analysis.hse_status()
    det = signals.detect_all()

    return {
        "as_of": ov.get("date_range", "").split(" to ")[-1],
        "vessel": ov.get("vessel"), "field": ov.get("field"),
        "reports_loaded": ov.get("reports_loaded", 0),
        "date_range": ov.get("date_range"),
        "mgo_price_per_m3": price,
        "model": {"base_L": model.get("base_L"), "rate": model.get("rate"), "sd": model.get("sd")},
        "kpis": {
            "mean_daily_fuel_L": fov.get("mean_daily_fuel_L"),
            "mean_daily_cost_usd": fov.get("mean_daily_cost_usd"),
            "annualised_cost_usd": fov.get("annualised_cost_usd"),
            "net_deviation_L": net_dev,
            "net_cost_impact_usd": net_cost,
            "worst_day": fov.get("worst_day"),
            "worst_day_deviation_L": fov.get("worst_day_deviation_L"),
        },
        "signal_counts": det.get("counts", {}),
        "fuel_series": fuel_series,
        "dp_efficiency": {
            "days": dpe.get("days", []) if not dpe.get("error") else [],
            "best": dpe.get("best_day"), "worst": dpe.get("worst_day"),
            "spread_percent": dpe.get("spread_percent"),
        },
        "maintenance": machines,
        "fluids": fluids,
        "engine": {
            "me1_temps": eng.get("me1_cylinder_temps_C", []),
            "me2_temps": eng.get("me2_cylinder_temps_C", []),
            "me1_deviation": eng.get("me1_deviation_C"),
            "me2_deviation": eng.get("me2_deviation_C"),
            "telemetry_is_static": eng.get("telemetry_is_static"),
            "note": eng.get("data_quality_note"),
        } if not eng.get("error") else None,
        "hse": {
            "tallies": hse.get("tallies", {}),
            "near_misses": hse.get("near_misses_to_date"),
        } if not hse.get("error") else None,
    }


@app.get("/dashboard")
def dashboard(user=Depends(require_auth)):
    ensure_loaded()
    return build_dashboard()


# ---------------------------------------------------------------------------
# Settings — alert recipient email
# ---------------------------------------------------------------------------
_SETTINGS_DEFAULTS = {
    "emails": [], "digest_enabled": True, "digest_time": "08:00",
    "timezone": "Africa/Libreville", "critical_immediate": True,
}


def _read_settings():
    cfg = store.get_setting("alert_config") or {}
    # migrate legacy single-list if present and no emails yet
    if not cfg.get("emails"):
        legacy = store.get_setting("alert_recipients") or []
        cfg["emails"] = [r.get("email") for r in legacy if r.get("email")]
    return {k: cfg.get(k, v) for k, v in _SETTINGS_DEFAULTS.items()}


@app.get("/settings")
def get_settings(user=Depends(require_auth)):
    return _read_settings()


@app.post("/settings")
def save_settings(body: SettingsBody, user=Depends(require_auth)):
    clean_emails = []
    for e in body.emails:
        e = (e or "").strip()
        if not e:
            continue
        if "@" not in e or "." not in e.split("@")[-1]:
            raise HTTPException(status_code=400, detail=f"Invalid email: {e}")
        if e not in clean_emails:
            clean_emails.append(e)
    # validate timezone
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(body.timezone)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timezone")
    # validate HH:MM
    try:
        hh, mm = body.digest_time.split(":")
        assert 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid digest time (use HH:MM)")

    cfg = store.get_setting("alert_config") or {}
    cfg.update({
        "emails": clean_emails,
        "digest_enabled": body.digest_enabled,
        "digest_time": body.digest_time,
        "timezone": body.timezone,
        "critical_immediate": body.critical_immediate,
    })
    store.set_setting("alert_config", cfg)
    return _read_settings()


# ---------------------------------------------------------------------------
# Internal (workers) — reload analysis after new ingestion
# ---------------------------------------------------------------------------
@app.post("/internal/refresh")
def internal_refresh(x_worker_secret: str = Header(default="")):
    if x_worker_secret != (config.SESSION_SECRET or ""):
        raise HTTPException(status_code=403, detail="forbidden")
    return {"days": refresh_data()}
