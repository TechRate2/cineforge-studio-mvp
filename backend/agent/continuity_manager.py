"""Continuity Manager — quản lý Continuity Bible xuyên video.

Mục đích:
    - Validate Bible (character ids, ref bindings, duration sum)
    - Inject Bible vào Scene Generation prompts (face_signature / style / etc.)
    - Sync state khi user edit shot ở UI (re-bind refs, re-chain previous_shot_id)

KHÔNG gọi LLM. Pure data ops.
"""
from __future__ import annotations

from typing import Optional
from loguru import logger

from agent.schemas import (
    ContinuityBible, Shot, Character, Product, ReferenceAsset,
    DirectorPlan, StoryboardFrame,
)


class ContinuityError(ValueError):
    """Raise khi Bible/Shot có inconsistency mà không sửa được tự động."""


def validate_plan(plan: DirectorPlan, target_duration_s: int, tolerance_s: int = 2) -> list[str]:
    """Validate a DirectorPlan and return a list of soft warnings (empty = clean).

    Raises `ContinuityError` only for hard failures that would break the render
    (no shots, duplicate shot_ids, previous_shot_id pointing nowhere). Soft
    issues (unknown char_id, out-of-range reference_indices, etc.) are returned
    as warnings so the caller can still render with `auto_chain_shots()` /
    `references_for_shot()` recovery.
    """
    warnings: list[str] = []
    bible = plan.continuity_bible
    shots = plan.shot_list

    if not shots:
        raise ContinuityError("shot_list rỗng — Director Agent fail")

    # 1. duration sum
    total = sum(s.duration_s for s in shots)
    if abs(total - target_duration_s) > tolerance_s:
        warnings.append(
            f"duration sum {total}s lệch target {target_duration_s}s "
            f"(tolerance ±{tolerance_s}s)"
        )

    # 2. shot_id unique
    ids = [s.shot_id for s in shots]
    if len(ids) != len(set(ids)):
        dupes = sorted({sid for sid in ids if ids.count(sid) > 1})
        raise ContinuityError(f"shot_id duplicate: {dupes}")

    # 3. char_ids / product_ids must exist trong Bible
    char_ids_known = {c.id for c in bible.characters}
    prod_ids_known = {p.id for p in bible.products}

    for s in shots:
        for cid in s.continuity.character_ids:
            if cid not in char_ids_known:
                warnings.append(f"{s.shot_id}.character_ids '{cid}' không có trong bible.characters")
        for pid in s.continuity.product_ids:
            if pid not in prod_ids_known:
                warnings.append(f"{s.shot_id}.product_ids '{pid}' không có trong bible.products")

    # 4. reference_indices must be valid
    ref_count = len(bible.reference_assets)
    for s in shots:
        for ri in s.continuity.reference_indices:
            if ri < 0 or ri >= ref_count:
                warnings.append(
                    f"{s.shot_id}.reference_indices[{ri}] out of range "
                    f"(have {ref_count} refs)"
                )

    # 5. previous_shot_id → shot_id phải tồn tại + chỉ trỏ về shot trước nó
    #    Soft: `sanitize_plan()` clears bad refs so render still proceeds.
    id_to_idx = {s.shot_id: s.index for s in shots}
    for s in shots:
        psid = s.continuity.previous_shot_id
        if psid is None:
            continue
        if psid not in id_to_idx:
            warnings.append(
                f"{s.shot_id}.previous_shot_id='{psid}' không tồn tại — sẽ bị clear"
            )
        elif id_to_idx[psid] >= s.index:
            warnings.append(
                f"{s.shot_id}.previous_shot_id='{psid}' trỏ về shot sau hoặc bằng — "
                f"chain phải đi xuôi thời gian"
            )

    # 6. reference_assets.apply_to_shots phải reference shot_id tồn tại
    for r in bible.reference_assets:
        for sid in r.apply_to_shots:
            if sid not in id_to_idx:
                warnings.append(
                    f"reference_assets[{r.index}].apply_to_shots '{sid}' "
                    f"không tồn tại"
                )

    # 7. storyboard_grid 1:1 với shot_list
    storyboard_ids = {f.shot_id for f in plan.storyboard_grid}
    if storyboard_ids and storyboard_ids != set(ids):
        warnings.append(
            f"storyboard_grid không 1:1 với shot_list "
            f"(missing={set(ids) - storyboard_ids}, extra={storyboard_ids - set(ids)})"
        )

    return warnings


# Sprint2 M16 — Severity tiers for plan validation warnings.
# Lets the UI bucket "must fix" vs "ok to proceed" vs "FYI" instead of dumping
# a flat 15-line list at the user.
_HIGH_KEYS = (
    "duration sum",                # timeline off by > tolerance
    "previous_shot_id",            # broken chain reference (sanitize will null)
    "không tồn tại",               # missing IDs
)
_LOW_KEYS = (
    "storyboard_grid",             # cosmetic — storyboard images optional
    "apply_to_shots",              # bibliography binding, not render-blocking
)


def classify_warnings(warnings: list[str]) -> dict[str, list[str]]:
    """Bucket validate_plan() warning strings by severity.

    Returns `{"errors": [], "warnings": [], "info": []}` with mutually-exclusive
    lists. `errors` are things the user MUST fix to render; `warnings` are
    things sanitize_plan() will silently fix; `info` are cosmetic.

    Check LOW keys first — they're more specific (e.g. "apply_to_shots") and
    would otherwise overlap with HIGH catch-all keys like "không tồn tại".
    """
    out = {"errors": [], "warnings": [], "info": []}
    for w in warnings:
        wl = w.lower()
        if any(k in wl for k in (kk.lower() for kk in _LOW_KEYS)):
            out["info"].append(w)
        elif any(k in wl for k in (kk.lower() for kk in _HIGH_KEYS)):
            out["warnings"].append(w)  # high but sanitize-recoverable
        else:
            out["warnings"].append(w)
    return out


def validate_plan_against_model(plan: DirectorPlan, user_model: str) -> list[str]:
    """Check every shot against the chosen model's hard capability limits.

    Returns a list of human-readable violations (empty = compatible). Called by
    `/director/generate` BEFORE dispatching render — so the API can return 400
    with actionable suggestions instead of failing midway through the render.

    Example violations:
        "S3.duration_s=7 không hợp lệ — model wan_2_7 chỉ chấp nhận discrete [5, 10]s"
        "S2.reference_indices có 5 refs nhưng vidu_q3 max 4"
    """
    from agent.model_capabilities import capabilities_for, validate_shot_against_model

    cap = capabilities_for(user_model)
    out: list[str] = []
    for s in plan.shot_list:
        violations = validate_shot_against_model(s.model_dump(), cap)
        for v in violations:
            out.append(f"{s.shot_id}: {v}")
    return out


def sanitize_plan(plan: DirectorPlan) -> DirectorPlan:
    """Drop invalid `reference_indices` and clamp `apply_to_shots`.

    Sprint2 M7 — instead of silently dropping bad refs we LOG every drop so
    the user can see in server logs exactly which shot lost which ref.
    Returns the plan (mutated in-place for backward compat).
    """
    bible = plan.continuity_bible
    valid_shot_ids = {s.shot_id for s in plan.shot_list}
    ref_count = len(bible.reference_assets)
    dropped_refs: list[str] = []
    cleared_chains: list[str] = []
    cleared_apply: list[str] = []

    for s in plan.shot_list:
        before = list(s.continuity.reference_indices)
        s.continuity.reference_indices = [
            i for i in before
            if isinstance(i, int) and 0 <= i < ref_count
        ]
        bad = [i for i in before if i not in s.continuity.reference_indices]
        if bad:
            dropped_refs.append(f"{s.shot_id}: dropped indices {bad} (have {ref_count} refs)")
        if s.continuity.previous_shot_id and s.continuity.previous_shot_id not in valid_shot_ids:
            cleared_chains.append(f"{s.shot_id}: previous_shot_id='{s.continuity.previous_shot_id}' → null")
            s.continuity.previous_shot_id = None

    for r in bible.reference_assets:
        before_apply = list(r.apply_to_shots)
        r.apply_to_shots = [sid for sid in before_apply if sid in valid_shot_ids]
        bad_apply = [sid for sid in before_apply if sid not in r.apply_to_shots]
        if bad_apply:
            cleared_apply.append(f"ref[{r.index}]: dropped apply_to_shots {bad_apply}")

    if dropped_refs or cleared_chains or cleared_apply:
        for msg in dropped_refs[:5]:
            logger.warning(f"[sanitize_plan] {msg}")
        for msg in cleared_chains[:5]:
            logger.warning(f"[sanitize_plan] {msg}")
        for msg in cleared_apply[:5]:
            logger.warning(f"[sanitize_plan] {msg}")

    return plan


def normalize_timeline(shots: list[Shot]) -> list[Shot]:
    """Re-compute start_s / end_s từ duration_s đảm bảo timeline liền mạch.

    Nếu Director Agent output start_s/end_s lệch (vd: gap giữa shots), normalize lại
    để pipeline render dùng được. KHÔNG đụng duration_s (giữ ý đồ Director).
    """
    cursor = 0.0
    for s in shots:
        s.start_s = round(cursor, 2)
        s.end_s = round(cursor + s.duration_s, 2)
        cursor = s.end_s
    return shots


def find_character(bible: ContinuityBible, char_id: str) -> Optional[Character]:
    for c in bible.characters:
        if c.id == char_id:
            return c
    return None


def find_product(bible: ContinuityBible, prod_id: str) -> Optional[Product]:
    for p in bible.products:
        if p.id == prod_id:
            return p
    return None


def references_for_shot(bible: ContinuityBible, shot: Shot) -> list[ReferenceAsset]:
    """Trả về list ReferenceAsset áp dụng cho shot này.

    Union của:
        - shot.continuity.reference_indices (explicit)
        - reference_assets có apply_to_shots chứa shot.shot_id (universal binding)

    Dedupe theo index, preserve order (character_anchor → product_hero → others).
    """
    by_index = {r.index: r for r in bible.reference_assets}
    selected: dict[int, ReferenceAsset] = {}

    # 1. Explicit refs từ shot
    for idx in shot.continuity.reference_indices:
        if idx in by_index:
            selected[idx] = by_index[idx]

    # 2. Universal binding qua apply_to_shots
    for r in bible.reference_assets:
        if shot.shot_id in r.apply_to_shots:
            selected[r.index] = r

    # Sort by role priority: character_anchor > product_hero > product_detail > style > env > brand > unknown
    role_order = {
        "character_anchor": 0,
        "secondary_character": 1,
        "product_hero": 2,
        "product_detail": 3,
        "brand_asset": 4,
        "style_reference": 5,
        "environment": 6,
        "unknown": 7,
    }
    return sorted(
        selected.values(),
        key=lambda r: (role_order.get(r.role, 99), r.index),
    )


def inject_bible_context_into_prompt(
    bible: ContinuityBible,
    shot: Shot,
    base_prompt: str,
) -> str:
    """Helper — prepend character anchor + style anchor vào base prompt.

    Dùng làm fallback khi Scene Generation Agent fail hoặc khi build prompt
    không qua LLM. Lightweight string concat — không LLM call.
    """
    pieces: list[str] = []

    # Character anchors
    for cid in shot.continuity.character_ids:
        c = find_character(bible, cid)
        if c and c.face_signature:
            pieces.append(f"[{c.name}: {c.face_signature}, wearing {c.outfit}]")

    # Product anchors
    for pid in shot.continuity.product_ids:
        p = find_product(bible, pid)
        if p:
            packaging = p.packaging_description or ""
            pieces.append(f"[{p.name}: {packaging}]" if packaging else f"[{p.name}]")

    # Style anchor — shot-level wins over bible
    style_line = shot.continuity.style_anchor or (
        f"{bible.visual_style.cinematography}, "
        f"{bible.visual_style.color_grading}, "
        f"{bible.visual_style.lighting_design}"
    )
    pieces.append(f"Style: {style_line}.")

    return " ".join(pieces) + " " + base_prompt


def build_negative_prompt(bible: ContinuityBible) -> str:
    """Build negative prompt từ bible.constraints.must_avoid + brand_safety + defaults."""
    defaults = [
        "extra fingers",
        "warped face",
        "watermark",
        "low quality",
        "blurry text overlay",
        "deformed limbs",
    ]
    items = list(bible.constraints.must_avoid) + list(bible.constraints.brand_safety) + defaults
    # Dedupe preserving order
    seen = set()
    out = []
    for it in items:
        k = it.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(it.strip())
    return ", ".join(out)


def auto_chain_shots(shots: list[Shot], reset_on_purpose_change: bool = True) -> list[Shot]:
    """Heuristic: nếu shot[i].continuity.previous_shot_id None nhưng cùng character
    + cùng purpose family với shot[i-1] → auto-set previous_shot_id = shot[i-1].shot_id.

    Gọi sau khi Director Agent return — đảm bảo identity chain mạnh dù LLM quên set.
    Reset (giữ None) khi purpose family đổi (vd: từ "hook" sang "cta") nếu flag bật.
    """
    purpose_family = {
        "hook": "open", "reveal": "open", "tease": "open",
        "problem": "middle", "solution": "middle", "demo": "middle", "proof": "middle",
        "cta": "close", "closing": "close", "outro": "close",
        "transition": "transition",
    }
    for i in range(1, len(shots)):
        prev = shots[i - 1]
        cur = shots[i]
        if cur.continuity.previous_shot_id is not None:
            continue
        # Không chain qua transition
        if purpose_family.get(cur.purpose, "?") == "transition":
            continue
        if purpose_family.get(prev.purpose, "?") == "transition":
            continue

        same_char = bool(set(prev.continuity.character_ids) & set(cur.continuity.character_ids))
        same_family = (
            not reset_on_purpose_change
            or purpose_family.get(prev.purpose) == purpose_family.get(cur.purpose)
        )
        if same_char and same_family:
            cur.continuity.previous_shot_id = prev.shot_id
            logger.debug(f"[continuity] auto-chained {cur.shot_id} ← {prev.shot_id}")
    return shots


def ensure_storyboard_complete(plan: DirectorPlan) -> DirectorPlan:
    """Nếu storyboard_grid thiếu frame cho shot nào → tạo entry placeholder.

    Director Agent thường output đủ, nhưng phòng trường hợp LLM cắt ngắn.
    """
    existing = {f.shot_id for f in plan.storyboard_grid}
    for s in plan.shot_list:
        if s.shot_id not in existing:
            placeholder = StoryboardFrame(
                shot_id=s.shot_id,
                prompt=inject_bible_context_into_prompt(
                    plan.continuity_bible, s,
                    base_prompt=f"{s.visual.subject}, {s.visual.action}, "
                                f"{s.visual.camera_shot} {s.visual.camera_movement}, "
                                f"{s.visual.composition}, {s.visual.background}",
                ),
                image_size="1080*1920" if plan.continuity_bible.aspect_ratio == "9:16"
                            else "1920*1080" if plan.continuity_bible.aspect_ratio == "16:9"
                            else "1024*1024",
            )
            plan.storyboard_grid.append(placeholder)
    # Sort theo shot order
    order = {s.shot_id: s.index for s in plan.shot_list}
    plan.storyboard_grid.sort(key=lambda f: order.get(f.shot_id, 999))
    return plan
