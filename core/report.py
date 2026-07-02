"""
report.py
=========
Turns an intelligence run (from intelligence.py) into the three artefacts the
system delivers and displays:

  render_html(run)  -> a professional, VAALCO-branded HTML email/report
  render_text(run)  -> a plain-text fallback (for text-only mail clients)
  render_sms(run)   -> a terse SMS digest (notification, not detail)

The HTML is fully self-contained (inline styles, embedded logo) so it renders
identically in an email client and in the Signals console. Colours follow the
VAALCO brand: deep navy + signal orange, with clear low/medium/high accents.
"""

import os
import re
import html
import base64

import config

# Brand palette (from the VAALCO logo: navy + orange)
NAVY = "#0B3A5B"
NAVY_DEEP = "#082A42"
ORANGE = "#E8563F"
INK = "#1b2a33"
MUT = "#5b6b76"
LINE = "#e2e8ec"
BG = "#f4f6f8"

PRI_COLOR = {"high": "#c62f28", "medium": "#d98a26", "low": "#3a7d8c"}
PRI_BG = {"high": "#fbeceb", "medium": "#fbf3e6", "low": "#eaf3f5"}
PRI_LABEL = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW"}

_LOGO_CACHE = None


def _logo_data_uri():
    global _LOGO_CACHE
    if _LOGO_CACHE is not None:
        return _LOGO_CACHE
    # prefer the pre-encoded file if present, else read the png
    here = os.path.dirname(__file__)
    root = os.path.dirname(here)
    b64_path = os.path.join(root, "assets", "logo_b64.txt")
    png_path = os.path.join(root, "assets", "vaalco_logo_email.png")
    b64 = None
    try:
        if os.path.exists(b64_path):
            b64 = open(b64_path).read().strip()
        elif os.path.exists(png_path):
            b64 = base64.b64encode(open(png_path, "rb").read()).decode()
    except OSError:
        b64 = None
    _LOGO_CACHE = f"data:image/png;base64,{b64}" if b64 else ""
    return _LOGO_CACHE


def _esc(s):
    return html.escape(str(s if s is not None else ""))


def _md(s):
    """Escape HTML, then render basic inline markdown (bold/italic/code) and
    newlines — so **bold** and lists in LLM prose show properly in the email."""
    s = html.escape(str(s if s is not None else ""))
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\*\w])\*(?!\s)(.+?)(?<!\s)\*(?![\*\w])", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"^\s*[-*]\s+(.+)$", r"• \1", s, flags=re.MULTILINE)
    return s.replace("\n", "<br>")


def subject_line(run):
    c = run.get("counts", {})
    bits = []
    if c.get("high"):
        bits.append(f"{c['high']} High")
    if c.get("medium"):
        bits.append(f"{c['medium']} Medium")
    if c.get("low"):
        bits.append(f"{c['low']} Low")
    status = ", ".join(bits) if bits else "All clear"
    return f"Vessel Intelligence — {run.get('vessel','Vessel')} — {run.get('as_of','')} — {status}"


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
def _pill(priority):
    return (f'<span style="display:inline-block;font:600 11px/1 -apple-system,Segoe UI,Roboto,sans-serif;'
            f'letter-spacing:.06em;color:#fff;background:{PRI_COLOR[priority]};'
            f'padding:5px 9px;border-radius:4px;">{PRI_LABEL[priority]}</span>')


def _signal_card(sig):
    p = sig["priority"]
    ev_rows = ""
    for e in sig.get("evidence", []):
        ev_rows += (
            f'<tr>'
            f'<td style="padding:4px 12px 4px 0;color:{MUT};font-size:13px;white-space:nowrap;vertical-align:top;">{_esc(e["label"])}</td>'
            f'<td style="padding:4px 0;color:{INK};font-size:13px;font-weight:600;vertical-align:top;">{_esc(e["value"])}</td>'
            f'</tr>'
        )
    steps = ""
    for s in sig.get("next_steps", []):
        steps += (f'<li style="margin:0 0 6px;color:{INK};font-size:13.5px;line-height:1.5;">{_esc(s)}</li>')

    return f"""
    <tr><td style="padding:0 0 16px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="border:1px solid {LINE};border-left:4px solid {PRI_COLOR[p]};border-radius:6px;background:#fff;">
        <tr><td style="padding:16px 18px 10px;">
          <table role="presentation" width="100%"><tr>
            <td style="vertical-align:middle;">{_pill(p)}
              <span style="display:inline-block;margin-left:8px;font:600 15.5px/1.3 -apple-system,Segoe UI,Roboto,sans-serif;color:{NAVY};">{_esc(sig["title"])}</span>
            </td>
            <td style="text-align:right;color:{MUT};font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;vertical-align:middle;">{_esc(sig["category"])}</td>
          </tr></table>
          <p style="margin:10px 0 0;color:{INK};font-size:14px;line-height:1.55;">{_md(sig.get("explanation",""))}</p>
        </td></tr>
        <tr><td style="padding:2px 18px 6px;">
          <div style="background:{PRI_BG[p]};border-radius:5px;padding:11px 13px;">
            <div style="color:{MUT};font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;margin-bottom:6px;">Evidence</div>
            <table role="presentation" cellpadding="0" cellspacing="0">{ev_rows}</table>
          </div>
        </td></tr>
        <tr><td style="padding:6px 18px 16px;">
          <div style="color:{MUT};font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;margin-bottom:6px;">Recommended next steps</div>
          <ul style="margin:0;padding-left:18px;">{steps}</ul>
        </td></tr>
      </table>
    </td></tr>"""


def _count_chip(n, label, color):
    dim = "opacity:.35;" if not n else ""
    return (f'<td style="padding:0 6px;"><div style="{dim}background:#fff;border:1px solid {LINE};'
            f'border-top:3px solid {color};border-radius:6px;padding:12px 18px;text-align:center;min-width:64px;">'
            f'<div style="font:700 26px/1 -apple-system,Segoe UI,Roboto,sans-serif;color:{color};">{n}</div>'
            f'<div style="font-size:11px;color:{MUT};text-transform:uppercase;letter-spacing:.06em;margin-top:4px;">{label}</div>'
            f'</div></td>')


def render_html(run):
    logo = _logo_data_uri()
    c = run.get("counts", {})
    signals = run.get("signals", [])

    logo_block = (f'<img src="{logo}" alt="{_esc(run.get("operator",""))}" '
                  f'style="height:46px;width:auto;display:block;">' if logo
                  else f'<div style="font:700 20px -apple-system,sans-serif;color:#fff;">{_esc(run.get("operator",""))}</div>')

    if signals:
        cards = "".join(_signal_card(s) for s in signals)
        body_inner = f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{cards}</table>'
    else:
        body_inner = (f'<div style="background:#fff;border:1px solid {LINE};border-radius:6px;padding:28px;'
                      f'text-align:center;color:{MUT};font-size:14px;">No signals were raised for this window. '
                      f'All monitored metrics are within their configured thresholds.</div>')

    narr = ("Analysis narrated by AI, grounded in computed evidence"
            if run.get("narrated_by_model") else
            "Analysis generated by the deterministic engine (AI narration unavailable)")

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{BG};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:640px;max-width:100%;">

  <!-- header -->
  <tr><td style="background:{NAVY};border-radius:10px 10px 0 0;padding:22px 26px;">
    <table role="presentation" width="100%"><tr>
      <td style="vertical-align:middle;">{logo_block}</td>
      <td style="text-align:right;vertical-align:middle;">
        <div style="color:#fff;font:600 15px -apple-system,Segoe UI,Roboto,sans-serif;">Vessel Intelligence Report</div>
        <div style="color:#9fc0d6;font-size:12px;margin-top:3px;">{_esc(run.get("as_of",""))} &nbsp;·&nbsp; {_esc(run.get("vessel",""))}</div>
      </td>
    </tr></table>
  </td></tr>

  <!-- sub-header strip -->
  <tr><td style="background:{NAVY_DEEP};padding:9px 26px;border-bottom:3px solid {ORANGE};">
    <span style="color:#bcd4e4;font-size:12px;">{_esc(run.get("field",""))} &nbsp;·&nbsp; {run.get('reports_loaded',0)} reports &nbsp;·&nbsp; window {_esc(run.get("date_range",""))}</span>
  </td></tr>

  <!-- body -->
  <tr><td style="background:{BG};padding:22px 26px 8px;">

    <!-- counts -->
    <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto 20px;"><tr>
      {_count_chip(c.get('high',0), 'High', PRI_COLOR['high'])}
      {_count_chip(c.get('medium',0), 'Medium', PRI_COLOR['medium'])}
      {_count_chip(c.get('low',0), 'Low', PRI_COLOR['low'])}
    </tr></table>

    <!-- exec summary -->
    <table role="presentation" width="100%" style="margin-bottom:20px;"><tr>
      <td style="background:#fff;border:1px solid {LINE};border-radius:6px;padding:16px 18px;">
        <div style="color:{ORANGE};font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin-bottom:7px;">Executive summary</div>
        <div style="color:{INK};font-size:14.5px;line-height:1.6;">{_md(run.get("executive_summary",""))}</div>
      </td>
    </tr></table>

    {body_inner}

  </td></tr>

  <!-- footer -->
  <tr><td style="background:{BG};padding:8px 26px 26px;">
    <div style="border-top:1px solid {LINE};padding-top:14px;color:{MUT};font-size:11.5px;line-height:1.6;">
      Generated {_esc(run.get("generated_at",""))} &nbsp;·&nbsp; trigger: {_esc(run.get("trigger",""))}<br>
      Every figure above is computed by the vessel analysis engine from the source reports; severity is rule-based. {narr}.<br>
      {_esc(run.get("operator",""))} · Offshore Vessel Intelligence Platform.
    </div>
  </td></tr>

</table>
</td></tr></table>
</body></html>"""


# ---------------------------------------------------------------------------
# Plain text
# ---------------------------------------------------------------------------
def render_text(run):
    L = []
    L.append(f"{run.get('operator','')} — VESSEL INTELLIGENCE REPORT")
    L.append(f"{run.get('vessel','')} · {run.get('field','')}")
    L.append(f"As of {run.get('as_of','')} · window {run.get('date_range','')} · {run.get('reports_loaded',0)} reports")
    c = run.get("counts", {})
    L.append(f"Signals: {c.get('high',0)} HIGH, {c.get('medium',0)} MEDIUM, {c.get('low',0)} LOW")
    L.append("=" * 64)
    L.append("EXECUTIVE SUMMARY")
    L.append(run.get("executive_summary", ""))
    L.append("")
    for i, s in enumerate(run.get("signals", []), 1):
        L.append("-" * 64)
        L.append(f"[{PRI_LABEL[s['priority']]}] {s['title']}  ({s['category']})")
        L.append(s.get("explanation", ""))
        L.append("  Evidence:")
        for e in s.get("evidence", []):
            L.append(f"    - {e['label']}: {e['value']}")
        L.append("  Recommended next steps:")
        for st in s.get("next_steps", []):
            L.append(f"    * {st}")
        L.append("")
    if not run.get("signals"):
        L.append("No signals raised for this window.")
    L.append("=" * 64)
    L.append(f"Generated {run.get('generated_at','')} · trigger {run.get('trigger','')}.")
    L.append("Figures computed by the analysis engine; severity is rule-based.")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# SMS digest — terse notification
# ---------------------------------------------------------------------------
def render_sms(run):
    c = run.get("counts", {})
    vessel = run.get("vessel", "Vessel").split(" (")[0]
    date = run.get("as_of", "")
    if c.get("total", 0) == 0:
        return f"VESSEL INTEL {date} ({vessel}): all clear, no signals. Full report emailed."

    # name the highest-priority items briefly
    highs = [s for s in run.get("signals", []) if s["priority"] == "high"]
    meds = [s for s in run.get("signals", []) if s["priority"] == "medium"]
    lead = ""
    if highs:
        names = "; ".join(_short_title(s) for s in highs[:2])
        extra = f" +{len(highs)-2} more" if len(highs) > 2 else ""
        lead = f"{len(highs)} HIGH ({names}{extra})"
    parts = [lead] if lead else []
    if meds:
        parts.append(f"{len(meds)} MED")
    if c.get("low"):
        parts.append(f"{c['low']} low")
    body = ", ".join(p for p in parts if p)
    msg = f"VESSEL INTEL {date} ({vessel}): {body}. Full report emailed."
    return msg[:320]  # keep it to a couple of SMS segments


def _short_title(sig):
    t = sig["title"]
    # compress common phrasings for SMS
    repl = {
        "lube service overdue": "svc overdue",
        "Wide spread in DP fuel efficiency": "DP efficiency spread",
        "Notable high-fuel day in the current window": "high-fuel day",
        "tank filling up": "tank high",
    }
    for k, v in repl.items():
        if k in t:
            return t.replace(k, v)
    return t[:38]
