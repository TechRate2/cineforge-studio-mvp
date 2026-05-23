"""Admin Panel — `/api/v1/admin/*` endpoints.

4 buckets (per Blueprint v2.1 §4):
  - presets/*  — Style Preset Library (reusable visual_style + audio + setting)
  - prompts/*  — Read/edit system prompts (director.md / scene.md / evaluation.md / revise.md)
  - credits    — Wallet balance view (AtlasCloud + GenMax — placeholder until vendor APIs expose balance)
  - config     — Read current LLM routing + cost gate defaults from env
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from core import style_presets
from core.config import settings
from core.sanitize import sanitize_prompt_injection


router = APIRouter()


# ============================================================
# V3 CRITICAL C1 — Admin auth dependency
# ============================================================
async def require_admin(x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")) -> None:
    """Guard MUTATING admin endpoints.

    Policy:
      - If `ADMIN_API_KEY` env is set → header `X-Admin-Key` MUST equal it (case-sensitive).
      - If empty AND `app_env == "development"` → bypass (localhost dev convenience).
      - Otherwise reject 403.
    """
    expected = settings.admin_api_key
    if expected:
        if not x_admin_key or x_admin_key != expected:
            raise HTTPException(403, "Unauthorized — set X-Admin-Key header with ADMIN_API_KEY value")
        return
    # No key configured
    if settings.app_env != "development":
        raise HTTPException(
            403,
            "Admin endpoints are locked: set ADMIN_API_KEY env var in production.",
        )


# ============================================================
# STYLE PRESETS
# ============================================================
class PresetVisualStyle(BaseModel):
    cinematography: str = ""
    color_grading: str = ""
    lighting_design: str = ""
    camera_language: str = ""
    film_grain: str = ""
    aspect_ratio: str = "9:16"


class PresetAudioDesign(BaseModel):
    mood: str = ""
    tempo: str = ""
    music_genre: str = ""
    sfx_emphasis: list[str] = Field(default_factory=list)
    dialogue_style: str = ""


class PresetSetting(BaseModel):
    location: str = ""
    time_of_day: str = ""
    atmosphere: str = ""


class PresetConstraints(BaseModel):
    must_have: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    brand_safety: list[str] = Field(default_factory=list)


class CreatePresetRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field("", max_length=400)
    visual_style: PresetVisualStyle
    audio_design: PresetAudioDesign
    setting: PresetSetting
    constraints: PresetConstraints
    tags: str = ""


class UpdatePresetRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = None
    visual_style: Optional[PresetVisualStyle] = None
    audio_design: Optional[PresetAudioDesign] = None
    setting: Optional[PresetSetting] = None
    constraints: Optional[PresetConstraints] = None
    tags: Optional[str] = None


@router.get("/presets")
async def list_presets(q: Optional[str] = None, limit: int = 100):
    return {"items": style_presets.list_presets(search=q, limit=limit)}


@router.post("/presets")
async def create_preset(request: CreatePresetRequest, _: None = Depends(require_admin)):
    return style_presets.create_preset(
        name=request.name,
        description=request.description,
        visual_style=request.visual_style.model_dump(),
        audio_design=request.audio_design.model_dump(),
        setting=request.setting.model_dump(),
        constraints=request.constraints.model_dump(),
        tags=request.tags,
    )


@router.get("/presets/{preset_id}")
async def get_preset(preset_id: str):
    p = style_presets.get_preset(preset_id)
    if not p:
        raise HTTPException(404, f"preset '{preset_id}' not found")
    return p


@router.patch("/presets/{preset_id}")
async def update_preset(preset_id: str, request: UpdatePresetRequest, _: None = Depends(require_admin)):
    out = style_presets.update_preset(
        preset_id,
        name=request.name,
        description=request.description,
        visual_style=request.visual_style.model_dump() if request.visual_style else None,
        audio_design=request.audio_design.model_dump() if request.audio_design else None,
        setting=request.setting.model_dump() if request.setting else None,
        constraints=request.constraints.model_dump() if request.constraints else None,
        tags=request.tags,
    )
    if not out:
        existing = style_presets.get_preset(preset_id)
        if existing and existing.get("is_builtin"):
            raise HTTPException(403, "built-in presets cannot be edited (fork instead)")
        raise HTTPException(404, f"preset '{preset_id}' not found")
    return out


@router.post("/presets/{preset_id}/touch")
async def touch_preset(preset_id: str):
    if not style_presets.get_preset(preset_id):
        raise HTTPException(404, f"preset '{preset_id}' not found")
    style_presets.touch_used(preset_id)
    return {"ok": True}


@router.delete("/presets/{preset_id}")
async def delete_preset(preset_id: str, _: None = Depends(require_admin)):
    existing = style_presets.get_preset(preset_id)
    if not existing:
        raise HTTPException(404, f"preset '{preset_id}' not found")
    if existing.get("is_builtin"):
        raise HTTPException(403, "built-in presets cannot be deleted")
    style_presets.delete_preset(preset_id)
    return {"ok": True}


# ============================================================
# PROMPT LIBRARY
# ============================================================
_PROMPT_DIR = Path(__file__).parent.parent.parent / "system_prompts"
ALLOWED_PROMPTS = {"director", "scene", "evaluation", "revise"}


class UpdatePromptRequest(BaseModel):
    content: str = Field(..., min_length=10, max_length=30000)


@router.get("/prompts")
async def list_prompts():
    """List system prompt files + size + last-modified."""
    out = []
    for name in ALLOWED_PROMPTS:
        path = _PROMPT_DIR / f"{name}.md"
        if path.exists():
            stat = path.stat()
            out.append({
                "name": name,
                "size": stat.st_size,
                "lines": path.read_text(encoding="utf-8").count("\n"),
                "updated_at": stat.st_mtime,
            })
    return {"items": out}


@router.get("/prompts/{name}")
async def get_prompt(name: str):
    if name not in ALLOWED_PROMPTS:
        raise HTTPException(404, f"prompt '{name}' not allowed. Available: {sorted(ALLOWED_PROMPTS)}")
    path = _PROMPT_DIR / f"{name}.md"
    if not path.exists():
        raise HTTPException(404, f"prompt file '{name}.md' not found")
    return {
        "name": name,
        "content": path.read_text(encoding="utf-8"),
        "size": path.stat().st_size,
    }


@router.put("/prompts/{name}")
async def update_prompt(
    name: str,
    request: UpdatePromptRequest,
    _: None = Depends(require_admin),
):
    """Overwrite a system prompt + clear the loader's lru_cache so the next
    LLM call picks up the new content without server restart.

    V3 CRITICAL C1 (auth) + HIGH-2 (jailbreak validation):
      - Requires admin auth (Header X-Admin-Key) per `require_admin` dependency.
      - Scans content for prompt-injection patterns before writing — if any
        BEYOND those that legitimately appear in system prompts as examples,
        reject with 400. We use a soft heuristic: a system prompt is supposed
        to declare "you are X" once at the top, not many times scattered.
    """
    if name not in ALLOWED_PROMPTS:
        raise HTTPException(404, f"prompt '{name}' not allowed")

    # Heuristic injection check — system prompts naturally describe roles, so
    # we tolerate them but cap density (>5 matches per prompt is suspicious).
    _, flagged = sanitize_prompt_injection(request.content)
    if len(flagged) > 5:
        raise HTTPException(
            400,
            f"Prompt rejected — {len(flagged)} injection-like patterns detected "
            f"(threshold 5). Sample: {flagged[:3]}",
        )

    path = _PROMPT_DIR / f"{name}.md"
    backup_path = path.with_suffix(".md.bak")
    if path.exists():
        # Keep a 1-deep backup of the previous version
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(request.content, encoding="utf-8")
    # Clear lru_cache so the next `load("director")` re-reads the file
    try:
        from system_prompts import load as _load
        _load.cache_clear()  # type: ignore[attr-defined]
    except Exception as e:
        logger.warning(f"[admin/prompts] cache_clear fail: {e}")
    logger.info(f"[admin/prompts] {name}.md updated ({len(request.content)} chars)")
    return {"ok": True, "name": name, "size": len(request.content), "backup": str(backup_path.name)}


# ============================================================
# CREDIT BALANCE (placeholder — real vendor APIs not yet wired)
# ============================================================
@router.get("/credits")
async def get_credits():
    """Wallet balance view. Returns mocked balances until vendor APIs expose
    them (AtlasCloud + GenMax don't currently have public balance endpoints
    via the same key we use to render)."""
    return {
        "atlascloud": {
            "key_set": bool(settings.atlascloud_api_key),
            "key_masked": _mask(settings.atlascloud_api_key),
            "base_url": settings.atlascloud_base_url,
            "balance_usd": None,
            "balance_source": "vendor API not exposed — track in your AtlasCloud dashboard",
        },
        "atlascloud_llm": {
            "key_set": bool(settings.atlascloud_llm_api_key),
            "key_masked": _mask(settings.atlascloud_llm_api_key),
            "base_url": settings.atlascloud_llm_base_url,
            "balance_usd": None,
            "balance_source": "Coding Plan separate wallet",
        },
        "genmax": {
            "key_set": bool(settings.genmax_api_key),
            "key_masked": _mask(settings.genmax_api_key),
            "base_url": settings.genmax_base_url,
            "balance_credits": None,
            "balance_source": "vendor API not exposed",
        },
        "anthropic": {
            "key_set": bool(settings.anthropic_api_key),
            "key_masked": _mask(settings.anthropic_api_key),
            "balance_usd": None,
            "balance_source": "fallback provider — check console.anthropic.com",
        },
        "r2": {
            "configured": bool(
                settings.r2_account_id and settings.r2_access_key_id
                and settings.r2_secret_access_key and settings.r2_bucket_name
            ),
            "bucket": settings.r2_bucket_name,
            "public_url": settings.r2_public_url or None,
        },
    }


# ============================================================
# MODEL ROUTING / CONFIG (read-only — edit via env reload)
# ============================================================
@router.get("/config")
async def get_config():
    """Read-only view of the current LLM + cost-gate routing config."""
    return {
        "llm": {
            "provider": settings.llm_provider,
            "models": {
                "analyzer": settings.llm_model_analyzer,
                "generator": settings.llm_model_generator,
                "vision": settings.llm_model_vision,
                "premium": settings.llm_model_premium,
            },
        },
        "cost_gate": {
            "default_mode": "off",
            "default_threshold": 7.0,
            "draft_model_map": {
                "seedance_2_0": "seedance_2_0_fast",
                "seedance_2_0_fast": "seedance_2_0_fast",
                "seedance_1_5_pro": "seedance_2_0_fast",
                "vidu_q3": "vidu_q3",
                "vidu_q3_mix": "vidu_q3",
                "wan_2_7": "wan_2_7",
                "auto": "seedance_2_0_fast",
            },
        },
        "video_models": {
            "auto_picker_default": "seedance_2_0",
            "available_user_models": [
                "auto", "vidu_q3", "vidu_q3_mix", "wan_2_7",
                "seedance_1_5_pro", "seedance_2_0", "seedance_2_0_fast",
            ],
        },
        "app": {
            "env": settings.app_env,
            "port": settings.app_port,
            "worker_concurrency": settings.worker_concurrency,
        },
    }


# ============================================================
# Helpers
# ============================================================
def _mask(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]
