"""Asset Library — `/api/v1/assets` CRUD endpoints.

Stores Character / Product / Storyboard reference assets so users can reuse
them across multiple Director plans (e.g. the same KOL face / packaging /
hero composition without re-uploading every time).

Backed by `core/assets_store.py` (SQLite). Image URLs can be either external
(after upload to R2/AtlasCloud) or `data:image/…` data-URLs for offline drafts.
"""
from __future__ import annotations

from typing import Optional, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import assets_store


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
