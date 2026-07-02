#!/usr/bin/env python3
"""
render_create.py — create (or fetch) the Render web service for the API via the
Render REST API, configured with env vars from .env. Idempotent-ish: if a
service named "vaalco-api" already exists it prints it instead of duplicating.

Run after Render's GitHub App has access to the repo:
    python infra/render_create.py
"""
import os
import sys
import json
import urllib.request
import urllib.error

OWNER = os.environ.get("RENDER_OWNER_ID", "tea-d85mhhndl75s73919ofg")
REPO = "https://github.com/Stealth-Pareto-Labs/Vaalco_Customer"
NAME = "vaalco-api"


def load_env(path=".env"):
    env = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def api(method, path, key, body=None):
    req = urllib.request.Request(
        f"https://api.render.com/v1{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:800]}


def main():
    env = load_env()
    key = env["RENDER_API_KEY"]

    # Already exists?
    _, services = api("GET", "/services?limit=50&name=vaalco-api", key)
    for s in services if isinstance(services, list) else []:
        svc = s["service"]
        if svc["name"] == NAME:
            print("EXISTS:", svc["id"], (svc.get("serviceDetails") or {}).get("url"))
            return 0

    keys = ["LLM_PROVIDER", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "SUPABASE_URL",
            "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_DB_URL", "SUPABASE_BUCKET_RAW",
            "SUPABASE_BUCKET_OUT", "RESEND_API_KEY", "EMAIL_FROM", "ACCESS_CODE",
            "SESSION_SECRET", "OPERATOR_NAME", "VESSEL_LABEL", "FIELD_LABEL",
            "MGO_PRICE_PER_M3", "RECIPIENTS_JSON"]
    env_vars = [{"key": k, "value": env[k]} for k in keys if env.get(k)]
    env_vars += [{"key": "STORAGE_BACKEND", "value": "supabase"},
                 {"key": "FRONTEND_ORIGIN", "value": os.environ.get("FRONTEND_ORIGIN", "*")}]

    payload = {
        "type": "web_service", "name": NAME, "ownerId": OWNER,
        "repo": REPO, "branch": "main", "autoDeploy": "yes", "rootDir": "",
        "serviceDetails": {
            "env": "docker", "runtime": "docker", "plan": "starter", "region": "oregon",
            "healthCheckPath": "/health",
            "envSpecificDetails": {"dockerfilePath": "./infra/Dockerfile.api",
                                   "dockerContext": "."},
        },
        "envVars": env_vars,
    }
    code, d = api("POST", "/services", key, payload)
    if code >= 300:
        print("FAILED", code, d.get("error"))
        return 1
    svc = d.get("service", d)
    print("CREATED:", svc.get("id"), svc.get("name"))
    print("dashboard:", svc.get("dashboardUrl"))
    print("url:", (svc.get("serviceDetails") or {}).get("url"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
