#!/usr/bin/env python3
"""
create_modal_secret.py — create/replace the Modal secret "vaalco-secrets"
from the local .env, so the worker functions get the same environment.

Run after `modal token new`:
    python infra/create_modal_secret.py
"""
import os
import subprocess
import sys

KEYS = [
    "LLM_PROVIDER", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL",
    "RESEND_API_KEY", "EMAIL_FROM", "RECIPIENTS_JSON",
    "ACCESS_CODE", "SESSION_SECRET",
    "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_DB_URL",
    "SUPABASE_BUCKET_RAW", "SUPABASE_BUCKET_OUT",
    "OPERATOR_NAME", "VESSEL_LABEL", "FIELD_LABEL", "MGO_PRICE_PER_M3",
    "API_BASE_URL",
]


def load_env(path=".env"):
    env = {}
    if os.path.exists(path):
        for line in open(path):
            line = line.rstrip("\n")
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def main():
    env = load_env()
    env["STORAGE_BACKEND"] = "supabase"   # workers always use the DB
    pairs = []
    for k in KEYS + ["STORAGE_BACKEND"]:
        v = env.get(k)
        if v:
            pairs.append(f"{k}={v}")
    if not pairs:
        print("no values found in .env")
        return 1
    cmd = ["modal", "secret", "create", "vaalco-secrets", *pairs, "--force"]
    print("Creating Modal secret 'vaalco-secrets' with keys:",
          ", ".join(p.split("=", 1)[0] for p in pairs))
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
