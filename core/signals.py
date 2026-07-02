"""
signals.py
==========
The deterministic SIGNAL-DETECTION layer for the automated intelligence system.

This is the "Signals" counterpart to the chatbot's analysis tools. Where the
chatbot answers questions you ask, this engine decides — on its own, every time
new data lands — what is worth telling someone about.

DESIGN PRINCIPLE (identical to the rest of the system):
    The CODE decides IF something is a concern and HOW severe it is.
    The MODEL only phrases it and suggests actions (done later, in
    intelligence.py). No severity, threshold, or number here is ever
    produced by the model — so a signal that says "Generator 2 is overdue"
    is a fact, not a guess.

Each detector returns zero or more Signal dicts with this shape:

    {
      "id":         stable string id (so re-runs don't duplicate),
      "category":   "fuel" | "dp" | "maintenance" | "engine" | "fluid" | "hse",
      "priority":   "low" | "medium" | "high",
      "title":      short human title,
      "summary":    one-line plain-English statement of the concern,
      "evidence":   list of {label, value} pairs pointing at the real data,
      "metric":     optional field name the chatbot can plot/probe,
      "probe":      optional question text to hand the chatbot for a deep-dive,
    }

The model turns `summary` + `evidence` into management prose and next steps;
it may not change any figure in `evidence`.
"""

import config
import analysis

_PRI_RANK = {"low": 1, "medium": 2, "high": 3}


def _th():
    return config.SIGNAL_THRESHOLDS


def _max_priority(a, b):
    return a if _PRI_RANK[a] >= _PRI_RANK[b] else b


# ---------------------------------------------------------------------------
# FUEL — residual vs the DP-workload model, and day-over-day jump
# ---------------------------------------------------------------------------
def _detect_fuel(days, model):
    out = []
    if not days:
        return out
    th = _th()
    sd = model.get("sd") or 0
    latest = days[-1]

    # (a) Latest day's residual vs the model (the "abnormal for the workload" test)
    resid = latest.get("resid_L", 0)
    if resid > th["fuel_resid_min_litres"] and sd > 0:
        sd_mult = resid / sd
        priority = None
        if sd_mult >= th["fuel_resid_sd_high"]:
            priority = "high"
        elif sd_mult >= th["fuel_resid_sd_medium"]:
            priority = "medium"
        if priority:
            cost = round(resid / 1000 * config.MGO_PRICE_PER_M3)
            out.append({
                "id": f"fuel_resid_{latest['date']}",
                "category": "fuel",
                "priority": priority,
                "title": "Fuel above expected for the workload",
                "summary": (f"On {latest['date']} the vessel burned {latest['fuel_L']:,} L — "
                            f"{resid:,} L more than the {latest['expected_L']:,} L expected for "
                            f"{latest.get('dp_hours')} DP hours."),
                "evidence": [
                    {"label": "Actual fuel", "value": f"{latest['fuel_L']:,} L"},
                    {"label": "Expected (model)", "value": f"{latest['expected_L']:,} L"},
                    {"label": "Deviation", "value": f"+{resid:,} L ({sd_mult:.1f}x the normal daily spread)"},
                    {"label": "Cost of the deviation", "value": f"${cost:,} at ${config.MGO_PRICE_PER_M3}/m3"},
                    {"label": "DP hours that day", "value": f"{latest.get('dp_hours')}"},
                    {"label": "Weather", "value": f"wind {latest.get('wind')}, sea {latest.get('sea_state')}"},
                ],
                "metric": "deviation_L",
                "probe": f"Why was fuel high on {latest['date'][5:]}?",
            })

    # (b) Day-over-day jump vs the trailing mean (catches a sudden step change
    #     even when the model residual alone wouldn't trip)
    if len(days) >= 4:
        prior = days[:-1]
        trailing = [d["fuel_L"] for d in prior[-5:] if d.get("fuel_L")]
        if trailing:
            mean_prev = sum(trailing) / len(trailing)
            if mean_prev > 0:
                frac = (latest["fuel_L"] - mean_prev) / mean_prev
                priority = None
                if frac >= th["fuel_jump_frac_high"]:
                    priority = "high"
                elif frac >= th["fuel_jump_frac_medium"]:
                    priority = "medium"
                if priority:
                    out.append({
                        "id": f"fuel_jump_{latest['date']}",
                        "category": "fuel",
                        "priority": priority,
                        "title": "Fuel stepped up sharply versus recent days",
                        "summary": (f"{latest['date']} fuel of {latest['fuel_L']:,} L is "
                                    f"{frac*100:.0f}% above the {round(mean_prev):,} L average "
                                    f"of the preceding days."),
                        "evidence": [
                            {"label": "Latest day", "value": f"{latest['fuel_L']:,} L"},
                            {"label": "Trailing average", "value": f"{round(mean_prev):,} L"},
                            {"label": "Increase", "value": f"+{frac*100:.0f}%"},
                        ],
                        "metric": "fuel_L",
                        "probe": "Plot fuel over time and explain the recent trend.",
                    })

    # (c) Window-level: the single worst fuel day still in the reporting window.
    #     The daily trigger focuses on the latest day, but a large recent spike
    #     (e.g. two days ago) should not silently drop off — surface it once,
    #     at a notch below the latest-day rules, and only if it isn't already
    #     the latest day covered by (a).
    if len(days) >= 3 and sd > 0:
        worst = max(days, key=lambda d: d.get("resid_L", 0))
        wres = worst.get("resid_L", 0)
        if (worst["date"] != latest["date"]
                and wres > th["fuel_resid_min_litres"]
                and wres / sd >= th["fuel_resid_sd_medium"]):
            sd_mult = wres / sd
            # window findings cap at medium — the latest day owns "high"
            priority = "medium"
            cost = round(wres / 1000 * config.MGO_PRICE_PER_M3)
            out.append({
                "id": f"fuel_window_worst_{worst['date']}",
                "category": "fuel",
                "priority": priority,
                "title": "Notable high-fuel day in the current window",
                "summary": (f"{worst['date']} remains the highest-deviation day in the window: "
                            f"{worst['fuel_L']:,} L vs {worst['expected_L']:,} L expected "
                            f"(+{wres:,} L)."),
                "evidence": [
                    {"label": "Date", "value": worst["date"]},
                    {"label": "Actual fuel", "value": f"{worst['fuel_L']:,} L"},
                    {"label": "Expected (model)", "value": f"{worst['expected_L']:,} L"},
                    {"label": "Deviation", "value": f"+{wres:,} L ({sd_mult:.1f}x the normal daily spread)"},
                    {"label": "Cost of the deviation", "value": f"${cost:,} at ${config.MGO_PRICE_PER_M3}/m3"},
                    {"label": "DP hours that day", "value": f"{worst.get('dp_hours')}"},
                ],
                "metric": "deviation_L",
                "probe": f"Why was fuel high on {worst['date'][5:]}?",
            })
    return out


# ---------------------------------------------------------------------------
# DP EFFICIENCY — spread between the most and least efficient DP days
# ---------------------------------------------------------------------------
def _detect_dp(dp):
    out = []
    if not isinstance(dp, dict) or "error" in dp or not dp.get("days"):
        return out
    th = _th()
    spread = dp.get("spread_percent", 0)
    priority = None
    if spread >= th["dp_spread_pct_high"]:
        priority = "high"
    elif spread >= th["dp_spread_pct_medium"]:
        priority = "medium"
    if priority:
        best, worst = dp["best_day"], dp["worst_day"]
        out.append({
            "id": "dp_spread",
            "category": "dp",
            "priority": priority,
            "title": "Wide spread in DP fuel efficiency",
            "summary": (f"DP fuel efficiency varies {spread}% across the window — from "
                        f"{best['L_per_dp_hour']:,} L/DP-hr on the best day to "
                        f"{worst['L_per_dp_hour']:,} L/DP-hr on the worst."),
            "evidence": [
                {"label": "Best day", "value": f"{best['date']}: {best['L_per_dp_hour']:,} L/DP-hr ({best['dp_hours']} DP hrs)"},
                {"label": "Worst day", "value": f"{worst['date']}: {worst['L_per_dp_hour']:,} L/DP-hr ({worst['dp_hours']} DP hrs)"},
                {"label": "Spread", "value": f"{spread}%"},
            ],
            "metric": "L_per_dp_hour",
            "probe": "How efficient is our DP, and what explains the best vs worst day?",
        })
    return out


# ---------------------------------------------------------------------------
# MAINTENANCE — overdue / due-soon from run-hours vs lube thresholds
# ---------------------------------------------------------------------------
def _detect_maintenance(maint):
    out = []
    if not isinstance(maint, dict) or "error" in maint:
        return out
    th = _th()
    as_of = maint.get("as_of")
    for m in maint.get("machines", []):
        rem = m.get("hours_remaining")
        days_left = m.get("days_to_service")
        name = m.get("machine")
        if rem is None:
            continue  # no interval recorded — nothing to assess
        if rem < 0:
            out.append({
                "id": f"maint_overdue_{name}",
                "category": "maintenance",
                "priority": "high",
                "title": f"{name}: lube service overdue",
                "summary": (f"{name} has passed its lube-oil change threshold by "
                            f"{abs(int(rem)):,} run-hours as of {as_of}."),
                "evidence": [
                    {"label": "Machine", "value": name},
                    {"label": "Total run-hours", "value": f"{int(m['total_run_hours']):,} h"},
                    {"label": "Service threshold", "value": f"{int(m['next_target_h']):,} h"},
                    {"label": "Past due by", "value": f"{abs(int(rem)):,} h"},
                ],
                "metric": None,
                "probe": f"Give me the full servicing detail on {name}.",
            })
        elif days_left is not None:
            priority = None
            if days_left <= th["maint_days_high"]:
                priority = "high"
            elif days_left <= th["maint_days_medium"]:
                priority = "medium"
            if priority:
                out.append({
                    "id": f"maint_due_{name}",
                    "category": "maintenance",
                    "priority": priority,
                    "title": f"{name}: lube service due soon",
                    "summary": (f"{name} reaches its lube-oil change threshold in about "
                                f"{days_left} days ({int(rem):,} run-hours remaining)."),
                    "evidence": [
                        {"label": "Machine", "value": name},
                        {"label": "Total run-hours", "value": f"{int(m['total_run_hours']):,} h"},
                        {"label": "Service threshold", "value": f"{int(m['next_target_h']):,} h"},
                        {"label": "Hours remaining", "value": f"{int(rem):,} h (~{days_left} days at current usage)"},
                    ],
                    "metric": None,
                    "probe": f"Give me the full servicing detail on {name}.",
                })
    return out


# ---------------------------------------------------------------------------
# ENGINE — data-quality signal when telemetry is static/hand-entered
# ---------------------------------------------------------------------------
def _detect_engine(engine):
    out = []
    if not isinstance(engine, dict) or "error" in engine:
        return out
    if engine.get("telemetry_is_static"):
        out.append({
            "id": "engine_static_telemetry",
            "category": "engine",
            "priority": "low",
            "title": "Engine telemetry is not live — condition cannot be trended",
            "summary": ("Per-cylinder engine readings are identical across every report, "
                        "which means they are being hand-entered rather than measured. "
                        "Engine health cannot be monitored or predicted until a live "
                        "sensor feed exists."),
            "evidence": [
                {"label": "Finding", "value": "Cylinder exhaust temps byte-identical across all reports"},
                {"label": "Latest ME1 deviation", "value": f"{engine.get('me1_deviation_C')} C"},
                {"label": "Latest ME2 deviation", "value": f"{engine.get('me2_deviation_C')} C"},
                {"label": "Implication", "value": "No early-warning of engine degradation is possible from this data"},
            ],
            "metric": None,
            "probe": "Can I trust the engine data, and what would it take to monitor engine health?",
        })
    return out


# ---------------------------------------------------------------------------
# FLUIDS — consumables running toward empty; waste tanks filling up
# ---------------------------------------------------------------------------
_WASTE_FLUIDS = {"Bilge Water", "Dirty Oil", "Sludges", "Sewage"}
_CONSUMABLE_FLUIDS = {"M/E Lub oil", "A/E Lub oil", "Hydraulic oil", "Gear Oil", "Fresh Water"}


def _detect_fluids(days):
    out = []
    if len(days) < 2:
        return out
    th = _th()
    latest = days[-1]
    fluids = latest.get("fluids", {})

    for name, f in fluids.items():
        bal = f.get("balance")
        if bal is None:
            continue

        # Consumables: days-to-empty at the recent average consumption rate
        if name in _CONSUMABLE_FLUIDS:
            rates = [d.get("fluids", {}).get(name, {}).get("consumed") for d in days[-5:]]
            rates = [r for r in rates if isinstance(r, (int, float)) and r > 0]
            if rates and bal > 0:
                rate = sum(rates) / len(rates)
                if rate > 0:
                    days_to_empty = bal / rate
                    priority = None
                    if days_to_empty <= th["fluid_days_to_empty_high"]:
                        priority = "high"
                    elif days_to_empty <= th["fluid_days_to_empty_medium"]:
                        priority = "medium"
                    if priority:
                        out.append({
                            "id": f"fluid_low_{name}",
                            "category": "fluid",
                            "priority": priority,
                            "title": f"{name} running low",
                            "summary": (f"{name} balance is {bal:g} {f.get('unit','')}, about "
                                        f"{days_to_empty:.0f} days at the recent rate of "
                                        f"{rate:.2g} {f.get('unit','')}/day."),
                            "evidence": [
                                {"label": "Current balance", "value": f"{bal:g} {f.get('unit','')}"},
                                {"label": "Recent daily use", "value": f"{rate:.2g} {f.get('unit','')}/day"},
                                {"label": "Days to empty", "value": f"~{days_to_empty:.0f}"},
                            ],
                            "metric": None,
                            "probe": f"Show me the consumption and balance trend for {name}.",
                        })

        # Waste tanks: only a concern if the level is actually RISING toward a
        # capacity. A flat level (common with hand-entered logs) is not
        # "filling up" — flagging it would be a false alarm — so we require a
        # genuine upward trend across the window before raising anything.
        if name in _WASTE_FLUIDS:
            history = [d.get("fluids", {}).get(name, {}).get("balance") for d in days]
            history = [h for h in history if isinstance(h, (int, float))]
            if len(history) >= 3 and bal >= 1:
                first, peak = history[0], max(history)
                rose = bal - first                     # net rise over the window
                is_rising = rose > 0 and bal >= peak    # trending up AND at its own peak now
                if is_rising and peak > 0:
                    frac = bal / peak
                    priority = None
                    if frac >= th["waste_fill_frac_high"]:
                        priority = "high"
                    elif frac >= th["waste_fill_frac_medium"]:
                        priority = "medium"
                    if priority:
                        out.append({
                            "id": f"waste_high_{name}",
                            "category": "fluid",
                            "priority": priority,
                            "title": f"{name} tank filling up",
                            "summary": (f"{name} has risen to {bal:g} {f.get('unit','')} and is trending "
                                        f"up — plan an offload before it reaches capacity."),
                            "evidence": [
                                {"label": "Current level", "value": f"{bal:g} {f.get('unit','')}"},
                                {"label": "Level at start of window", "value": f"{first:g} {f.get('unit','')}"},
                                {"label": "Net change", "value": f"+{rose:g} {f.get('unit','')}"},
                            ],
                            "metric": None,
                            "probe": f"Show me the trend for {name}.",
                        })
    return out


# ---------------------------------------------------------------------------
# HSE — a near miss / incident logged today
# ---------------------------------------------------------------------------
def _detect_hse(days):
    out = []
    if not days:
        return out
    th = _th()
    latest = days[-1]
    tallies = latest.get("hse_tallies", {})

    def _today(cat):
        v = tallies.get(cat, {}).get("today")
        return v if isinstance(v, (int, float)) else 0

    near_today = _today("Near Misses")
    if near_today and near_today > 0:
        out.append({
            "id": f"hse_near_{latest['date']}",
            "category": "hse",
            "priority": th["hse_near_miss_priority"],
            "title": "Near miss logged today",
            "summary": f"{int(near_today)} near miss(es) recorded on {latest['date']}.",
            "evidence": [
                {"label": "Near misses today", "value": f"{int(near_today)}"},
                {"label": "Near misses to date", "value": f"{int(tallies.get('Near Misses', {}).get('total', 0))}"},
            ],
            "metric": None,
            "probe": f"What's the HSE status and what happened on {latest['date'][5:]}?",
        })

    for cat in ("PD : Property Damage", "Workdays lost"):
        v = _today(cat)
        if v and v > 0:
            out.append({
                "id": f"hse_incident_{cat}_{latest['date']}",
                "category": "hse",
                "priority": th["hse_incident_priority"],
                "title": f"{cat} logged today",
                "summary": f"{int(v)} {cat} event(s) recorded on {latest['date']}.",
                "evidence": [
                    {"label": cat + " today", "value": f"{int(v)}"},
                    {"label": "To date", "value": f"{int(tallies.get(cat, {}).get('total', 0))}"},
                ],
                "metric": None,
                "probe": f"Summarise HSE for {latest['date'][5:]}.",
            })
    return out


# ---------------------------------------------------------------------------
# Orchestrator — run every detector against the current data store
# ---------------------------------------------------------------------------
def detect_all():
    """Run all detectors against the live analysis state. Returns a dict:
       {signals: [...], counts: {high,medium,low,total}, as_of, ...}."""
    days = analysis._STATE["days"]
    if not days:
        return {"signals": [], "counts": {"high": 0, "medium": 0, "low": 0, "total": 0},
                "as_of": None, "error": "No reports loaded."}

    model = analysis.model_summary()
    signals = []
    signals += _detect_fuel(days, model)
    signals += _detect_dp(analysis.dp_efficiency())
    signals += _detect_maintenance(analysis.maintenance_status())
    signals += _detect_engine(analysis.engine_health())
    signals += _detect_fluids(days)
    signals += _detect_hse(days)

    # sort by priority (high first), then category for stable ordering
    signals.sort(key=lambda s: (-_PRI_RANK[s["priority"]], s["category"], s["id"]))

    counts = {"high": 0, "medium": 0, "low": 0}
    for s in signals:
        counts[s["priority"]] += 1
    counts["total"] = len(signals)

    return {
        "as_of": days[-1]["date"],
        "date_range": f"{days[0]['date']} to {days[-1]['date']}",
        "reports_loaded": len(days),
        "vessel": days[-1].get("vessel") or config.VESSEL_LABEL,
        "field": days[-1].get("field") or config.FIELD_LABEL,
        "signals": signals,
        "counts": counts,
    }
