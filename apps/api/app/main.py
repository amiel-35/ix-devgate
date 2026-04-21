import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.modules.auth.router import router as auth_router
from app.modules.portal.router import router as portal_router
from app.modules.admin.router import router as admin_router
from app.modules.gateway.router import router as gateway_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    if settings.ENV == "production":
        if settings.SESSION_SECRET_KEY in ("changeme", "changeme-generate-a-real-secret", ""):
            raise RuntimeError("SESSION_SECRET_KEY doit être remplacée en production")
        if not settings.DEVGATE_MASTER_KEY:
            raise RuntimeError("DEVGATE_MASTER_KEY est obligatoire en production")
        if not settings.COOKIE_SECURE:
            raise RuntimeError("COOKIE_SECURE doit être True en production")
    elif not settings.DEVGATE_MASTER_KEY:
        logger.warning("DEVGATE_MASTER_KEY non configurée — le secret store sera indisponible")
    yield


app = FastAPI(
    title="DevGate API",
    version="0.1.0",
    # Docs désactivées en production
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,  # nécessaire pour les cookies de session
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Cookie"],
)

# ── Modules ──────────────────────────────────────────────────────
app.include_router(auth_router,    prefix="/auth",    tags=["auth"])
app.include_router(portal_router,  prefix="",         tags=["portal"])
app.include_router(admin_router,   prefix="/admin",   tags=["admin"])
app.include_router(gateway_router, prefix="/gateway", tags=["gateway"])


@app.get("/healthz")
def health():
    return {"ok": True}
