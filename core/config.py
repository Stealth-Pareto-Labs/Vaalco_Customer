
"""
config.py
=========
The ONE place BOTH systems read configuration — the chatbot ("Ask") and the
automated intelligence layer ("Signals").

SECURITY NOTE (production hardening, 2026-07):
    All secrets are read from environment variables ONLY. Nothing sensitive is
    hardcoded in this file, so it is safe to commit. Set the variables via your
    platform's secret manager (Render env vars, Modal secrets, Vercel env,
    GitHub Actions secrets) or a local, git-ignored `.env` for development.
    See `.env.example` for the full list.

Sections below:
  1. LLM provider + key      (OpenAI / Anthropic — swappable)
  2. Email delivery          (Resend preferred; SMTP fallback)
  3. SMS delivery (Twilio)   (OFF until configured)
  4. Recipients              (who gets the report / SMS)
  5. Signal thresholds       (what counts as low / medium / high)
  6. Storage + data          (file backend today, Supabase in production)
  7. Auth                    (shared access code for the demo stage)
"""

import os


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


# ===================================================================
# 1. LLM PROVIDER + KEY  (required for both systems)
#    LLM_PROVIDER selects the reasoning layer. The deterministic math
#    always runs in Python tools regardless of provider.
# ===================================================================
LLM_PROVIDER = _env("LLM_PROVIDER", "openai").strip().lower()   # "openai" | "anthropic"

OPENAI_API_KEY = _env("OPENAI_API_KEY")        # set in the environment, never here
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")  # set in the environment, never here

# Model per provider (both support tool calling).
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o")
ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL", "claude-sonnet-5")

# Back-compat: existing core code reads config.MODEL. Point it at the active
# provider's model so nothing downstream changes.
MODEL = ANTHROPIC_MODEL if LLM_PROVIDER == "anthropic" else OPENAI_MODEL

MAX_TOKENS = _env_int("MAX_TOKENS", 4096)          # chat answer length cap
MAX_TOOL_ROUNDS = _env_int("MAX_TOOL_ROUNDS", 6)   # safety cap on the tool loop per question
INTEL_MAX_TOKENS = _env_int("INTEL_MAX_TOKENS", 4096)   # Signals report length cap


# ---- Data settings --------------------------------------------------------
REPORTS_DIR = _env("REPORTS_DIR", "reports")            # folder watched for incoming .xlsx
REPORTS_OUT_DIR = _env("REPORTS_OUT_DIR", "reports_out")  # where intelligence runs are saved
WATCH_INTERVAL_SECONDS = _env_int("WATCH_INTERVAL_SECONDS", 2)


# ---- Domain settings ------------------------------------------------------
# Set this to the client's real MGO contract price before any client demo.
MGO_PRICE_PER_M3 = _env_int("MGO_PRICE_PER_M3", 730)

# Shown in report headers / branding.
OPERATOR_NAME = _env("OPERATOR_NAME", "VAALCO Energy")
VESSEL_LABEL = _env("VESSEL_LABEL", "Navigator Z (NZ-MCT)")
FIELD_LABEL = _env("FIELD_LABEL", "ETAME Field, Offshore Gabon")


# ---- Server settings ------------------------------------------------------
HOST = _env("HOST", "")                 # "" = all interfaces
PORT = _env_int("PORT", 8000)


# ===================================================================
# 2. EMAIL DELIVERY
#    Preferred: Resend (transactional, reliable). If RESEND_API_KEY is
#    unset, the system falls back to SMTP; if neither is configured it
#    writes the email to the outbox and logs it (never crashes).
# ===================================================================
RESEND_API_KEY = _env("RESEND_API_KEY")
EMAIL_FROM = _env("EMAIL_FROM")                 # e.g. "VAALCO Alerts <alerts@yourdomain.com>"

# SMTP fallback (used only if RESEND_API_KEY is empty).
SMTP_HOST = _env("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = _env_int("SMTP_PORT", 587)          # 587 = STARTTLS
SMTP_USER = _env("SMTP_USER")
SMTP_PASSWORD = _env("SMTP_PASSWORD")
SMTP_USE_TLS = _env_bool("SMTP_USE_TLS", True)


def resend_configured() -> bool:
    return bool(RESEND_API_KEY.strip() and EMAIL_FROM.strip())


def smtp_configured() -> bool:
    return bool(SMTP_HOST.strip() and SMTP_USER.strip() and SMTP_PASSWORD.strip()
                and EMAIL_FROM.strip())


def email_configured() -> bool:
    return resend_configured() or smtp_configured()


# ===================================================================
# 3. SMS DELIVERY (Twilio) - OFF by default. Safe when unconfigured.
# ===================================================================
SMS_ENABLED = _env_bool("SMS_ENABLED", False)
TWILIO_ACCOUNT_SID = _env("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = _env("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = _env("TWILIO_FROM_NUMBER")


def sms_configured() -> bool:
    return bool(SMS_ENABLED and TWILIO_ACCOUNT_SID.strip()
                and TWILIO_AUTH_TOKEN.strip() and TWILIO_FROM_NUMBER.strip())


# ===================================================================
# 4. RECIPIENTS - who receives the daily intelligence report.
#    Configurable via RECIPIENTS_JSON (a JSON array) for cloud deploys;
#    falls back to a single self-addressed entry for local dev.
# ===================================================================
def _load_recipients():
    import json
    raw = os.environ.get("RECIPIENTS_JSON", "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
    fallback_email = EMAIL_FROM or _env("SMTP_USER") or ""
    if not fallback_email:
        return []
    return [{
        "name": "Operations",
        "email": fallback_email,
        "phone": "+10000000000",
        "sms_from_priority": "none",
    }]


RECIPIENTS = _load_recipients()


# ===================================================================
# 5. SIGNAL THRESHOLDS - tune what the engine flags and at what severity.
#    (Unchanged from the original — these are load-bearing domain values.)
# ===================================================================
SIGNAL_THRESHOLDS = {
    # --- Fuel vs the DP-workload model (residual in litres, as multiples of
    #     the model's own residual standard deviation) ---
    "fuel_resid_sd_medium": 1.5,   # residual > 1.5 sd over expected -> MEDIUM
    "fuel_resid_sd_high": 3.0,     # residual > 3.0 sd over expected -> HIGH
    "fuel_resid_min_litres": 800,  # ignore tiny deviations below this many L

    # --- Day-over-day fuel jump vs the trailing mean (fractional) ---
    "fuel_jump_frac_medium": 0.15,  # +15% vs trailing mean -> MEDIUM
    "fuel_jump_frac_high": 0.30,    # +30% vs trailing mean -> HIGH

    # --- Maintenance (from run-hours vs the lube-oil change threshold) ---
    "maint_days_medium": 14,        # <= 14 days to service -> MEDIUM ("due soon")
    "maint_days_high": 3,           # <= 3 days to service  -> HIGH
    # overdue (hours_remaining < 0) is always HIGH.

    # --- DP efficiency spread across the window (best vs worst L/DP-hour) ---
    "dp_spread_pct_medium": 25,     # >25% spread -> MEDIUM
    "dp_spread_pct_high": 45,       # >45% spread -> HIGH

    # --- Fluid / tank levels ---
    "fluid_days_to_empty_medium": 7,
    "fluid_days_to_empty_high": 3,
    "waste_fill_frac_medium": 0.80,
    "waste_fill_frac_high": 0.95,

    # --- HSE ---
    "hse_near_miss_priority": "medium",
    "hse_incident_priority": "high",
}


# ===================================================================
# 6. STORAGE BACKEND
#    "file"     -> local filesystem (dev / Phase-0, unchanged behavior)
#    "supabase" -> Postgres + Storage (production)
# ===================================================================
STORAGE_BACKEND = _env("STORAGE_BACKEND", "file").strip().lower()
SUPABASE_URL = _env("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = _env("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_ANON_KEY = _env("SUPABASE_ANON_KEY")
SUPABASE_DB_URL = _env("SUPABASE_DB_URL")
SUPABASE_BUCKET_RAW = _env("SUPABASE_BUCKET_RAW", "raw-reports")
SUPABASE_BUCKET_OUT = _env("SUPABASE_BUCKET_OUT", "intelligence-runs")


# ===================================================================
# 7. AUTH - simple shared access code for the prototype/demo stage.
# ===================================================================
ACCESS_CODE = _env("ACCESS_CODE")               # gate for the demo login
SESSION_SECRET = _env("SESSION_SECRET")         # signs session cookies / JWTs


def api_key_present() -> bool:
    if LLM_PROVIDER == "anthropic":
        return bool(ANTHROPIC_API_KEY.strip())
    return bool(OPENAI_API_KEY.strip())
