"""
auth.py — shared-access-code auth for the prototype.
====================================================
The agreed demo auth is a single shared access code. On success we mint a short
HS256 JWT (signed with SESSION_SECRET) that the frontend sends as a Bearer
token. This is deliberately simple; Supabase Auth (profiles + RLS already exist
in the schema) can replace it without touching the analysis code.
"""

import time
import hmac
import json
import base64
import hashlib

import config

_ALG = "HS256"
_TTL_SECONDS = 60 * 60 * 12   # 12h sessions


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(msg: bytes) -> str:
    secret = (config.SESSION_SECRET or config.ACCESS_CODE or "dev-secret").encode()
    return _b64(hmac.new(secret, msg, hashlib.sha256).digest())


def issue_token(subject: str = "demo", role: str = "viewer") -> str:
    header = _b64(json.dumps({"alg": _ALG, "typ": "JWT"}).encode())
    now = int(time.time())
    payload = _b64(json.dumps({
        "sub": subject, "role": role, "iat": now, "exp": now + _TTL_SECONDS,
    }).encode())
    signing_input = f"{header}.{payload}".encode()
    return f"{header}.{payload}.{_sign(signing_input)}"


def verify_token(token: str):
    """Return the payload dict if valid, else None."""
    try:
        header, payload, sig = token.split(".")
    except (ValueError, AttributeError):
        return None
    if not hmac.compare_digest(sig, _sign(f"{header}.{payload}".encode())):
        return None
    try:
        data = json.loads(_b64d(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if data.get("exp", 0) < int(time.time()):
        return None
    return data


def check_access_code(code: str) -> bool:
    expected = (config.ACCESS_CODE or "").strip()
    if not expected:
        return False
    return hmac.compare_digest((code or "").strip(), expected)
