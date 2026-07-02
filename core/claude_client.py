"""
llm_client.py  (filename kept as claude_client.py so imports don't change)
==========================================================================
The real LLM integration — calls the OpenAI API (GPT) with the full tool set.

Standard tool-use loop:
  1. send question + tool menu to the model
  2. if the model calls a tool, run OUR deterministic function (analysis.py)
  3. feed the result back
  4. repeat until the model returns a final text answer

The model reads unstructured text (via the activity_log tool) and phrases
answers; it never computes numbers — those come from the tools.
"""

import json

import config
import analysis
import llm


def _fn(name, description, properties=None, required=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }


TOOLS = [
    _fn("dataset_overview",
        "Get a metadata summary of what report data is loaded — vessel, date range, which "
        "dates are present, the fuel model, the ranges of each numeric field, which machines "
        "and fluids are tracked, and known data-quality issues. Call this FIRST if you're "
        "unsure what data exists or what can be queried."),
    _fn("query_metric",
        "Flexible analytical query over the reports for open-ended questions that the specific "
        "tools don't cover — e.g. 'every day the bow thruster ran over 15 hours', 'average fuel "
        "on days with more than 15 DP hours', 'how many days were over expected fuel'. Pick a "
        "field, an operation, and an optional filter. Call dataset_overview first to see valid "
        "field names.",
        {"field": {"type": "string", "description": "field to analyse, e.g. 'fuel_L', 'dp_hours', 'L_per_dp_hour', 'bow_thruster_1_hours', 'deviation_L' (see dataset_overview)"},
         "operation": {"type": "string", "description": "'list' | 'sum' | 'mean' | 'min' | 'max' | 'count'"},
         "filter_field": {"type": "string", "description": "optional field to filter on, e.g. 'dp_hours'"},
         "filter_op": {"type": "string", "description": "optional comparison: '>' '<' '>=' '<=' '==' '!='"},
         "filter_value": {"type": "number", "description": "optional value to compare against"}},
        ["field"]),
    _fn("plot_metric",
        "Draw a CHART (line or bar) of a metric across the reports for the user to see — "
        "e.g. 'plot fuel over time', 'show me a bar chart of DP hours', 'graph fuel deviation'. "
        "Uses the same fields as query_metric, with an optional filter. The chart is rendered "
        "in the chat; after calling this, give a one-sentence description of what the chart shows.",
        {"field": {"type": "string", "description": "field to plot, e.g. 'fuel_L', 'dp_hours', 'L_per_dp_hour', 'deviation_L'"},
         "chart_type": {"type": "string", "description": "'line' (trend over time) or 'bar' (compare days)"},
         "filter_field": {"type": "string", "description": "optional field to filter on"},
         "filter_op": {"type": "string", "description": "optional comparison: '>' '<' '>=' '<=' '==' '!='"},
         "filter_value": {"type": "number", "description": "optional value to compare against"},
         "title": {"type": "string", "description": "optional chart title"}},
        ["field"]),
    _fn("fuel_overview",
        "Overall fuel picture across the whole reporting window: average daily fuel, "
        "daily and annualised cost, and the worst day. Use for broad fuel/cost questions."),
    _fn("explain_day",
        "Explain why fuel was high or low on a SPECIFIC date vs the DP-workload model, "
        "with that day's activity summary. Use for 'why was fuel high on the 22nd'. "
        "Returns the worst day if no date given.",
        {"date": {"type": "string", "description": "e.g. '06-22' or '22'"}}),
    _fn("dp_efficiency",
        "Fuel efficiency during Dynamic Positioning — fuel per DP hour across days and "
        "the best/worst spread. Use for DP efficiency questions."),
    _fn("maintenance_status",
        "Which machines are due or overdue for service, from run-hours vs their lube-oil "
        "change thresholds. Use for 'what maintenance is due', 'anything overdue'."),
    _fn("machine_detail",
        "Full servicing detail on ONE machine (run-hours, since-overhaul, last/next lube "
        "change, hours remaining). Use when the user names a machine, e.g. 'Generator 2', "
        "'Port main engine', 'bow thruster'.",
        {"name": {"type": "string", "description": "machine name fragment, e.g. 'generator No2', 'Port ME'"}}),
    _fn("engine_health",
        "Per-cylinder exhaust temperatures, deviation, load, and lube/fuel pressures for the "
        "main engines — AND whether the telemetry is actually being measured or is static/"
        "hand-entered. Use for 'how are the engines', 'can I trust the engine data', 'cylinder temps'."),
    _fn("fluid_status",
        "Consumption and inventory balance of fluids (fuel, lube oils, hydraulic oil, fresh "
        "water, bilge, sludge, etc.). Pass a fluid name for detail + trend, or omit for a "
        "summary of all fluids. Use for 'how much lube oil left', 'water consumption', 'fluid balances'.",
        {"fluid": {"type": "string", "description": "optional fluid name, e.g. 'lube', 'fresh water', 'hydraulic'"}}),
    _fn("activity_log",
        "Read the UNSTRUCTURED hour-by-hour operations narrative for a day — what the vessel "
        "actually did, in the crew's own words. Use to understand the 'why' behind a day, or "
        "for 'what did they do on the 22nd', 'what happened that day'.",
        {"date": {"type": "string", "description": "e.g. '06-22' or '22'; omit for latest day"}}),
    _fn("hse_status",
        "Safety indicators — permits, toolbox meetings, drills, near misses, medical reports. "
        "Use for 'any safety incidents', 'HSE status', 'near misses'."),
    _fn("report_summary",
        "A full one-day briefing pulling from every section (fuel, DP, activity, maintenance "
        "flags, POB, weather). Use for 'summarise the 22nd', 'give me the rundown for that day'.",
        {"date": {"type": "string", "description": "e.g. '06-22' or '22'; omit for latest day"}}),
]


SYSTEM_PROMPT_BASE = """You are the intelligence assistant for the offshore support vessel Navigator Z (NZ-MCT), operating in the ETAME Field, Offshore Gabon. You help a marine superintendent and crew understand the vessel's daily midnight reports.

You have tools that read and compute from the vessel's real reports — fuel and operations, maintenance and run-hours, per-cylinder engine telemetry, fluid inventory, the hour-by-hour activity narrative, HSE, plus a flexible query_metric tool for open-ended analytical questions. Follow these rules strictly:

1. To answer any question about the vessel, you MUST call the appropriate tool(s). Never answer from memory or guesswork. You may call several tools for one question (e.g. explain_day plus activity_log to explain both the number and the reason). For open-ended analytical questions that no specific tool covers, use query_metric.

2. Every number you state must come from a tool result. NEVER calculate, estimate, round, or invent a figure. If a tool returns 20,800 L, say 20,800 L — not "about 20,000". The tools do all math; you report and interpret what they return.

3. The activity_log tool returns the crew's own free-text description of what they did. Use it to explain WHY a day looked the way it did — but only describe what the text actually says. Do not invent causes, platforms, or events that aren't in the returned text.

4. When you call plot_metric, the chart is rendered to the user automatically. NEVER output image markdown, base64 strings, data URIs, or ![](...) syntax — that produces garbage on screen. Just mention the chart in one short sentence and keep your analysis in plain text.

5. If the engine telemetry is flagged as static/hand-entered, be honest that engine condition cannot be assessed from it.

6. When a tool returns an "error" field, say plainly what wasn't found rather than making something up.

7. Answer in clear, plain language for a busy captain who is not a data analyst. Lead with the conclusion. Be concise. Say what the number means and, where useful, what to do.

Be direct, accurate, and grounded entirely in the tool results.

Here is a summary of the data currently loaded, so you know what exists before you query:
"""


def _system_prompt():
    """Base rules + a live metadata summary of the loaded data (Layer-1 context)."""
    try:
        overview = analysis.dataset_overview()
        return SYSTEM_PROMPT_BASE + json.dumps(overview, indent=2)
    except Exception:
        return SYSTEM_PROMPT_BASE + "(no data loaded yet)"


def answer_question(user_message, history=None):
    if not config.api_key_present():
        return {"answer": ("No LLM API key is set. Set ANTHROPIC_API_KEY (or OPENAI_API_KEY "
                           "with LLM_PROVIDER=openai) in the environment."), "trace": []}
    # The tool set (TOOLS), the system prompt (_system_prompt), and the
    # deterministic tool runner (analysis.run_tool) are unchanged. Only the
    # provider transport lives in llm.py, selected by config.LLM_PROVIDER.
    return llm.run_tool_conversation(
        system=_system_prompt(),
        history=history,
        user_message=user_message,
        tools=TOOLS,
        tool_runner=analysis.run_tool,
        max_rounds=config.MAX_TOOL_ROUNDS,
    )
