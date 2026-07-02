"""
modal_app.py — Modal deployment of the ingestion/analysis worker fleet.
=======================================================================
Wraps workers/ingest_core.py so report processing runs as elastic Modal
functions: one invocation per file, fanning out across thousands of files.

Deploy:
    modal deploy workers/modal_app.py           # deploys functions + web endpoint
Trigger a single file (already in the raw-reports bucket):
    modal run workers/modal_app.py::ingest_report --storage-path "NZ-... .xlsx"
Seed the sample reports from the repo:
    modal run workers/modal_app.py::seed

Secrets: expects a Modal secret named "vaalco-secrets" carrying the same env
vars as .env (ANTHROPIC_API_KEY, SUPABASE_*, RESEND_*, ACCESS_CODE,
SESSION_SECRET, STORAGE_BACKEND=supabase, ...). Create it with:
    bash infra/modal_secret.sh
"""

import modal

app = modal.App("vaalco-workers")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("openpyxl>=3.1", "psycopg[binary]>=3.2",
                 "fastapi[standard]>=0.115", "tzdata>=2024.1")
    .add_local_dir("core", remote_path="/root/core")
    .add_local_dir("workers", remote_path="/root/workers")
)

secrets = [modal.Secret.from_name("vaalco-secrets")]
COMMON = dict(image=image, secrets=secrets, timeout=900)


def _ic():
    import sys
    for p in ("/root/core", "/root/workers"):
        if p not in sys.path:
            sys.path.insert(0, p)
    import ingest_core
    return ingest_core


# ---------------------------------------------------------------------------
# One file -> full pipeline. This is the unit that fans out.
# ---------------------------------------------------------------------------
@app.function(**COMMON)
def ingest_report(storage_path: str, vessel_code: str = "NZ-MCT",
                  run_intelligence: bool = True, deliver: bool = True):
    ic = _ic()
    return ic.ingest_object(storage_path, vessel_code=vessel_code,
                            run_intelligence=run_intelligence, deliver=deliver)


# ---------------------------------------------------------------------------
# Fan-out: process many files in parallel (the "thousands of files" story).
# ---------------------------------------------------------------------------
@app.function(**COMMON)
def ingest_many(vessel_code: str = "NZ-MCT", prefix: str = "", deliver: bool = False):
    ic = _ic()
    paths = ic.list_objects(ic.config.SUPABASE_BUCKET_RAW, prefix=prefix)
    args = [(p, vessel_code, True, deliver) for p in paths]
    results = list(ingest_report.starmap(args))
    return {"processed": len(results), "results": results}


# ---------------------------------------------------------------------------
# Webhook endpoint — call this after a file lands in Storage (from the API or
# a Supabase Storage webhook). Body: {"storage_path": "...", "vessel_code": "..."}
# ---------------------------------------------------------------------------
@app.function(**COMMON)
@modal.fastapi_endpoint(method="POST")
def ingest_webhook(payload: dict):
    storage_path = payload.get("storage_path")
    if not storage_path:
        return {"error": "storage_path required"}
    vessel_code = payload.get("vessel_code", "NZ-MCT")
    deliver = bool(payload.get("deliver", True))
    # Run in the background so the webhook returns immediately.
    call = ingest_report.spawn(storage_path, vessel_code, True, deliver)
    return {"accepted": True, "call_id": call.object_id, "storage_path": storage_path}


# ---------------------------------------------------------------------------
# Scheduled digest — runs every 15 min; sends the report at the user's chosen
# local time (timezone-aware). Critical HIGH alerts are already delivered
# immediately at ingestion; this handles the medium/low + routine digest.
# ---------------------------------------------------------------------------
@app.function(**COMMON, schedule=modal.Cron("*/15 * * * *"))
def digest_tick():
    import sys
    for p in ("/root/core", "/root/workers"):
        if p not in sys.path:
            sys.path.insert(0, p)
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import store, analysis, intelligence, notify

    cfg = store.get_setting("alert_config") or {}
    if not cfg.get("digest_enabled", True):
        return {"skipped": "digest disabled"}
    if not [e for e in (cfg.get("emails") or []) if e]:
        return {"skipped": "no recipients"}

    tz = cfg.get("timezone", "Africa/Libreville")
    try:
        now = datetime.now(ZoneInfo(tz))
    except Exception:
        now = datetime.utcnow()
    parts = (cfg.get("digest_time", "08:00").split(":") + ["0"])[:2]
    target = int(parts[0]) * 60 + int(parts[1])
    now_mod = now.hour * 60 + now.minute
    if not (0 <= now_mod - target < 15):      # only in the 15-min window at/after the target
        return {"skipped": "outside window", "local": now.strftime("%H:%M %Z")}
    today = now.strftime("%Y-%m-%d")
    if cfg.get("last_digest_date") == today:
        return {"skipped": "already sent today"}

    analysis.load(store.load_daily_records() or [])
    run = intelligence.run(trigger="scheduled digest", lang="en")
    store.save_run(run)
    # email each recipient the digest in their own language
    notify.deliver_localized(
        lambda lang: intelligence.run(trigger="scheduled digest", lang=lang),
        cache={"en": run})
    cfg["last_digest_date"] = today
    store.set_setting("alert_config", cfg)
    return {"sent": True, "run_id": run["run_id"], "local": now.strftime("%H:%M %Z")}


# ---------------------------------------------------------------------------
# Local entrypoint: fan out over every file already in the raw-reports bucket
# (upload sample files first with `python scripts/seed_storage.py`).
# ---------------------------------------------------------------------------
@app.local_entrypoint()
def run_all(deliver: bool = False):
    print(ingest_many.remote(deliver=deliver))
