"""
watcher.py
==========
Watches the reports/ folder and ingests any new .xlsx the moment it appears —
so you can drag a report into the folder while the app is running and it gets
parsed and analysed live, no restart.

This is the Level-1 automation: in production an automated process (email
ingestion, cloud sync, or a direct vessel feed) drops files into this folder;
here you can play that role by dropping a file yourself.
"""

import os
import glob
import time
import threading

import config
import parser
import analysis

# Records of what we've already ingested, and a log of recent ingest events
# the UI can poll to show "new report received" notices.
_seen = set()
_events = []
_lock = threading.Lock()

# Optional callback invoked (with the ingested day record) after each NEW
# report is successfully ingested. The server registers this so a fresh
# report automatically triggers an intelligence run + notification — the
# natural "new data files that day" trigger. Kept as a hook so watcher.py
# has no dependency on the intelligence layer (clean layering).
_on_ingest = None


def set_on_ingest(callback):
    """Register a function(day_record) -> None to run after each new ingest."""
    global _on_ingest
    _on_ingest = callback


def _scan_once():
    for path in sorted(glob.glob(os.path.join(config.REPORTS_DIR, "*.xlsx"))):
        key = (path, os.path.getmtime(path))
        if key in _seen:
            continue
        _seen.add(key)
        try:
            record = parser.parse_one(path)
            enriched = analysis.ingest(record)
            with _lock:
                _events.append({
                    "date": enriched["date"],
                    "file": enriched["source_file"],
                    "fuel_L": enriched["fuel_L"],
                    "dp_hrs": enriched.get("dp_hours"),
                    "deviation_L": enriched["resid_L"],
                    "at": time.time(),
                })
            print(f"  + ingested {enriched['source_file']} "
                  f"({enriched['date']}: {enriched['fuel_L']} L, dev {enriched['resid_L']:+d})")
            # fire the optional intelligence trigger (outside the lock)
            if _on_ingest is not None:
                try:
                    _on_ingest(enriched)
                except Exception as e:
                    print(f"  ! on-ingest hook failed: {e}")
        except Exception as e:
            print(f"  ! failed to ingest {os.path.basename(path)}: {e}")


def initial_load():
    """Parse whatever is already in the folder at startup."""
    records = parser.parse_folder(config.REPORTS_DIR)
    for r in records:
        _seen.add((os.path.join(config.REPORTS_DIR, r["source_file"]),
                   os.path.getmtime(os.path.join(config.REPORTS_DIR, r["source_file"]))))
    return records


def drain_events():
    """Return and clear pending ingest events (the UI polls this)."""
    with _lock:
        out = list(_events)
        _events.clear()
    return out


def start_background():
    """Start the watch loop in a daemon thread."""
    def loop():
        while True:
            try:
                _scan_once()
            except Exception as e:
                print(f"  ! watcher error: {e}")
            time.sleep(config.WATCH_INTERVAL_SECONDS)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
