"""Autonomous asset memory bridge.

The Asset Library already supports reusable character/product/storyboard refs.
This helper lets Autonomous Director save useful image references automatically
after RoleTagger assigns their roles, so future series/brand workflows can reuse
the same character, product, environment, and style anchors.
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from core import assets_store, autonomous_asset_pins


_ASSET_TYPE_PRIORITY = {
    "character": 3,
    "product": 2,
    "storyboard": 1,
}

_ROLE_TO_ASSET_TYPE = {
    "character_anchor": "character",
    "secondary_character": "character",
    "product_hero": "product",
    "product_detail": "product",
    "brand_asset": "product",
    "style_reference": "storyboard",
    "environment": "storyboard",
}


def suggest_autonomous_assets(
    *,
    user_idea: str,
    niche: str,
    target_market: str,
    limit: int = 6,
) -> dict[str, Any]:
    """Return conservative reusable asset candidates for the next autonomous run.

    This intentionally does not inject old assets into render references. It only
    exposes ranked candidates so the API/UI/artifact can show memory context, and
    a future approved step can decide whether to pin them into a continuity bible.
    """
    candidates: list[dict[str, Any]] = []
    idea_lc = user_idea.lower()
    niche_lc = (niche or "").lower()
    market_lc = (target_market or "auto").lower()

    for asset in assets_store.list_assets(limit=500):
        score, reasons = _score_asset_candidate(
            asset=asset,
            idea_lc=idea_lc,
            niche_lc=niche_lc,
            market_lc=market_lc,
        )
        if score <= 0:
            continue
        payload = asset.get("payload") or {}
        candidates.append({
            "asset_id": asset.get("id"),
            "type": asset.get("type"),
            "name": asset.get("name"),
            "image_url": asset.get("image_url"),
            "role": payload.get("role"),
            "tags": asset.get("tags", ""),
            "score": score,
            "reasons": reasons,
            "last_used_at": asset.get("last_used_at"),
            "updated_at": asset.get("updated_at"),
        })

    candidates.sort(
        key=lambda item: (
            item["score"],
            1 if item.get("last_used_at") else 0,
            item.get("updated_at") or "",
        ),
        reverse=True,
    )
    selected = candidates[: max(0, limit)]
    pinned = autonomous_asset_pins.list_pins(
        target_market=market_lc,
        niche=niche_lc,
        status="active",
        limit=limit,
    )
    return {
        "enabled": True,
        "mode": "metadata_with_approved_pins",
        "injected_into_render": False,
        "pin_count": len(pinned),
        "pinned": pinned,
        "count": len(selected),
        "items": selected,
        "policy": "Suggestions are ranked by niche/market/tag fit. Approved pins are surfaced separately. Render-time auto-selection is handled by select_approved_asset_pins_for_render with explicit pins taking priority.",
    }


def select_approved_asset_pins_for_render(
    *,
    user_idea: str,
    niche: str,
    target_market: str,
    series_key: str = "",
    explicit_pin_ids: list[str] | None = None,
    limit: int = 6,
) -> dict[str, Any]:
    """Select safe approved pins for a render when the user did not pick enough.

    Explicit pins always win. Auto-selection only considers active pins with an
    image-backed asset and ranks by series, niche, market, role, priority, and
    idea-token match.
    """
    explicit = [pid for pid in (explicit_pin_ids or []) if pid]
    explicit_set = set(explicit)
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set(explicit_set)
    market = (target_market or "auto").strip().lower()
    niche_lc = (niche or "any").strip().lower()
    series = (series_key or "").strip()

    pools: list[dict[str, Any]] = []
    if series:
        pools.extend(autonomous_asset_pins.list_pins(
            status="active",
            target_market=None if market == "auto" else market,
            niche=niche_lc if niche_lc and niche_lc != "any" else None,
            series_key=series,
            limit=100,
        ))
    pools.extend(autonomous_asset_pins.list_pins(
        status="active",
        target_market=None if market == "auto" else market,
        niche=niche_lc if niche_lc and niche_lc != "any" else None,
        limit=150,
    ))

    idea_lc = (user_idea or "").lower()
    for pin in pools:
        pin_id = str(pin.get("id") or "")
        if not pin_id or pin_id in seen:
            continue
        asset = pin.get("asset") or {}
        if not asset.get("image_url"):
            continue
        score, reasons = _score_pin_candidate(
            pin=pin,
            idea_lc=idea_lc,
            niche_lc=niche_lc,
            market_lc=market,
            series_key=series,
        )
        candidates.append({
            "pin_id": pin_id,
            "asset_id": pin.get("asset_id"),
            "role": pin.get("role"),
            "priority": pin.get("priority"),
            "target_market": pin.get("target_market"),
            "niche": pin.get("niche"),
            "series_key": pin.get("series_key"),
            "score": score,
            "reasons": reasons,
        })
        seen.add(pin_id)

    candidates.sort(key=lambda item: (item["score"], int(item.get("priority") or 0)), reverse=True)
    selected = candidates[: max(0, min(int(limit or 0), 12 - len(explicit)))]
    return {
        "enabled": True,
        "mode": "explicit_plus_ranked_approved_pins",
        "explicit_pin_ids": explicit,
        "auto_selected_pin_ids": [item["pin_id"] for item in selected],
        "count": len(selected),
        "candidates_considered": len(candidates),
        "selected": selected,
        "policy": "Auto-select only active approved image pins; explicit user pins keep priority; Seedance image cap is enforced downstream.",
    }


def remember_autonomous_assets(
    *,
    tagged_references: list[Any],
    user_idea: str,
    niche: str,
    target_market: str,
    plan_id: str,
) -> dict[str, Any]:
    """Create/touch reusable assets from tagged image references."""
    created: list[dict[str, Any]] = []
    touched: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    existing = assets_store.list_assets(limit=1000)
    by_url = {a.get("image_url"): a for a in existing if a.get("image_url")}

    for ref in tagged_references:
        if getattr(ref, "modality", None) != "image":
            continue
        role = str(getattr(ref, "role", "") or "unknown")
        asset_type = _ROLE_TO_ASSET_TYPE.get(role)
        url = str(getattr(ref, "url", "") or "")
        if not asset_type:
            skipped.append({"role": role, "reason": "role_not_memorable"})
            continue
        if not url or len(url) > 5000:
            skipped.append({"role": role, "reason": "empty_or_too_large_url"})
            continue

        if url in by_url:
            assets_store.touch_used(by_url[url]["id"])
            touched.append({
                "asset_id": by_url[url]["id"],
                "type": by_url[url]["type"],
                "role": role,
            })
            continue

        asset = assets_store.create_asset(
            type=asset_type,
            name=_asset_name(asset_type, role, len(created) + 1),
            image_url=url,
            payload=_payload_for(role, ref, user_idea, niche, target_market, plan_id),
            tags=f"autonomous,{niche},{target_market},{role}",
        )
        by_url[url] = asset
        created.append({
            "asset_id": asset["id"],
            "type": asset["type"],
            "role": role,
        })

    out = {
        "enabled": True,
        "created_count": len(created),
        "touched_count": len(touched),
        "skipped_count": len(skipped),
        "created": created,
        "touched": touched,
        "skipped": skipped[:10],
    }
    logger.info(
        f"[asset_memory] plan={plan_id} created={len(created)} touched={len(touched)} skipped={len(skipped)}"
    )
    return out


def _score_asset_candidate(
    *,
    asset: dict[str, Any],
    idea_lc: str,
    niche_lc: str,
    market_lc: str,
) -> tuple[int, list[str]]:
    tags = str(asset.get("tags") or "").lower()
    name = str(asset.get("name") or "").lower()
    payload = asset.get("payload") or {}
    role = str(payload.get("role") or "").lower()
    asset_type = str(asset.get("type") or "").lower()
    haystack = f"{tags} {name} {role}".strip()

    score = 0
    reasons: list[str] = []

    if "autonomous" in tags:
        score += 2
        reasons.append("autonomous_asset")
    if niche_lc and niche_lc in haystack:
        score += 5
        reasons.append("niche_match")
    if market_lc and market_lc != "auto" and market_lc in haystack:
        score += 3
        reasons.append("market_match")
    if role and role.replace("_", " ") in idea_lc:
        score += 2
        reasons.append("idea_mentions_role")

    for token in _important_idea_tokens(idea_lc):
        if token in haystack:
            score += 1
            reasons.append(f"idea_token:{token}")
            break

    score += _ASSET_TYPE_PRIORITY.get(asset_type, 0)
    if asset_type:
        reasons.append(f"type_priority:{asset_type}")

    return score, reasons


def _score_pin_candidate(
    *,
    pin: dict[str, Any],
    idea_lc: str,
    niche_lc: str,
    market_lc: str,
    series_key: str,
) -> tuple[int, list[str]]:
    asset = pin.get("asset") or {}
    tags = str(asset.get("tags") or "").lower()
    name = str(asset.get("name") or "").lower()
    role = str(pin.get("role") or "").lower()
    pin_niche = str(pin.get("niche") or "").lower()
    pin_market = str(pin.get("target_market") or "").lower()
    pin_series = str(pin.get("series_key") or "")
    haystack = f"{tags} {name} {role} {pin_niche} {pin_market} {pin_series.lower()}"
    score = int(pin.get("priority") or 50)
    reasons = ["priority"]

    role_weight = {
        "character_anchor": 20,
        "product_hero": 18,
        "style_reference": 10,
        "environment": 8,
        "brand_asset": 8,
    }.get(role, 4)
    score += role_weight
    reasons.append(f"role:{role or 'unknown'}")

    if series_key and pin_series == series_key:
        score += 35
        reasons.append("series_match")
    elif not pin_series:
        score += 4
        reasons.append("global_series_fallback")
    if niche_lc and pin_niche in {niche_lc, "any"}:
        score += 14 if pin_niche == niche_lc else 5
        reasons.append("niche_match" if pin_niche == niche_lc else "any_niche")
    if market_lc and pin_market in {market_lc, "auto"}:
        score += 10 if pin_market == market_lc else 4
        reasons.append("market_match" if pin_market == market_lc else "auto_market")
    for token in _important_idea_tokens(idea_lc):
        if token in haystack:
            score += 8
            reasons.append(f"idea_token:{token}")
            break
    return score, reasons


def _important_idea_tokens(idea_lc: str) -> list[str]:
    stop = {
        "the", "and", "for", "with", "from", "this", "that", "video",
        "make", "create", "about", "một", "cho", "với", "của", "làm",
        "tạo", "video", "ngắn", "dài", "viral",
    }
    tokens = []
    for raw in idea_lc.replace(",", " ").replace(".", " ").split():
        token = raw.strip("-_:/()[]{}")
        if len(token) < 4 or token in stop:
            continue
        tokens.append(token)
    return tokens[:8]


def _asset_name(asset_type: str, role: str, n: int) -> str:
    if asset_type == "character":
        return "Autonomous Character" if role == "character_anchor" else f"Autonomous Character {n}"
    if asset_type == "product":
        return "Autonomous Product" if role == "product_hero" else f"Autonomous Product {n}"
    return f"Autonomous {role.replace('_', ' ').title()}"


def _payload_for(
    role: str,
    ref: Any,
    user_idea: str,
    niche: str,
    target_market: str,
    plan_id: str,
) -> dict[str, Any]:
    base = {
        "source": "autonomous_director",
        "plan_id": plan_id,
        "role": role,
        "reference_index": getattr(ref, "index", None),
        "confidence": getattr(ref, "confidence", None),
        "tag": getattr(ref, "tag", ""),
        "niche": niche,
        "target_market": target_market,
        "user_idea_excerpt": user_idea[:240],
    }
    if role in ("character_anchor", "secondary_character"):
        return {
            **base,
            "face_signature": f"Auto-tagged {role} from @image_{getattr(ref, 'index', 0) + 1}",
            "outfit": "(inherit from reference image)",
        }
    if role in ("product_hero", "product_detail", "brand_asset"):
        return {
            **base,
            "packaging_description": "(inherit from reference image)",
            "hero_features": [role, niche],
            "forbidden_claims": [],
        }
    return {
        **base,
        "prompt": f"Reusable {role} visual reference for {niche} autonomous videos.",
    }


__all__ = [
    "remember_autonomous_assets",
    "select_approved_asset_pins_for_render",
    "suggest_autonomous_assets",
]
