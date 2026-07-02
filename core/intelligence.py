"""
intelligence.py
===============
Orchestrates one full INTELLIGENCE RUN:

    1. signals.detect_all()   -> deterministic findings + hard evidence  (CODE)
    2. the model              -> executive summary + polished wording +
                                 recommended next steps for each signal   (LANGUAGE)
    3. assemble a run object  -> saved to reports_out/ as JSON, rendered to
                                 HTML/text/SMS by report.py, delivered by notify.py

TRUST BOUNDARY (the same one the whole system is built on):
  - The model MAY: write the executive summary, rephrase each concern for a
    busy manager, and propose concrete next steps.
  - The model MAY NOT: invent, change, round, or add any number. Every figure
    it uses must already be present in the signal's `evidence`. Severity and
    detection are decided in code (signals.py), never by the model.

If the model is unavailable (no API key, or the call fails), the run still
completes: it falls back to the deterministic summary and a default set of
next steps, so the pipeline never blocks on the model.
"""

import os
import json
import time
import datetime

import config
import signals
import llm


# ---------------------------------------------------------------------------
# The model call — structured JSON in, structured JSON out
# ---------------------------------------------------------------------------
_SYNTH_SYSTEM = """You are the fleet intelligence analyst for offshore support vessels operated by {operator}. A deterministic analysis engine has ALREADY scanned today's vessel data and decided which issues matter and how severe each is. Your job is ONLY to communicate them well to a busy marine superintendent and to management.

STRICT RULES:
1. You must NOT invent, change, round, or add any number, date, machine, or fact. Every figure you write must already appear in the evidence you are given. If a number is not in the evidence, do not state it.
2. You must NOT change any priority. The engine's priority (low/medium/high) is final.
3. For each signal, write:
   - "explanation": 1-2 sentences telling the manager what this means operationally and why it matters, in plain English. Ground it in the evidence.
   - "next_steps": 2-4 short, concrete, actionable bullet strings the crew or office can act on. Be specific and practical for vessel operations. No preamble.
4. Also write an "executive_summary": 2-4 sentences a superintendent can read in ten seconds — what today's headline is, what needs attention first, and the overall posture. Lead with the most important thing.
5. Plain, direct, professional maritime tone. No hype, no filler, no apologies. Do not restate every number; interpret it.

Return ONLY valid JSON, no markdown, no code fences, in exactly this shape:
{{
  "executive_summary": "string",
  "signals": [
    {{"id": "the signal id", "explanation": "string", "next_steps": ["string", "string"]}}
  ]
}}
Include one entry in "signals" for every signal id you are given, in the same order."""


def _default_next_steps(sig):
    """Deterministic fallback next-steps by category, used if the model is
    unavailable. Kept practical and safe."""
    cat = sig["category"]
    base = {
        "maintenance": [
            "Schedule the lube-oil service at the next safe operational window.",
            "Confirm spares and lubricant stock are aboard before the service date.",
            "Log the planned service date against this machine in the maintenance system.",
        ],
        "fuel": [
            "Review the day's activity log to confirm the operational reason for the excess.",
            "If unexplained by workload, inspect for fouling, trim, or engine-load inefficiency.",
            "Track whether the deviation persists over the next reports.",
        ],
        "dp": [
            "Compare vessel loading, heading and thruster use between the best and worst DP days.",
            "Share the most efficient day's setup with the bridge team as a reference.",
        ],
        "engine": [
            "Arrange for engine telemetry to be captured from sensors rather than entered by hand.",
            "Until then, treat engine-condition reporting as unverified.",
        ],
        "fluid": [
            "Plan the offload or resupply before the level reaches an operational limit.",
            "Confirm the balance against a physical sounding.",
        ],
        "hse": [
            "Ensure the event has been logged and investigated per the HSE procedure.",
            "Brief the crew at the next toolbox meeting.",
        ],
    }
    return base.get(cat, ["Review this item and assign an owner."])


def _call_model(payload_signals, context):
    """Ask the model for summary + explanations + next steps. Returns dict or None."""
    if not config.api_key_present():
        return None

    # We hand the model ONLY the fields it is allowed to use: id, priority,
    # title, summary, evidence. It never sees code internals.
    slim = [{
        "id": s["id"], "priority": s["priority"], "category": s["category"],
        "title": s["title"], "summary": s["summary"], "evidence": s["evidence"],
    } for s in payload_signals]

    user = {
        "context": context,
        "signals": slim,
    }
    system = _SYNTH_SYSTEM.format(operator=config.OPERATOR_NAME)
    # Transport is provider-abstracted (llm.py); the prompt and the strict
    # JSON contract above are unchanged. Returns a dict or None (fallback).
    return llm.complete_json(system, json.dumps(user), config.INTEL_MAX_TOKENS)


# ---------------------------------------------------------------------------
# Assemble a full run
# ---------------------------------------------------------------------------
def _deterministic_summary(detection):
    c = detection["counts"]
    if c["total"] == 0:
        return ("No signals were raised for this reporting window. Fuel, maintenance, "
                "DP efficiency and HSE are all within their configured thresholds.")
    parts = []
    if c["high"]:
        parts.append(f"{c['high']} high-priority")
    if c["medium"]:
        parts.append(f"{c['medium']} medium")
    if c["low"]:
        parts.append(f"{c['low']} low")
    headline = detection["signals"][0]
    return (f"{', '.join(parts)} signal(s) for {detection['vessel']} as of "
            f"{detection['as_of']}. Attend first to: {headline['title'].lower()}.")


def run(trigger="manual"):
    """Perform a full intelligence run against the current data store."""
    detection = signals.detect_all()
    ts = datetime.datetime.now()
    run_id = ts.strftime("%Y%m%dT%H%M%S")

    if detection.get("error"):
        return {
            "run_id": run_id, "generated_at": ts.isoformat(timespec="seconds"),
            "trigger": trigger, "error": detection["error"],
            "counts": detection["counts"], "signals": [],
            "executive_summary": detection["error"],
            "vessel": config.VESSEL_LABEL, "field": config.FIELD_LABEL,
        }

    context = {
        "operator": config.OPERATOR_NAME,
        "vessel": detection["vessel"],
        "field": detection["field"],
        "as_of": detection["as_of"],
        "date_range": detection["date_range"],
        "reports_loaded": detection["reports_loaded"],
        "counts": detection["counts"],
    }

    model_out = _call_model(detection["signals"], context)
    used_model = model_out is not None

    # Merge model prose onto the deterministic signals (evidence is untouched)
    by_id = {}
    if used_model:
        for entry in (model_out.get("signals") or []):
            if isinstance(entry, dict) and entry.get("id"):
                by_id[entry["id"]] = entry

    enriched = []
    for s in detection["signals"]:
        m = by_id.get(s["id"], {})
        explanation = (m.get("explanation") or "").strip() or s["summary"]
        next_steps = m.get("next_steps") if isinstance(m.get("next_steps"), list) else None
        if not next_steps:
            next_steps = _default_next_steps(s)
        enriched.append({**s, "explanation": explanation, "next_steps": next_steps})

    exec_summary = ""
    if used_model:
        exec_summary = (model_out.get("executive_summary") or "").strip()
    if not exec_summary:
        exec_summary = _deterministic_summary(detection)

    return {
        "run_id": run_id,
        "generated_at": ts.isoformat(timespec="seconds"),
        "trigger": trigger,
        "vessel": detection["vessel"],
        "field": detection["field"],
        "operator": config.OPERATOR_NAME,
        "as_of": detection["as_of"],
        "date_range": detection["date_range"],
        "reports_loaded": detection["reports_loaded"],
        "counts": detection["counts"],
        "executive_summary": exec_summary,
        "narrated_by_model": used_model,
        "signals": enriched,
    }


# ---------------------------------------------------------------------------
# Persistence — save/load run history for the Signals console
# ---------------------------------------------------------------------------
def _out_dir():
    os.makedirs(config.REPORTS_OUT_DIR, exist_ok=True)
    return config.REPORTS_OUT_DIR


def save_run(run_obj):
    """Persist a run as JSON (and its rendered HTML alongside it)."""
    d = _out_dir()
    path = os.path.join(d, f"run_{run_obj['run_id']}.json")
    with open(path, "w") as fh:
        json.dump(run_obj, fh, indent=2, default=str)
    return path


def list_runs():
    """Return saved runs, newest first, as lightweight summaries."""
    d = _out_dir()
    runs = []
    for name in os.listdir(d):
        if name.startswith("run_") and name.endswith(".json"):
            try:
                with open(os.path.join(d, name)) as fh:
                    r = json.load(fh)
                runs.append({
                    "run_id": r.get("run_id"),
                    "generated_at": r.get("generated_at"),
                    "trigger": r.get("trigger"),
                    "as_of": r.get("as_of"),
                    "counts": r.get("counts", {}),
                    "headline": (r.get("signals") or [{}])[0].get("title", "No signals"),
                })
            except (json.JSONDecodeError, OSError):
                continue
    runs.sort(key=lambda x: x.get("generated_at", ""), reverse=True)
    return runs


def load_run(run_id):
    path = os.path.join(_out_dir(), f"run_{run_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)
