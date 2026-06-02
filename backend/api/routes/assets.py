"""Asset Library — `/api/v1/assets` CRUD endpoints.

Stores Character / Product / Storyboard reference assets so users can reuse
them across multiple Director plans (e.g. the same KOL face / packaging /
hero composition without re-uploading every time).

Backed by `core/assets_store.py` (SQLite). Image URLs can be either external
(after upload to R2/AtlasCloud) or `data:image/…` data-URLs for offline drafts.
"""
from __future__ import annotations

from typing import Optional, Literal, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import assets_store, autonomous_asset_pins


router = APIRouter()


AssetType = Literal["character", "product", "storyboard"]


# ============================================================
# Schemas
# ============================================================
class CharacterPayload(BaseModel):
    face_signature: str = ""
    outfit: str = ""
    age_apparent: Optional[str] = None
    gender: Optional[str] = None
    voice_persona: Optional[str] = None


class ProductPayload(BaseModel):
    packaging_description: str = ""
    hero_features: list[str] = Field(default_factory=list)
    color_palette: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)


class StoryboardPayload(BaseModel):
    prompt: str = ""
    aspect_ratio: str = "9:16"


class CreateAssetRequest(BaseModel):
    type: AssetType
    name: str = Field(..., min_length=1, max_length=120)
    image_url: str = Field(..., min_length=1)
    payload: dict = Field(default_factory=dict)
    tags: str = ""


class UpdateAssetRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    image_url: Optional[str] = None
    payload: Optional[dict] = None
    tags: Optional[str] = None


class CreateAutonomousPinRequest(BaseModel):
    asset_id: str = Field(..., min_length=1)
    role: str = Field(..., min_length=2, max_length=80)
    target_market: str = Field("auto", max_length=40)
    niche: str = Field("any", max_length=80)
    series_key: str = Field("", max_length=120)
    priority: int = Field(50, ge=0, le=100)
    status: str = Field("active", description="active|paused|archived")
    notes: str = Field("", max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateAutonomousPinRequest(BaseModel):
    role: Optional[str] = Field(None, min_length=2, max_length=80)
    target_market: Optional[str] = Field(None, max_length=40)
    niche: Optional[str] = Field(None, max_length=80)
    series_key: Optional[str] = Field(None, max_length=120)
    priority: Optional[int] = Field(None, ge=0, le=100)
    status: Optional[str] = Field(None, description="active|paused|archived")
    notes: Optional[str] = Field(None, max_length=1000)
    metadata: Optional[dict[str, Any]] = None


# ============================================================
# CRUD
# ============================================================
@router.get("/")
async def list_assets(
    type: Optional[AssetType] = None,
    q: Optional[str] = None,
    limit: int = 100,
):
    """List assets, optionally filter by `type` and search by `q` (name/tags).

    Sorted by `last_used_at` desc so recently-applied refs surface first.
    """
    return {
        "items": assets_store.list_assets(type_filter=type, search=q, limit=limit),
    }


@router.get("/autonomous-pins")
async def list_autonomous_pins(
    status: Optional[str] = "active",
    target_market: Optional[str] = None,
    niche: Optional[str] = None,
    role: Optional[str] = None,
    series_key: Optional[str] = None,
    limit: int = 100,
):
    """List approved autonomous asset pins for series/brand continuity."""
    try:
        return {
            "stats": autonomous_asset_pins.stats(),
            "items": autonomous_asset_pins.list_pins(
                status=status,
                target_market=target_market,
                niche=niche,
                role=role,
                series_key=series_key,
                limit=limit,
            ),
        }
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/autonomous-pins")
async def create_autonomous_pin(request: CreateAutonomousPinRequest):
    """Approve an existing asset as an autonomous continuity anchor."""
    try:
        return autonomous_asset_pins.create_pin(**request.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/autonomous-pins/{pin_id}")
async def get_autonomous_pin(pin_id: str):
    pin = autonomous_asset_pins.get_pin(pin_id)
    if not pin:
        raise HTTPException(404, f"pin '{pin_id}' not found")
    return pin


@router.patch("/autonomous-pins/{pin_id}")
async def update_autonomous_pin(pin_id: str, request: UpdateAutonomousPinRequest):
    try:
        pin = autonomous_asset_pins.update_pin(
            pin_id,
            **request.model_dump(exclude_unset=True),
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if not pin:
        raise HTTPException(404, f"pin '{pin_id}' not found")
    return pin


@router.delete("/autonomous-pins/{pin_id}")
async def delete_autonomous_pin(pin_id: str):
    if not autonomous_asset_pins.delete_pin(pin_id):
        raise HTTPException(404, f"pin '{pin_id}' not found")
    return {"ok": True, "pin_id": pin_id}


@router.post("/")
async def create_asset(request: CreateAssetRequest):
    """Save a new asset. Returns full record with server-assigned `id`."""
    if request.type == "character":
        CharacterPayload(**request.payload)  # validate (raise 422 on bad shape)
    elif request.type == "product":
        ProductPayload(**request.payload)
    elif request.type == "storyboard":
        StoryboardPayload(**request.payload)
    return assets_store.create_asset(
        type=request.type,
        name=request.name,
        image_url=request.image_url,
        payload=request.payload,
        tags=request.tags,
    )


@router.get("/{asset_id}")
async def get_asset(asset_id: str):
    a = assets_store.get_asset(asset_id)
    if not a:
        raise HTTPException(404, f"asset '{asset_id}' not found")
    return a


@router.patch("/{asset_id}")
async def update_asset(asset_id: str, request: UpdateAssetRequest):
    out = assets_store.update_asset(
        asset_id,
        name=request.name,
        image_url=request.image_url,
        payload=request.payload,
        tags=request.tags,
    )
    if not out:
        raise HTTPException(404, f"asset '{asset_id}' not found")
    return out


@router.post("/{asset_id}/touch")
async def touch_asset(asset_id: str):
    """Mark asset as recently used (bumps it to the top of the list)."""
    if not assets_store.get_asset(asset_id):
        raise HTTPException(404, f"asset '{asset_id}' not found")
    assets_store.touch_used(asset_id)
    return {"ok": True, "asset_id": asset_id}


@router.delete("/{asset_id}")
async def delete_asset(asset_id: str):
    if not assets_store.delete_asset(asset_id):
        raise HTTPException(404, f"asset '{asset_id}' not found")
    return {"ok": True, "asset_id": asset_id}
