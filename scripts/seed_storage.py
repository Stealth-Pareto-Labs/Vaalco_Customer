#!/usr/bin/env python3
"""
seed_storage.py — upload the repo's sample reports to the Supabase raw-reports
bucket and ingest them (parse -> store -> one intelligence run). Idempotent.

    python scripts/seed_storage.py

Reads .env for SUPABASE_* + provider keys. Uses STORAGE_BACKEND=supabase.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "workers"))


def load_env():
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main():
    load_env()
    os.environ["STORAGE_BACKEND"] = "supabase"
    import ingest_core as ic
    res = ic.seed_sample_reports(os.path.join(ROOT, "reports"),
                                 vessel_code="NZ-MCT", deliver=False)
    print(res)


if __name__ == "__main__":
    main()
