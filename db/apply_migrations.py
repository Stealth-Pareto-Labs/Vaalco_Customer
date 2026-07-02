#!/usr/bin/env python3
"""
apply_migrations.py — apply every db/migrations/*.sql file in order.

Uses the direct Postgres connection (SUPABASE_DB_URL, or built from
SUPABASE_PROJECT_REF + SUPABASE_DB_PASSWORD). Each file is run in its own
transaction. Migrations are written to be idempotent, so re-running is safe.

    python db/apply_migrations.py
"""
import os
import sys
import glob
import psycopg


def load_env(path=".env"):
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def dsn():
    ref = os.environ.get("SUPABASE_PROJECT_REF", "")
    pw = os.environ.get("SUPABASE_DB_PASSWORD", "")
    return (f"host=db.{ref}.supabase.co port=5432 dbname=postgres "
            f"user=postgres password={pw} sslmode=require connect_timeout=10")


def main():
    load_env()
    here = os.path.dirname(os.path.abspath(__file__))
    files = sorted(glob.glob(os.path.join(here, "migrations", "*.sql")))
    if not files:
        print("no migrations found")
        return 1
    with psycopg.connect(dsn()) as conn:
        for f in files:
            name = os.path.basename(f)
            sql = open(f).read()
            try:
                with conn.transaction():
                    conn.execute(sql)
                print(f"OK   {name}")
            except Exception as e:
                print(f"FAIL {name}: {type(e).__name__}: {e}")
                return 1
    print("all migrations applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
