"""
FASTAPI MAIN — Entry point của backend.

Run:
    uvicorn api.main:app --reload --port 8000

Swagger docs: http://localhost:8000/docs
"""

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from core.config import settings


# BUG-L5 fix: loguru UTF-8 — Windows console default cp1252, escape emoji
# Reconfigure để emoji render đúng. KHÔNG dùng `encoding` (loguru.add() không accept cho stream sink)
# Fix: reconfigure sys.stdout buffer UTF-8 ở Windows.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
logger.remove()
logger.add(
    sys.stdout,
    colorize=True,
    enqueue=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup + shutdown events."""
    logger.info(f"🚀 UGC Vietnam Backend starting ({settings.app_env})...")
    logger.info(f"Anthropic: {'✅' if settings.anthropic_api_key else '❌'}")
    logger.info(
        f"AtlasCloud Pay-as-you-go (image/video): {'✅' if settings.atlascloud_api_key else '❌'}"
    )
    logger.info(
        f"AtlasCloud Coding Plan (LLM):           {'✅' if settings.atlascloud_llm_api_key else '❌'}"
    )
    logger.info(
        f"LLM provider: {settings.llm_provider} "
        f"(analyzer={settings.llm_model_analyzer}, generator={settings.llm_model_generator}, "
        f"vision={settings.llm_model_vision})"
    )
    logger.info(f"GenMax TTS: {'✅' if settings.genmax_api_key else '❌'}")
    logger.info(f"ElevenLabs SFX: {'✅' if settings.elevenlabs_api_key else '❌'}")

    yield

    logger.info("🛑 Backend shutting down...")
    # CRITICAL C5 — Drain pending Director background tasks gracefully
    # so in-flight renders / refines / reassembles don't get killed mid-way.
    try:
        from api.routes.director import shutdown_pending_tasks
        await shutdown_pending_tasks(timeout_s=30.0)
    except Exception as e:
        logger.warning(f"[lifespan] shutdown_pending_tasks fail (non-fatal): {e}")


app = FastAPI(
    title="UGC Vietnam Backend",
    description="AI video UGC backend cho thị trường Việt Nam — như Topview Agent V2 nhưng tối ưu VN",
    version="1.0.0",
    lifespan=lifespan,
)

_DEFAULT_ALLOWED = "http://localhost:3000,http://127.0.0.1:3000"
_allowed_origins = [
    o.strip()
    for o in __import__("os").getenv("CORS_ALLOWED_ORIGINS", _DEFAULT_ALLOWED).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    # Sprint2 M10 — explicit allowlist instead of "*" (CSRF amplification risk).
    # Add new headers here when introducing them.
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Admin-Key",          # /admin/* auth (C1)
        "Idempotency-Key",      # /jobs/ugc + /director/generate (M11)
        "Accept",
        "Accept-Language",
        "X-Requested-With",
    ],
)


# Import routes — V3 canonical flow lives under /api/v1/director/*
# Legacy /jobs/* render endpoints kept for the existing Studio V4 modal until FE swap completes.
from api.routes import (  # noqa: E402
    jobs, avatars, video_direct, image_direct, media_upload,
    audio_direct, llm_direct, director, assets, admin,
)

# V3 — Director Agent (Continuity Bible + Shot List + Reference Chaining)
app.include_router(director.router, prefix="/api/v1/director", tags=["director-v3"])

# Asset Library — reusable Character / Product / Storyboard refs
app.include_router(assets.router, prefix="/api/v1/assets", tags=["assets"])

# Admin Panel — Style Preset Library / Prompt Library / Credits / Routing config
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])

# Direct vendor calls (used by manual playground + by Director storyboard/audio fill)
app.include_router(avatars.router, prefix="/api/v1/avatars", tags=["avatars"])
app.include_router(video_direct.router, prefix="/api/v1/video/direct", tags=["video-direct"])
app.include_router(image_direct.router, prefix="/api/v1/image/direct", tags=["image-direct"])
app.include_router(audio_direct.router, prefix="/api/v1/audio/direct", tags=["audio-direct"])
app.include_router(media_upload.router, prefix="/api/v1", tags=["media-upload"])
app.include_router(llm_direct.router, prefix="/api/v1/llm", tags=["llm"])

# Legacy render queue (kept for Studio V4 SceneEditor — will be removed once FE moves to /director/generate)
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs-legacy"])


@app.get("/")
async def root():
    return {
        "name": "UGC Vietnam Backend",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
