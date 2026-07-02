"""
notify.py
=========
Delivery layer for the intelligence report — email (SMTP) and SMS (Twilio).

SAFE BY DEFAULT — the guiding rule for this file:
  * If email is not configured (no SMTP host), the report is written to
    reports_out/ and logged. Nothing is sent, nothing crashes.
  * If SMS is not configured (or SMS_ENABLED is False), the SMS text is logged
    to reports_out/ and the console. No paid message is sent.
So the whole pipeline runs end-to-end on a fresh checkout with no credentials,
and you can inspect exactly what WOULD have been sent. Fill in the config
sections when you're ready to go live; no code changes are needed.

Everything here uses the Python standard library only (smtplib, email, urllib)
— no third-party SDKs — matching the rest of the project.
"""

import os
import json
import ssl
import smtplib
import urllib.request
import urllib.parse
import urllib.error
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config
import report as report_mod

_PRI_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


def _outbox_dir():
    d = os.path.join(config.REPORTS_OUT_DIR, "outbox")
    os.makedirs(d, exist_ok=True)
    return d


def _log_email_to_disk(run, html_body, text_body, recipients, reason):
    """Write the exact email that would be sent, for verification/audit."""
    d = _outbox_dir()
    stem = os.path.join(d, f"email_{run['run_id']}")
    with open(stem + ".html", "w") as fh:
        fh.write(html_body)
    meta = {
        "run_id": run["run_id"],
        "to": [r["email"] for r in recipients],
        "subject": report_mod.subject_line(run),
        "reason_not_sent": reason,
        "written_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    with open(stem + ".meta.json", "w") as fh:
        json.dump(meta, fh, indent=2)
    return stem + ".html"


def send_email(run, html_body=None, text_body=None):
    """Send (or, if unconfigured, save) the full report email to all recipients.
    Returns a result dict describing what happened."""
    html_body = html_body if html_body is not None else report_mod.render_html(run)
    text_body = text_body if text_body is not None else report_mod.render_text(run)
    recipients = config.RECIPIENTS
    subject = report_mod.subject_line(run)
    to_addrs = [r["email"] for r in recipients if r.get("email")]

    if not to_addrs:
        return {"channel": "email", "sent": False, "detail": "No recipients configured."}

    if not config.smtp_configured():
        path = _log_email_to_disk(run, html_body, text_body, recipients,
                                  "SMTP not configured (see config.py section 2)")
        print(f"  · EMAIL not sent (SMTP not configured). Saved to {path}")
        print(f"    Would send to: {', '.join(to_addrs)}")
        return {"channel": "email", "sent": False, "simulated": True,
                "saved_to": path, "to": to_addrs, "subject": subject,
                "detail": "SMTP not configured — email saved to outbox instead of sent."}

    # Build a multipart/alternative message (text + html)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_FROM
    msg["To"] = ", ".join(to_addrs)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if config.SMTP_USE_TLS:
            ctx = ssl.create_default_context()
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as srv:
                srv.starttls(context=ctx)
                if config.SMTP_USER:
                    srv.login(config.SMTP_USER, config.SMTP_PASSWORD)
                srv.sendmail(config.EMAIL_FROM, to_addrs, msg.as_string())
        else:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as srv:
                if config.SMTP_USER:
                    srv.login(config.SMTP_USER, config.SMTP_PASSWORD)
                srv.sendmail(config.EMAIL_FROM, to_addrs, msg.as_string())
        print(f"  · EMAIL sent to {', '.join(to_addrs)}")
        return {"channel": "email", "sent": True, "to": to_addrs, "subject": subject}
    except (smtplib.SMTPException, OSError) as e:
        path = _log_email_to_disk(run, html_body, text_body, recipients, f"send failed: {e}")
        print(f"  ! EMAIL send failed ({e}). Saved to {path}")
        return {"channel": "email", "sent": False, "error": str(e), "saved_to": path,
                "detail": "SMTP send failed — email saved to outbox."}


def _sms_recipients_for(run):
    """Which people should get an SMS, given the run's highest priority and
    each person's sms_from_priority gate."""
    counts = run.get("counts", {})
    # the top priority present in this run
    top = "none"
    for p in ("high", "medium", "low"):
        if counts.get(p):
            top = p
            break
    if top == "none":
        return [], top
    out = []
    for r in config.RECIPIENTS:
        gate = (r.get("sms_from_priority") or "none").lower()
        if gate == "none":
            continue
        if _PRI_RANK.get(top, 0) >= _PRI_RANK.get(gate, 99):
            if r.get("phone"):
                out.append(r)
    return out, top


def _log_sms_to_disk(run, body, recipients, reason):
    d = _outbox_dir()
    path = os.path.join(d, f"sms_{run['run_id']}.json")
    payload = {
        "run_id": run["run_id"],
        "to": [r["phone"] for r in recipients],
        "body": body,
        "reason_not_sent": reason,
        "written_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2)
    return path


def _twilio_send(to_number, body):
    """Send one SMS via Twilio's REST API using only urllib (no SDK)."""
    url = f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_ACCOUNT_SID}/Messages.json"
    data = urllib.parse.urlencode({
        "From": config.TWILIO_FROM_NUMBER,
        "To": to_number,
        "Body": body,
    }).encode()
    # HTTP basic auth: SID:AUTH_TOKEN
    import base64
    cred = base64.b64encode(
        f"{config.TWILIO_ACCOUNT_SID}:{config.TWILIO_AUTH_TOKEN}".encode()).decode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Authorization": f"Basic {cred}",
                                          "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def send_sms(run, body=None):
    """Send (or, if unconfigured, log) the SMS digest to the gated recipients."""
    body = body if body is not None else report_mod.render_sms(run)
    recipients, top = _sms_recipients_for(run)

    if not recipients:
        return {"channel": "sms", "sent": False,
                "detail": f"No SMS recipients for a '{top}' run (per each person's SMS gate)."}

    if not config.sms_configured():
        path = _log_sms_to_disk(run, body, recipients,
                                "SMS not enabled/configured (see config.py section 3)")
        print(f"  · SMS not sent (SMS disabled/unconfigured). Saved to {path}")
        print(f"    Would send to {', '.join(r['phone'] for r in recipients)}: \"{body}\"")
        return {"channel": "sms", "sent": False, "simulated": True, "saved_to": path,
                "to": [r["phone"] for r in recipients], "body": body,
                "detail": "SMS disabled/unconfigured — digest saved to outbox instead of sent."}

    results = []
    for r in recipients:
        try:
            resp = _twilio_send(r["phone"], body)
            results.append({"to": r["phone"], "sid": resp.get("sid"), "sent": True})
            print(f"  · SMS sent to {r['phone']}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            results.append({"to": r["phone"], "sent": False, "error": str(e)})
            print(f"  ! SMS to {r['phone']} failed: {e}")
    return {"channel": "sms", "sent": any(x["sent"] for x in results),
            "body": body, "results": results}


def deliver(run):
    """Deliver a run over all channels. Returns a combined result."""
    email_res = send_email(run)
    sms_res = send_sms(run)
    return {"email": email_res, "sms": sms_res}
