"""APScheduler wiring for daily sync only."""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _daily_sync_job() -> None:
    from app.db import init_db
    from app.sync.service import run_with_lock

    init_db()
    run_with_lock(trigger="scheduled")


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    settings = get_settings()
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _daily_sync_job,
        trigger="cron",
        hour=settings.sync_cron_hour,
        minute=settings.sync_cron_minute,
        id="daily_sync",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Sync scheduler started (daily %02d:%02d)",
        settings.sync_cron_hour,
        settings.sync_cron_minute,
    )
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
