"""API route package."""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.routes import router as app_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(app_router)
