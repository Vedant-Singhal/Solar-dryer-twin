from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.db.session import engine
from app.services.cache import get_cache
from app.services.surrogate import Surrogate

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "model_version": settings.model_version}


@router.get("/readyz")
def readyz() -> dict:
    checks: dict[str, bool] = {}
    try:
        Surrogate.get()
        checks["model"] = True
    except Exception:
        checks["model"] = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["db"] = True
    except Exception:
        checks["db"] = False
    checks["cache"] = get_cache().ping()
    return {"ready": all(checks.values()), "checks": checks}
