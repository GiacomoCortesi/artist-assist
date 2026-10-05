"""FastAPI application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import api_router
from app.config import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    Path("data").mkdir(parents=True, exist_ok=True)
    Path(settings.media_root).mkdir(parents=True, exist_ok=True)
    from app.db import init_db
    from app.sync.scheduler import shutdown_scheduler, start_scheduler

    init_db()
    if settings.environment != "test":
        from app.db import get_session_factory
        from app.security.bootstrap import bootstrap_meta_tokens_from_env

        session = get_session_factory()()
        try:
            bootstrap_meta_tokens_from_env(session, settings)
            session.commit()
        finally:
            session.close()
        start_scheduler()
    yield
    shutdown_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
