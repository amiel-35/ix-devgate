from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.modules.auth.router import router as auth_router
from app.modules.portal.router import router as portal_router
from app.modules.admin.router import router as admin_router
from app.modules.gateway.router import router as gateway_router

app = FastAPI(
    title="DevGate API",
    version="0.1.0",
    # Docs désactivées en production
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev local (sans Docker)
        "http://localhost:3001",  # Next.js dev via Docker (port mappé)
    ],
    allow_credentials=True,  # nécessaire pour les cookies de session
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Modules ──────────────────────────────────────────────────────
app.include_router(auth_router,    prefix="/auth",    tags=["auth"])
app.include_router(portal_router,  prefix="",         tags=["portal"])
app.include_router(admin_router,   prefix="/admin",   tags=["admin"])
app.include_router(gateway_router, prefix="/gateway", tags=["gateway"])


@app.get("/healthz")
def health():
    return {"ok": True}
