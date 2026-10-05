"""Bootstrap platform credentials from environment into encrypted storage."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import repository as repo

logger = logging.getLogger(__name__)


def bootstrap_meta_tokens_from_env(session: Session, settings: Settings | None = None) -> None:
    """Copy Meta page/Threads tokens from .env into platform_accounts + encrypted_tokens."""
    cfg = settings or get_settings()

    if cfg.meta_page_access_token and cfg.meta_page_id:
        fb = repo.upsert_platform_account(
            session,
            source="facebook",
            external_id=cfg.meta_page_id,
            status="connected",
            meta={"from_fixtures": False},
        )
        repo.store_account_token(session, fb, cfg.meta_page_access_token)
        logger.info("Bootstrapped facebook account from env (page_id=%s)", cfg.meta_page_id)

        if cfg.meta_ig_user_id:
            ig = repo.upsert_platform_account(
                session,
                source="instagram",
                external_id=cfg.meta_ig_user_id,
                status="connected",
                meta={"from_fixtures": False},
            )
            repo.store_account_token(session, ig, cfg.meta_page_access_token)
            logger.info("Bootstrapped instagram account from env (ig_user_id=%s)", cfg.meta_ig_user_id)

    if cfg.threads_access_token and cfg.threads_user_id:
        th = repo.upsert_platform_account(
            session,
            source="threads",
            external_id=cfg.threads_user_id,
            status="connected",
            meta={"from_fixtures": False},
        )
        repo.store_account_token(session, th, cfg.threads_access_token)
        logger.info("Bootstrapped threads account from env (user_id=%s)", cfg.threads_user_id)
