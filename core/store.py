"""
store.py — persistence facade.
==============================
Chooses a backend from config.STORAGE_BACKEND:

  "file"     -> the original local-JSON behaviour (delegates to intelligence.py).
  "supabase" -> Postgres via the Supabase PostgREST HTTP API (service role).

Why HTTP (PostgREST) and not a direct Postgres socket: Supabase's direct DB
host is IPv6-only and its pooler is not enabled for this project, so serverless
runtimes (Modal, IPv4) can't open a socket. The REST API is served over the
same IPv4 HTTPS host as the project and works everywhere. Schema migrations
(DDL) are applied separately via db/apply_migrations.py from a dev machine.

The deterministic core (intelligence.run(), signals, analysis) is unchanged —
it produces run objects; this module decides where they are stored.
"""

import json
import urllib.request
import urllib.error

import config
import intelligence

# Seeded baseline IDs (see db/migrations/0002_seed.sql).
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-0000000000a1"
DEFAULT_VESSEL_ID = "00000000-0000-0000-0000-0000000000b1"


def _supabase() -> bool:
    return config.STORAGE_BACKEND == "supabase"


# ---------------------------------------------------------------------------
# PostgREST HTTP helpers (service role -> bypasses RLS)
# ---------------------------------------------------------------------------
def _rest_base():
    return f"{config.SUPABASE_URL}/rest/v1"


def _headers(extra=None):
    key = config.SUPABASE_SERVICE_ROLE_KEY
    h = {"apikey": key, "Authorization": f"Bearer {key}",
         "Content-Type": "application/json", "Accept": "application/json"}
    if extra:
        h.update(extra)
    return h


def _request(method, path, params="", body=None, prefer=None):
    url = f"{_rest_base()}/{path}"
    if params:
        url += "?" + params
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers=_headers({"Prefer": prefer} if prefer else None))
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else []
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise RuntimeError(f"Supabase REST {method} {path} -> {e.code}: {detail[:300]}")


def _get(path, params):
    return _request("GET", path, params=params)


def _insert(path, rows, upsert_on=None):
    prefer = "return=representation"
    params = ""
    if upsert_on:
        prefer = "resolution=merge-duplicates,return=representation"
        params = f"on_conflict={upsert_on}"
    return _request("POST", path, params=params, body=rows, prefer=prefer)


def _delete(path, params):
    return _request("DELETE", path, params=params, prefer="return=minimal")


def _clean(row):
    """Drop keys whose value is None so DB defaults apply."""
    return {k: v for k, v in row.items() if v is not None}


# ---------------------------------------------------------------------------
# Vessel resolution
# ---------------------------------------------------------------------------
def resolve_vessel(code=None):
    if not _supabase() or not code:
        return DEFAULT_TENANT_ID, DEFAULT_VESSEL_ID
    rows = _get("vessels", f"code=eq.{code}&select=tenant_id,id&limit=1")
    if rows:
        return rows[0]["tenant_id"], rows[0]["id"]
    return DEFAULT_TENANT_ID, DEFAULT_VESSEL_ID


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------
def save_run(run_obj, vessel_id=DEFAULT_VESSEL_ID, tenant_id=DEFAULT_TENANT_ID):
    if not _supabase():
        return intelligence.save_run(run_obj)

    run_id = run_obj["run_id"]
    signals_list = run_obj.get("signals", [])
    headline = (signals_list or [{}])[0].get("title", "No signals")
    row = _clean({
        "tenant_id": tenant_id, "vessel_id": vessel_id, "run_id": run_id,
        "trigger": run_obj.get("trigger"), "as_of": run_obj.get("as_of"),
        "headline": headline, "executive_summary": run_obj.get("executive_summary"),
        "reports_loaded": run_obj.get("reports_loaded"),
        "counts": run_obj.get("counts", {}), "payload": run_obj,
        "generated_at": run_obj.get("generated_at"),
    })
    created = _insert("analysis_runs", row, upsert_on="vessel_id,run_id")
    run_uuid = created[0]["id"] if created else None
    if run_uuid:
        _delete("signals", f"run_id=eq.{run_uuid}")
        sig_rows = [{
            "tenant_id": tenant_id, "vessel_id": vessel_id, "run_id": run_uuid,
            "priority": s.get("priority"), "category": s.get("category"),
            "title": s.get("title"),
            "explanation": s.get("explanation") or s.get("summary"),
            "evidence": s.get("evidence", []), "next_steps": s.get("next_steps", []),
            "probe": s.get("probe"),
        } for s in signals_list]
        if sig_rows:
            _insert("signals", sig_rows)
    return run_id


def list_runs(vessel_id=DEFAULT_VESSEL_ID, limit=50):
    if not _supabase():
        return intelligence.list_runs()
    rows = _get("analysis_runs",
                f"vessel_id=eq.{vessel_id}&order=generated_at.desc&limit={limit}"
                "&select=run_id,generated_at,trigger,as_of,headline,counts")
    return [{
        "run_id": r.get("run_id"), "generated_at": r.get("generated_at"),
        "trigger": r.get("trigger"), "as_of": r.get("as_of"),
        "headline": r.get("headline"), "counts": r.get("counts") or {},
    } for r in rows]


def load_run(run_id, vessel_id=DEFAULT_VESSEL_ID):
    if not _supabase():
        return intelligence.load_run(run_id)
    rows = _get("analysis_runs",
                f"vessel_id=eq.{vessel_id}&run_id=eq.{run_id}&select=payload&limit=1")
    return rows[0]["payload"] if rows else None


# ---------------------------------------------------------------------------
# Daily records + raw reports (ingestion workers)
# ---------------------------------------------------------------------------
def load_daily_records(vessel_id=DEFAULT_VESSEL_ID):
    if not _supabase():
        return None
    rows = _get("daily_records",
                f"vessel_id=eq.{vessel_id}&order=report_date&select=payload")
    return [r["payload"] for r in rows]


def upsert_daily_record(record, raw_report_id=None,
                        vessel_id=DEFAULT_VESSEL_ID, tenant_id=DEFAULT_TENANT_ID):
    if not _supabase():
        return None
    row = _clean({
        "tenant_id": tenant_id, "vessel_id": vessel_id,
        "raw_report_id": raw_report_id,          # omitted when None -> existing link preserved
        "report_date": record.get("date"), "fuel_l": record.get("fuel_L"),
        "dp_hours": record.get("dp_hours"), "resid_l": record.get("resid_L"),
        "payload": record,
    })
    _insert("daily_records", row, upsert_on="vessel_id,report_date")


def record_raw_report(source_file, storage_path, file_hash, report_date=None,
                      status="parsed", error=None,
                      vessel_id=DEFAULT_VESSEL_ID, tenant_id=DEFAULT_TENANT_ID):
    if not _supabase():
        return None
    row = _clean({
        "tenant_id": tenant_id, "vessel_id": vessel_id, "report_date": report_date,
        "source_file": source_file, "storage_path": storage_path,
        "file_hash": file_hash, "status": status, "error": error,
    })
    created = _insert("raw_reports", row, upsert_on="vessel_id,file_hash")
    return created[0]["id"] if created else None


def log_notification(channel, recipients, status, detail=None, run_id=None,
                     vessel_id=DEFAULT_VESSEL_ID, tenant_id=DEFAULT_TENANT_ID):
    if not _supabase():
        return None
    run_uuid = None
    if run_id:
        rows = _get("analysis_runs",
                    f"vessel_id=eq.{vessel_id}&run_id=eq.{run_id}&select=id&limit=1")
        run_uuid = rows[0]["id"] if rows else None
    row = _clean({
        "tenant_id": tenant_id, "vessel_id": vessel_id, "run_id": run_uuid,
        "channel": channel, "recipients": recipients or [],
        "status": status, "detail": detail,
    })
    _insert("notifications_log", row)
