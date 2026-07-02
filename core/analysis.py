"""
analysis.py
===========
The deterministic analysis layer — does ALL vessel math across the full report.

The model never computes here; it chooses which of these functions to call.
Every number the assistant states comes from one of these functions.

Tools now cover the whole report, not just fuel:
  fuel_overview / explain_day / dp_efficiency     — fuel & operations
  maintenance_status / machine_detail             — run-hours & servicing
  engine_health                                   — per-cylinder telemetry + data-quality
  fluid_status                                    — consumption & inventory of every fluid
  activity_log  (reads the UNSTRUCTURED narrative) — the "why" behind a day
  hse_status                                      — safety indicators
  report_summary                                  — a full one-day briefing

Holds the live in-memory data store, updated by the folder-watcher.
"""

import re
import config

_STATE = {"days": [], "model": {"base_L": 0, "rate": 0, "sd": 0}}


# ---------------------------------------------------------------------------
# Fuel model (least squares: expected fuel = base + rate * DP hours)
# ---------------------------------------------------------------------------
def _fit_fuel_model(days):
    pts = [(d["dp_hours"], d["fuel_L"]) for d in days
           if d.get("dp_hours") is not None and d.get("fuel_L")]
    n = len(pts)
    if n < 2:
        return {"base_L": 0, "rate": 0, "sd": 0}
    sx = sum(p[0] for p in pts); sy = sum(p[1] for p in pts)
    sxx = sum(p[0] ** 2 for p in pts); sxy = sum(p[0] * p[1] for p in pts)
    denom = (n * sxx - sx * sx) or 1
    rate = (n * sxy - sx * sy) / denom
    base = (sy - rate * sx) / n
    resid = [p[1] - (base + rate * p[0]) for p in pts]
    sd = (sum(r * r for r in resid) / n) ** 0.5
    return {"base_L": round(base), "rate": round(rate), "sd": round(sd)}


def _recompute():
    days = _STATE["days"]
    m = _fit_fuel_model(days)
    for d in days:
        dp = d.get("dp_hours") or 0
        d["expected_L"] = round(m["base_L"] + m["rate"] * dp)
        d["resid_L"] = d["fuel_L"] - d["expected_L"]
    _STATE["model"] = m


def load(days):
    _STATE["days"] = list(days)
    _recompute()


def ingest(day_record):
    days = _STATE["days"]
    days[:] = [d for d in days if d["date"] != day_record["date"]]
    days.append(day_record)
    days.sort(key=lambda d: d["date"])
    _recompute()
    return next(d for d in days if d["date"] == day_record["date"])


def day_count():
    return len(_STATE["days"])


def model_summary():
    return dict(_STATE["model"])


def _find_day(date):
    if not date:
        return None
    date = str(date).strip()
    for d in _STATE["days"]:
        if date in d["date"] or d["date"].split("-")[-1] == date.zfill(2):
            return d
    return None


# ===========================================================================
# TOOLS
# ===========================================================================
def fuel_overview(**_):
    days = _STATE["days"]
    if not days:
        return {"error": "No reports loaded."}
    price = config.MGO_PRICE_PER_M3
    mean_m3 = sum((d.get("fuel_m3") or 0) for d in days) / len(days)
    worst = max(days, key=lambda d: d["resid_L"])
    m = _STATE["model"]
    return {
        "days_covered": len(days),
        "date_range": f"{days[0]['date']} to {days[-1]['date']}",
        "mean_daily_fuel_L": round(mean_m3 * 1000),
        "mean_daily_cost_usd": round(mean_m3 * price),
        "annualised_cost_usd": round(mean_m3 * price * 365),
        "mgo_price_per_m3": price,
        "worst_day": worst["date"],
        "worst_day_deviation_L": worst["resid_L"],
        "model_base_load_L": m["base_L"],
        "model_L_per_dp_hour": m["rate"],
    }


def explain_day(date=None, **_):
    days = _STATE["days"]
    if not days:
        return {"error": "No reports loaded."}
    d = _find_day(date) if date else max(days, key=lambda x: x["resid_L"])
    if not d:
        return {"error": f"No report found for '{date}'."}
    resid = d["resid_L"]; sd = _STATE["model"]["sd"] or 1
    assessment = ("abnormally high for the workload — worth investigating" if resid > 1.5 * sd
                  else "moderately above expected" if resid > sd
                  else "efficiently below expected" if resid < -sd
                  else "in line with expected for the workload")
    return {
        "date": d["date"],
        "fuel_actual_L": d["fuel_L"],
        "expected_L": d["expected_L"],
        "deviation_L": resid,
        "deviation_cost_usd": round(resid / 1000 * config.MGO_PRICE_PER_M3),
        "dp_hours": d.get("dp_hours"),
        "wind": d.get("wind"),
        "sea_state": d.get("sea_state"),
        "assessment": assessment,
        "activity_summary": d.get("activity_text", "")[:600],
    }


def dp_efficiency(**_):
    days = _STATE["days"]
    rows = [{"date": d["date"], "dp_hours": d.get("dp_hours"),
             "fuel_L": d["fuel_L"],
             "L_per_dp_hour": round(d["fuel_L"] / d["dp_hours"])}
            for d in days if d.get("dp_hours") and d["dp_hours"] >= 10]
    if not rows:
        return {"error": "No high-DP days to compare."}
    best = min(rows, key=lambda r: r["L_per_dp_hour"])
    worst = max(rows, key=lambda r: r["L_per_dp_hour"])
    return {"days": rows, "best_day": best, "worst_day": worst,
            "spread_percent": round((worst["L_per_dp_hour"] - best["L_per_dp_hour"]) / worst["L_per_dp_hour"] * 100)}


def _parse_next_threshold(text):
    """Pull the numeric hours target out of a 'Next Lube oil change' string like '52980 (250h)'."""
    if not text:
        return None
    m = re.search(r"(\d{4,6})", str(text).replace(",", ""))
    return int(m.group(1)) if m else None


def maintenance_status(**_):
    days = _STATE["days"]
    if not days:
        return {"error": "No reports loaded."}
    latest = days[-1]
    machines = latest.get("machinery", {})
    out = []
    for name, m in machines.items():
        total = m.get("total_run_hours")
        target = _parse_next_threshold(m.get("next_lube_change"))
        rate = m.get("run_hrs_since_last") or 0
        rem = (target - total) if (target is not None and total is not None) else None
        days_left = round(rem / rate) if (rem is not None and rate) else None
        status = ("OVERDUE" if rem is not None and rem < 0
                  else "due soon" if days_left is not None and days_left <= 14
                  else "on schedule" if days_left is not None
                  else "no interval recorded")
        out.append({"machine": name.replace("Run hrs for ", "").strip(),
                    "total_run_hours": total, "next_target_h": target,
                    "hours_remaining": rem, "days_to_service": days_left, "status": status})
    return {"as_of": latest["date"], "machines": out,
            "overdue": [x["machine"] for x in out if x["status"] == "OVERDUE"],
            "due_soon": [x["machine"] for x in out if x["status"] == "due soon"]}


def machine_detail(name=None, **_):
    days = _STATE["days"]
    if not name:
        return {"error": "No machine name given."}
    if not days:
        return {"error": "No reports loaded."}
    latest = days[-1]
    for mname, m in latest.get("machinery", {}).items():
        if name.lower() in mname.lower():
            total = m.get("total_run_hours")
            target = _parse_next_threshold(m.get("next_lube_change"))
            rate = m.get("run_hrs_since_last") or 0
            rem = (target - total) if (target is not None and total is not None) else None
            return {"machine": mname.replace("Run hrs for ", "").strip(),
                    "total_run_hours": total, "since_overhaul": m.get("since_overhaul"),
                    "run_hrs_since_last": rate, "monthly_hours": m.get("monthly"),
                    "last_lube_change": m.get("last_lube_change"),
                    "next_lube_change": m.get("next_lube_change"),
                    "hours_remaining": rem,
                    "days_to_service": round(rem / rate) if (rem is not None and rate) else None,
                    "overdue": rem is not None and rem < 0}
    return {"error": f"No machine matching '{name}'."}


def engine_health(**_):
    days = _STATE["days"]
    if not days:
        return {"error": "No reports loaded."}
    latest = days[-1].get("technical", {})
    # data-quality: are the per-cylinder temps identical across every day?
    seq = [tuple(d.get("technical", {}).get("me1_cyl_temps", [])) for d in days]
    static = len(set(seq)) == 1 and len(seq[0]) > 0
    me1 = latest.get("me1_cyl_temps", [])
    me2 = latest.get("me2_cyl_temps", [])
    return {
        "as_of": days[-1]["date"],
        "me1_cylinder_temps_C": me1,
        "me1_deviation_C": latest.get("me1_deviation"),
        "me1_spread_C": (max(me1) - min(me1)) if me1 else None,
        "me1_load_pct": latest.get("me1_load_pct"),
        "me2_cylinder_temps_C": me2,
        "me2_deviation_C": latest.get("me2_deviation"),
        "me2_spread_C": (max(me2) - min(me2)) if me2 else None,
        "lube_oil_pressure_bar": latest.get("me1_lo_pressure"),
        "fuel_oil_pressure_bar": latest.get("me1_fo_pressure"),
        "telemetry_is_static": static,
        "data_quality_note": (
            "WARNING: engine telemetry is byte-identical across all reports — it is "
            "being entered by hand, not measured. Engine condition cannot be assessed "
            "or trended until a live sensor feed exists."
        ) if static else "Telemetry varies across reports.",
    }


def fluid_status(fluid=None, **_):
    days = _STATE["days"]
    if not days:
        return {"error": "No reports loaded."}
    latest = days[-1].get("fluids", {})
    if fluid:
        # normalise common phrasings to what the reports actually call fluids
        q = fluid.lower().replace("oil", "").strip()
        synonyms = {"lube": "lub", "lubricant": "lub", "diesel": "mgo", "gas": "mgo",
                    "water": "fresh water", "hydraulic": "hydraulic", "gear": "gear"}
        q = synonyms.get(q, q)
        for name, f in latest.items():
            if q in name.lower():
                trend = [{"date": d["date"],
                          "consumed": d.get("fluids", {}).get(name, {}).get("consumed"),
                          "balance": d.get("fluids", {}).get(name, {}).get("balance")} for d in days]
                return {"fluid": name, "as_of": days[-1]["date"], **f, "trend": trend}
        return {"error": f"No fluid matching '{fluid}'. Available: {', '.join(latest.keys())}"}
    summary = {name: {"consumed": f.get("consumed"), "balance": f.get("balance"), "unit": f.get("unit")}
               for name, f in latest.items()}
    return {"as_of": days[-1]["date"], "fluids": summary}


def activity_log(date=None, **_):
    """Read the UNSTRUCTURED hour-by-hour operations narrative for a day."""
    days = _STATE["days"]
    if not days:
        return {"error": "No reports loaded."}
    d = _find_day(date) if date else days[-1]
    if not d:
        return {"error": f"No report found for '{date}'."}
    return {"date": d["date"], "field": d.get("field"),
            "wind": d.get("wind"), "sea_state": d.get("sea_state"),
            "dp_hours": d.get("dp_hours"),
            "activities": d.get("activity_log", [])}


def hse_status(**_):
    days = _STATE["days"]
    if not days:
        return {"error": "No reports loaded."}
    latest = days[-1]
    tallies = {k: v.get("total") for k, v in latest.get("hse_tallies", {}).items()}
    # flag any day with a near miss / incident in the activity/hse
    near_misses = latest.get("hse_tallies", {}).get("Near Misses", {}).get("total")
    return {"as_of": latest["date"], "tallies": tallies,
            "near_misses_to_date": near_misses}


def report_summary(date=None, **_):
    """A full one-day briefing pulling from every section."""
    days = _STATE["days"]
    if not days:
        return {"error": "No reports loaded."}
    d = _find_day(date) if date else days[-1]
    if not d:
        return {"error": f"No report found for '{date}'."}
    fuel = explain_day(d["date"])
    return {
        "date": d["date"], "field": d.get("field"), "pob": d.get("pob_total"),
        "wind": d.get("wind"), "sea_state": d.get("sea_state"),
        "fuel": {"actual_L": fuel["fuel_actual_L"], "expected_L": fuel["expected_L"],
                 "deviation_L": fuel["deviation_L"], "assessment": fuel["assessment"]},
        "dp_hours": d.get("dp_hours"),
        "activity_summary": d.get("activity_text", "")[:500],
        "machines_of_note": maintenance_status().get("overdue", []) + maintenance_status().get("due_soon", []),
    }


def dataset_overview(**_):
    """
    A metadata summary of what data is loaded — so the model knows what exists
    before it queries. This is handed to the model upfront in the system prompt,
    and is also callable as a tool.
    """
    days = _STATE["days"]
    if not days:
        return {"error": "No reports loaded."}
    machines = list(days[-1].get("machinery", {}).keys())
    fluids = list(days[-1].get("fluids", {}).keys())
    m = _STATE["model"]
    # per-field ranges for the numeric day-level fields
    def rng(field):
        vals = [d.get(field) for d in days if isinstance(d.get(field), (int, float))]
        return {"min": min(vals), "max": max(vals), "mean": round(sum(vals) / len(vals), 1)} if vals else None
    return {
        "vessel": days[-1].get("vessel"),
        "field": days[-1].get("field"),
        "reports_loaded": len(days),
        "date_range": f"{days[0]['date']} to {days[-1]['date']}",
        "dates_present": [d["date"] for d in days],
        "fuel_model": {"base_load_L": m["base_L"], "L_per_dp_hour": m["rate"],
                       "residual_sd_L": m["sd"]},
        "queryable_numeric_fields": {
            "fuel_L": rng("fuel_L"),
            "dp_hours": rng("dp_hours"),
            "pob_total": rng("pob_total"),
            "temperature": rng("temperature"),
        },
        "machines_tracked": [mm.replace("Run hrs for ", "").strip() for mm in machines],
        "fluids_tracked": fluids,
        "each_report_also_has": [
            "hour-by-hour activity log (free text)",
            "per-cylinder engine exhaust temps + deviation",
            "HSE tallies (permits, drills, near misses)",
        ],
        "known_data_quality_issue": "engine telemetry is static/hand-entered across all reports",
    }


# fields the flexible query tool is allowed to operate on, mapped to how to read them
_QUERYABLE = {
    "fuel_L": lambda d: d.get("fuel_L"),
    "fuel_m3": lambda d: d.get("fuel_m3"),
    "dp_hours": lambda d: d.get("dp_hours"),
    "pob_total": lambda d: d.get("pob_total"),
    "temperature": lambda d: d.get("temperature"),
    "deviation_L": lambda d: d.get("resid_L"),
    "L_per_dp_hour": lambda d: round(d["fuel_L"] / d["dp_hours"]) if d.get("dp_hours") else None,
    "me1_deviation": lambda d: d.get("technical", {}).get("me1_deviation"),
    "me2_deviation": lambda d: d.get("technical", {}).get("me2_deviation"),
    "bow_thruster_1_hours": lambda d: d.get("machinery", {}).get("Run hrs for bow thruster  1", {}).get("run_hrs_since_last"),
    "bow_thruster_2_hours": lambda d: d.get("machinery", {}).get("Run hrs for bow thruster  2", {}).get("run_hrs_since_last"),
    "stern_thruster_hours": lambda d: d.get("machinery", {}).get("Run hrs for stern thruster", {}).get("run_hrs_since_last"),
    "fresh_water_consumed": lambda d: d.get("fluids", {}).get("Fresh Water", {}).get("consumed"),
}


def query_metric(field=None, operation="list", filter_field=None, filter_op=None, filter_value=None, **_):
    """
    Flexible query over the loaded reports WITHOUT arbitrary code execution.
    Lets the model answer open-ended analytical questions safely by choosing a
    known field, an aggregation, and an optional filter.

    field:        one of the queryable fields (see dataset_overview)
    operation:    'list' | 'sum' | 'mean' | 'min' | 'max' | 'count'
    filter_*:     optional — e.g. filter_field='dp_hours', filter_op='>', filter_value=15
    """
    days = _STATE["days"]
    if not days:
        return {"error": "No reports loaded."}
    if field not in _QUERYABLE:
        return {"error": f"Field '{field}' not queryable. Available: {list(_QUERYABLE.keys())}"}

    getter = _QUERYABLE[field]

    # apply optional filter
    def keep(d):
        if not filter_field:
            return True
        fg = _QUERYABLE.get(filter_field)
        if not fg:
            return True
        fv = fg(d)
        if fv is None:
            return False
        try:
            fval = float(filter_value)
        except (TypeError, ValueError):
            return True
        ops = {">": fv > fval, "<": fv < fval, ">=": fv >= fval,
               "<=": fv <= fval, "==": fv == fval, "!=": fv != fval}
        return ops.get(filter_op, True)

    rows = [(d["date"], getter(d)) for d in days if keep(d)]
    rows = [(dt, v) for dt, v in rows if v is not None]
    vals = [v for _, v in rows]

    if operation == "list":
        result = [{"date": dt, field: v} for dt, v in rows]
    elif operation == "count":
        result = len(vals)
    elif not vals:
        result = None
    elif operation == "sum":
        result = round(sum(vals), 2)
    elif operation == "mean":
        result = round(sum(vals) / len(vals), 2)
    elif operation == "min":
        result = min(vals)
    elif operation == "max":
        result = max(vals)
    else:
        return {"error": f"Unknown operation '{operation}'. Use list/sum/mean/min/max/count."}

    desc = f"{operation} of {field}"
    if filter_field:
        desc += f" where {filter_field} {filter_op} {filter_value}"
    return {"query": desc, "matched_days": len(rows), "result": result}


def plot_metric(field=None, chart_type="line", filter_field=None, filter_op=None, filter_value=None, title=None, **_):
    """
    Produce a CHART of a metric over the reports. Returns a chart spec that the
    browser renders (labels = dates, values = the field). Reuses the same safe
    queryable fields as query_metric — no arbitrary code, no plotting library
    on the backend; the front-end draws it.

    field:       one of the queryable fields
    chart_type:  'line' | 'bar'
    filter_*:    optional filter (same semantics as query_metric)
    title:       optional chart title
    """
    days = _STATE["days"]
    if not days:
        return {"error": "No reports loaded."}
    if field not in _QUERYABLE:
        return {"error": f"Field '{field}' not plottable. Available: {list(_QUERYABLE.keys())}"}
    getter = _QUERYABLE[field]

    def keep(d):
        if not filter_field:
            return True
        fg = _QUERYABLE.get(filter_field)
        if not fg:
            return True
        fv = fg(d)
        if fv is None:
            return False
        try:
            fval = float(filter_value)
        except (TypeError, ValueError):
            return True
        ops = {">": fv > fval, "<": fv < fval, ">=": fv >= fval,
               "<=": fv <= fval, "==": fv == fval, "!=": fv != fval}
        return ops.get(filter_op, True)

    labels, values = [], []
    for d in days:
        if not keep(d):
            continue
        v = getter(d)
        if v is None:
            continue
        labels.append(d["date"][5:])  # MM-DD
        values.append(v)

    if not values:
        return {"error": "No data points matched to plot."}

    if chart_type not in ("line", "bar"):
        chart_type = "line"

    pretty = field.replace("_", " ")
    auto_title = f"{pretty} by day"
    if filter_field:
        auto_title += f" (where {filter_field} {filter_op} {filter_value})"

    # The 'chart' key tells the UI to render a chart rather than print text.
    return {
        "chart": {
            "type": chart_type,
            "title": title or auto_title,
            "x_label": "Date",
            "y_label": pretty,
            "labels": labels,
            "values": values,
            "field": field,
        },
        "points_plotted": len(values),
        "instruction_to_assistant": (
            "The chart is now displayed to the user automatically. Do NOT reproduce it, "
            "do NOT output image markdown, base64, data URIs, or ![](...) syntax. In your "
            "text reply, only refer to the chart in one short sentence (e.g. 'the chart "
            "above shows fuel peaking on the 22nd') and continue your analysis in plain words."
        ),
    }


TOOL_FUNCTIONS = {
    "dataset_overview": dataset_overview,
    "query_metric": query_metric,
    "plot_metric": plot_metric,
    "fuel_overview": fuel_overview,
    "explain_day": explain_day,
    "dp_efficiency": dp_efficiency,
    "maintenance_status": maintenance_status,
    "machine_detail": machine_detail,
    "engine_health": engine_health,
    "fluid_status": fluid_status,
    "activity_log": activity_log,
    "hse_status": hse_status,
    "report_summary": report_summary,
}


def run_tool(name, arguments):
    fn = TOOL_FUNCTIONS.get(name)
    if not fn:
        return {"error": f"Unknown tool '{name}'."}
    try:
        return fn(**(arguments or {}))
    except Exception as e:
        return {"error": f"Tool '{name}' failed: {e}"}
