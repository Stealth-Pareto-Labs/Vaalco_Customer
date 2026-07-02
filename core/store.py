"""
store.py — persistence facade.
==============================
Chooses a backend from config.STORAGE_BACKEND:

  "file"     -> the original local-JSON behaviour (delegates to intelligence.py).
  "supabase" -> Postgres (analysis_runs, signals, daily_records, raw_reports,
                notifications_log) via a direct connection with the service role.

The deterministic core (intelligence.run(), signals, analysis) is unchanged —
it produces run objects; this module decides where they are stored. API and
workers call these functions; nothing here computes analysis.
"""

import json
import datetime

import config
import intelligence

# Seeded baseline IDs (see db/migrations/0002_seed.sql). Multi-vessel lookups
# resolve by code; these are the defaults for the single-vessel demo.
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-0000000000a1"
DEFAULT_VESSEL_ID = "00000000-0000-0000-0000-0000000000b1"


def _supabase() -> bool:
    return config.STORAGE_BACKEND == "supabase"


def _pg():
    import psycopg
    return psycopg.connect(config.SUPABASE_DB_URL, connect_timeout=15)


# ---------------------------------------------------------------------------
# Vessel resolution
# ---------------------------------------------------------------------------
def resolve_vessel(code=None):
    """Return (tenant_id, vessel_id) for a vessel code, defaulting to the seed."""
    if not _supabase() or not code:
        return DEFAULT_TENANT_ID, DEFAULT_VESSEL_ID
    with _pg() as c:
        row = c.execute(
            "select tenant_id, id from public.vessels where code = %s limit 1", (code,)
        ).fetchone()
    if row:
        return str(row[0]), str(row[1])
    return DEFAULT_TENANT_ID, DEFAULT_VESSEL_ID


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------
def save_run(run_obj, vessel_id=DEFAULT_VESSEL_ID, tenant_id=DEFAULT_TENANT_ID):
    """Persist a run object. File backend keeps the original JSON history."""
    if not _supabase():
        return intelligence.save_run(run_obj)

    run_id = run_obj["run_id"]
    counts = run_obj.get("counts", {})
    signals_list = run_obj.get("signals", [])
    headline = (signals_list or [{}])[0].get("title", "No signals")
    with _pg() as c, c.transaction():
        row = c.execute(
            """insert into public.analysis_runs
                 (tenant_id, vessel_id, run_id, trigger, as_of, headline,
                  executive_summary, reports_loaded, counts, payload, generated_at)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, coalesce(%s, now()))
               on conflict (vessel_id, run_id) do update set
                  trigger=excluded.trigger, as_of=excluded.as_of,
                  headline=excluded.headline, executive_summary=excluded.executive_summary,
                  reports_loaded=excluded.reports_loaded, counts=excluded.counts,
                  payload=excluded.payload
               returning id""",
            (tenant_id, vessel_id, run_id, run_obj.get("trigger"),
             run_obj.get("as_of"), headline, run_obj.get("executive_summary"),
             run_obj.get("reports_loaded"), json.dumps(counts),
             json.dumps(run_obj, default=str), run_obj.get("generated_at")),
        ).fetchone()
        run_uuid = row[0]
        c.execute("delete from public.signals where run_id = %s", (run_uuid,))
        for s in signals_list:
            c.execute(
                """insert into public.signals
                     (tenant_id, vessel_id, run_id, priority, category, title,
                      explanation, evidence, next_steps, probe)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (tenant_id, vessel_id, run_uuid, s.get("priority"), s.get("category"),
                 s.get("title"), s.get("explanation") or s.get("summary"),
                 json.dumps(s.get("evidence", [])), json.dumps(s.get("next_steps", [])),
                 s.get("probe")),
            )
    return run_id


def list_runs(vessel_id=DEFAULT_VESSEL_ID, limit=50):
    if not _supabase():
        return intelligence.list_runs()
    with _pg() as c:
        rows = c.execute(
            """select run_id, generated_at, trigger, as_of, headline, counts
                 from public.analysis_runs
                where vessel_id = %s order by generated_at desc limit %s""",
            (vessel_id, limit),
        ).fetchall()
    return [{
        "run_id": r[0],
        "generated_at": r[1].isoformat() if isinstance(r[1], datetime.datetime) else r[1],
        "trigger": r[2], "as_of": r[3], "headline": r[4],
        "counts": r[5] or {},
    } for r in rows]


def load_run(run_id, vessel_id=DEFAULT_VESSEL_ID):
    if not _supabase():
        return intelligence.load_run(run_id)
    with _pg() as c:
        row = c.execute(
            "select payload from public.analysis_runs where vessel_id=%s and run_id=%s limit 1",
            (vessel_id, run_id),
        ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Daily records + raw reports (used by the ingestion workers)
# ---------------------------------------------------------------------------
def upsert_daily_record(record, raw_report_id=None,
                        vessel_id=DEFAULT_VESSEL_ID, tenant_id=DEFAULT_TENANT_ID):
    if not _supabase():
        return None
    with _pg() as c, c.transaction():
        c.execute(
            """insert into public.daily_records
                 (tenant_id, vessel_id, raw_report_id, report_date, fuel_l, dp_hours, resid_l, payload)
               values (%s,%s,%s,%s,%s,%s,%s,%s)
               on conflict (vessel_id, report_date) do update set
                 raw_report_id=excluded.raw_report_id, fuel_l=excluded.fuel_l,
                 dp_hours=excluded.dp_hours, resid_l=excluded.resid_l, payload=excluded.payload""",
            (tenant_id, vessel_id, raw_report_id, record.get("date"),
             record.get("fuel_L"), record.get("dp_hours"), record.get("resid_L"),
             json.dumps(record, default=str)),
        )


def record_raw_report(source_file, storage_path, file_hash, report_date=None,
                      status="parsed", error=None,
                      vessel_id=DEFAULT_VESSEL_ID, tenant_id=DEFAULT_TENANT_ID):
    if not _supabase():
        return None
    with _pg() as c, c.transaction():
        row = c.execute(
            """insert into public.raw_reports
                 (tenant_id, vessel_id, report_date, source_file, storage_path, file_hash, status, error)
               values (%s,%s,%s,%s,%s,%s,%s,%s)
               on conflict (vessel_id, file_hash) do update set
                 status=excluded.status, error=excluded.error, report_date=excluded.report_date
               returning id""",
            (tenant_id, vessel_id, report_date, source_file, storage_path,
             file_hash, status, error),
        ).fetchone()
    return str(row[0]) if row else None


def log_notification(channel, recipients, status, detail=None, run_id=None,
                     vessel_id=DEFAULT_VESSEL_ID, tenant_id=DEFAULT_TENANT_ID):
    if not _supabase():
        return None
    run_uuid = None
    with _pg() as c, c.transaction():
        if run_id:
            r = c.execute(
                "select id from public.analysis_runs where vessel_id=%s and run_id=%s",
                (vessel_id, run_id)).fetchone()
            run_uuid = r[0] if r else None
        c.execute(
            """insert into public.notifications_log
                 (tenant_id, vessel_id, run_id, channel, recipients, status, detail)
               values (%s,%s,%s,%s,%s,%s,%s)""",
            (tenant_id, vessel_id, run_uuid, channel,
             json.dumps(recipients, default=str), status, detail),
        )
