"""
ingest_core.py — the ingestion pipeline, independent of Modal.
==============================================================
One report file -> parsed -> stored -> analyzed -> intelligence run -> notify.
Kept free of any Modal dependency so it can be unit-tested locally and simply
wrapped by workers/modal_app.py in the cloud.

Flow (per file):
  1. download the .xlsx from Supabase Storage (raw-reports bucket)
  2. parser.parse_one()                      (deterministic core, unchanged)
  3. record raw_reports row (idempotent on file hash)
  4. rebuild the vessel's dataset + upsert the normalized daily_record
  5. intelligence.run() -> save_run() -> notify.deliver()   (optional per call)
  6. best-effort: ping the API to refresh its in-memory analysis
"""

import os
import sys
import json
import hashlib
import tempfile
import urllib.request
import urllib.error
from urllib.parse import quote

# Make the shared core importable both locally and inside the Modal image.
for _p in ("/root/core",
           os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core")):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import config
import parser
import analysis
import intelligence
import store
import notify


# ---------------------------------------------------------------------------
# Supabase Storage helpers (REST, service-role, urllib only)
# ---------------------------------------------------------------------------
def _storage_url(path):
    return f"{config.SUPABASE_URL}/storage/v1/{path}"


def _auth_headers(extra=None):
    h = {"Authorization": f"Bearer {config.SUPABASE_SERVICE_ROLE_KEY}"}
    if extra:
        h.update(extra)
    return h


def download_object(bucket, path) -> bytes:
    req = urllib.request.Request(
        _storage_url(f"object/{bucket}/{quote(path)}"), headers=_auth_headers(), method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def upload_object(bucket, path, data: bytes,
                  content_type="application/octet-stream") -> dict:
    req = urllib.request.Request(
        _storage_url(f"object/{bucket}/{quote(path)}"), data=data, method="POST",
        headers=_auth_headers({"Content-Type": content_type, "x-upsert": "true"}))
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read() or b"{}")


def list_objects(bucket, prefix="") -> list:
    body = json.dumps({"prefix": prefix, "limit": 1000,
                       "sortBy": {"column": "name", "order": "asc"}}).encode()
    req = urllib.request.Request(
        _storage_url(f"object/list/{bucket}"), data=body, method="POST",
        headers=_auth_headers({"Content-Type": "application/json"}))
    with urllib.request.urlopen(req, timeout=60) as resp:
        items = json.loads(resp.read() or b"[]")
    return [it["name"] for it in items if it.get("name")]


# ---------------------------------------------------------------------------
# API refresh (so the always-on API reloads new data)
# ---------------------------------------------------------------------------
def _ping_api_refresh():
    base = os.environ.get("API_BASE_URL", "").rstrip("/")
    if not base:
        return
    try:
        req = urllib.request.Request(
            f"{base}/internal/refresh", data=b"{}", method="POST",
            headers={"Content-Type": "application/json",
                     "X-Worker-Secret": config.SESSION_SECRET or ""})
        urllib.request.urlopen(req, timeout=20).read()
    except (urllib.error.URLError, OSError):
        pass


# ---------------------------------------------------------------------------
# Core ingestion
# ---------------------------------------------------------------------------
def _parse_bytes(data: bytes, source_file: str):
    """Write bytes to a temp .xlsx and parse with the deterministic core."""
    with tempfile.NamedTemporaryFile(suffix="_" + os.path.basename(source_file),
                                     delete=False) as tf:
        tf.write(data)
        tmp = tf.name
    try:
        record = parser.parse_one(tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    return record


def ingest_bytes(data: bytes, source_file: str, storage_path: str,
                 vessel_code="NZ-MCT", run_intelligence=True, deliver=False):
    """Ingest one report given its bytes. Returns a summary dict."""
    file_hash = hashlib.sha256(data).hexdigest()
    tenant_id, vessel_id = store.resolve_vessel(vessel_code)

    record = _parse_bytes(data, source_file)

    raw_id = store.record_raw_report(
        source_file=source_file, storage_path=storage_path, file_hash=file_hash,
        report_date=record.get("date"), status="parsed",
        vessel_id=vessel_id, tenant_id=tenant_id)

    # Rebuild the vessel's full dataset so the fuel model + residuals are exact,
    # then persist the normalized (now enriched) day record.
    existing = store.load_daily_records(vessel_id) or []
    combined = [r for r in existing if r.get("date") != record.get("date")]
    combined.append(record)
    analysis.load(combined)   # refits the model + mutates every record's resid_L
    # Persist ALL days so the model-derived columns stay consistent as the
    # global fuel model shifts with each new report (raw_report_id is preserved
    # for existing rows via coalesce; set only for the newly-ingested day).
    for rec in combined:
        rid = raw_id if rec.get("date") == record.get("date") else None
        store.upsert_daily_record(rec, raw_report_id=rid,
                                  vessel_id=vessel_id, tenant_id=tenant_id)

    result = {"date": record.get("date"), "file_hash": file_hash,
              "source_file": source_file, "days_loaded": analysis.day_count()}

    if run_intelligence:
        run = intelligence.run(trigger=f"auto: new report {record.get('date')}")
        store.save_run(run, vessel_id=vessel_id, tenant_id=tenant_id)
        result["run_id"] = run["run_id"]
        result["counts"] = run["counts"]
        if deliver:
            result["delivery"] = notify.deliver(run)
        _ping_api_refresh()

    return result


def ingest_object(storage_path, vessel_code="NZ-MCT",
                  run_intelligence=True, deliver=False):
    """Ingest a file already present in the raw-reports bucket."""
    data = download_object(config.SUPABASE_BUCKET_RAW, storage_path)
    return ingest_bytes(data, os.path.basename(storage_path), storage_path,
                        vessel_code=vessel_code,
                        run_intelligence=run_intelligence, deliver=deliver)


def seed_sample_reports(local_dir, vessel_code="NZ-MCT", deliver=False):
    """Upload every sample .xlsx to Storage and ingest them, then run one final
    intelligence pass. Populates the DB for a full cloud demo."""
    files = sorted(f for f in os.listdir(local_dir) if f.endswith(".xlsx"))
    summaries = []
    for i, name in enumerate(files):
        with open(os.path.join(local_dir, name), "rb") as fh:
            data = fh.read()
        storage_path = name
        upload_object(config.SUPABASE_BUCKET_RAW, storage_path, data,
                      content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        last = (i == len(files) - 1)
        summaries.append(ingest_bytes(
            data, name, storage_path, vessel_code=vessel_code,
            run_intelligence=last, deliver=(deliver and last)))
    return {"ingested": len(files), "final": summaries[-1] if summaries else None}
