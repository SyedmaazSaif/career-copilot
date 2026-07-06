"""Daily scan scheduler.

A lightweight daemon thread (no extra dependency). Once there has been at least
one successful scan, it triggers a fresh daily scan whenever the newest
successful run is more than DAILY_INTERVAL old. The very first scan stays
user-initiated, so opening the app never kicks off a surprise multi-minute
network scan on its own.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

from . import scan_manager
from .db import SessionLocal
from .models import ScrapeRun

DAILY_INTERVAL = timedelta(hours=24)
CHECK_EVERY = 30 * 60  # seconds

_thread: threading.Thread | None = None


def _last_success_at() -> datetime | None:
    with SessionLocal() as db:
        run = (
            db.query(ScrapeRun)
            .filter(ScrapeRun.status == "done")
            .order_by(ScrapeRun.id.desc())
            .first()
        )
        return run.finished_at if run else None


def _loop() -> None:
    while True:
        try:
            last = _last_success_at()
            if last is not None and datetime.utcnow() - last >= DAILY_INTERVAL:
                if not scan_manager.is_running():
                    scan_manager.start_scan(trigger="daily")
        except Exception:
            pass  # a scheduler hiccup must never crash the app
        time.sleep(CHECK_EVERY)


def start_scheduler() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()
