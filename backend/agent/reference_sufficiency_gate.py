"""Reference sufficiency gate for autonomous Seedance jobs.

Seedance 2.0 can generate from text, but consistent production quality depends
on having the right references for the requested niche and runtime. This module
separates "renderable" from "top-tier ready" without forcing extra UI controls.
"""
from __future__ import annotations

from typing import Any


_PRODUCT_NICHES = {"beauty", "food", "fashion", "ecommerce_catalog", "ugc_review", "tech", "app_saas", "automotive"}
_CHARACTER_NICHES = {"drama", "anime_comic", "music_video", "education", "documentary", "fitness", "kids_family", "medical_wellness"}
_LOCATION_NICHES = {"real_estate", "restaurant_hospitality", "travel", "documentary", "lifestyle"}
_SFX_NICHES = {"asmr", "food", "beauty", "music_video"}
_CLAIMS_REVIEW_NICHES = {"finance_education", "medical_wellness", "documentary", "kids_family"}


def build_reference_sufficiency_report(
    *,
    niche: str,
    runtime_payload: dict[str, Any],
    reference_counts: dict[str, int],
    has_dialogue: bool,
    target_market: str = "auto",
) -> dict[str, Any]:
    """Return an inspectable quality gate for user/pinned references."""
    refs = {
        "images": max(0, int(reference_counts.get("images") or 0)),
        "videos": max(0, int(reference_counts.get("videos") or 0)),
        "audios": max(0, int(reference_counts.get("audios") or 0)),
        "pinned_assets": max(0, int(reference_counts.get("pinned_assets") or 0)),
    }
    runtime_class = str(runtime_payload.get("runtime_class") or "short")
    duration_s = int(runtime_payload.get("target_duration_s") or 0)
    visual_anchor_count = refs["images"] + refs["pinned_assets"]
    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, detail: str, *, recommendation: str = "") -> None:
        checks.append({
            "name": name,
            "status": status,
            "detail": detail,
            "recommendation": recommendation,
        })

    _cap_checks(add, refs)
    _visual_anchor_checks(
        add,
        niche=niche,
        runtime_class=runtime_class,
        duration_s=duration_s,
        visual_anchor_count=visual_anchor_count,
    )
    _motion_checks(add, niche=niche, refs=refs, runtime_class=runtime_class)
    _audio_checks(add, niche=niche, refs=refs, has_dialogue=has_dialogue)
    _market_checks(add, niche=niche, target_market=target_market, has_dialogue=has_dialogue)

    hard_failures = [item for item in checks if item["status"] == "fail"]
    warnings = [item for item in checks if item["status"] == "warn"]
    status = "fail" if hard_failures else ("warn" if warnings else "pass")
    score = max(
        0,
        100
        - 30 * len(hard_failures)
        - 8 * len(warnings)
        - _quality_gap_penalty(niche=niche, runtime_class=runtime_class, refs=refs, has_dialogue=has_dialogue),
    )
    return {
        "schema_version": "cinejelly.reference_sufficiency_gate.v1",
        "status": status,
        "score": score,
        "top_tier_ready": status == "pass" and score >= 85,
        "render_blocking": bool(hard_failures),
        "runtime_class": runtime_class,
        "target_duration_s": duration_s,
        "niche": niche,
        "target_market": target_market,
        "reference_counts": refs,
        "minimum_contract": _minimum_contract(niche=niche, runtime_class=runtime_class, has_dialogue=has_dialogue),
        "optimal_contract": _optimal_contract(niche=niche, runtime_class=runtime_class, has_dialogue=has_dialogue),
        "checks": checks,
        "missing_for_top_tier": [
            item["name"] for item in checks
            if item["status"] in {"warn", "fail"}
        ],
        "next_best_action": _next_best_action(checks),
    }


def _cap_checks(add: Any, refs: dict[str, int]) -> None:
    if refs["images"] > 9:
        add("seedance_image_cap", "fail", "Image references exceed Seedance 2.0 cap of 9.", recommendation="Reduce or merge image refs before render.")
    if refs["videos"] > 3:
        add("seedance_video_cap", "fail", "Video references exceed Seedance 2.0 cap of 3.", recommendation="Keep only camera/motion/pacing references.")
    if refs["audios"] > 3:
        add("seedance_audio_cap", "fail", "Audio references exceed Seedance 2.0 cap of 3.", recommendation="Keep voice/beat/SFX references only.")
    if refs["images"] + refs["videos"] + refs["audios"] > 12:
        add("seedance_mixed_cap", "fail", "Mixed references exceed practical Seedance 2.0 cap of 12.", recommendation="Prioritize identity/product/style/motion/audio anchors.")


def _visual_anchor_checks(
    add: Any,
    *,
    niche: str,
    runtime_class: str,
    duration_s: int,
    visual_anchor_count: int,
) -> None:
    needs_product = niche in _PRODUCT_NICHES
    needs_character = niche in _CHARACTER_NICHES
    needs_location = niche in _LOCATION_NICHES
    long_form = runtime_class in {"micro_film", "short_film", "episode"} or duration_s > 60
    if visual_anchor_count == 0 and (needs_product or needs_character or long_form):
        add(
            "visual_anchor_missing",
            "warn",
            "No image/pinned visual anchor is available for a consistency-sensitive job.",
            recommendation="Add one character/product/style image or approve an asset memory pin.",
        )
        return
    if needs_product and visual_anchor_count < 2 and long_form:
        add(
            "product_anchor_thin",
            "warn",
            "Long product/UGC job has fewer than two product/identity anchors.",
            recommendation="Use at least character/product or product/detail refs.",
        )
    elif needs_character and visual_anchor_count < 2 and long_form:
        add(
            "character_anchor_thin",
            "warn",
            "Long character/story job has fewer than two character/environment anchors.",
            recommendation="Use character identity plus outfit/location/style refs.",
        )
    elif needs_location and visual_anchor_count < 1:
        add(
            "location_anchor_missing",
            "warn",
            "Location-driven niche lacks an environment reference.",
            recommendation="Add room/property/destination/venue image reference.",
        )
    else:
        add("visual_anchor_coverage", "pass", f"Visual anchor coverage is plausible with {visual_anchor_count} image/pinned refs.")


def _motion_checks(add: Any, *, niche: str, refs: dict[str, int], runtime_class: str) -> None:
    if refs["videos"] > 0:
        add("motion_reference", "pass", f"{refs['videos']} video reference(s) can guide camera/motion/pacing.")
        return
    if niche in {"real_estate", "travel", "fitness", "music_video", "automotive", "drama"} or runtime_class in {"short_film", "episode"}:
        add(
            "motion_reference_missing",
            "warn",
            "No video motion/camera reference for a motion-sensitive or long-form job.",
            recommendation="Add one short camera/motion/pacing reference when possible.",
        )
    else:
        add("motion_reference", "pass", "Motion references are optional for this compact job.")


def _audio_checks(add: Any, *, niche: str, refs: dict[str, int], has_dialogue: bool) -> None:
    if has_dialogue and refs["audios"] == 0:
        add(
            "dialogue_audio_missing",
            "warn",
            "Dialogue/VO is expected but no audio reference exists.",
            recommendation="Add a voice/VO sample or keep dialogue as subtitles/VO generated downstream.",
        )
        return
    if niche in _SFX_NICHES and refs["audios"] == 0:
        add(
            "sensory_audio_missing",
            "warn",
            "Sensory niche lacks beat/SFX/ambience reference.",
            recommendation="Add one beat/SFX/texture audio reference for tactile timing.",
        )
    elif refs["audios"] > 0:
        add("audio_reference", "pass", f"{refs['audios']} audio reference(s) available.")
    else:
        add("audio_reference", "pass", "Audio reference is optional for this route.")


def _market_checks(add: Any, *, niche: str, target_market: str, has_dialogue: bool) -> None:
    if target_market in {"vn", "jp", "kr"} and has_dialogue:
        add(
            "localized_dialogue_review",
            "warn",
            "Localized dialogue needs phoneme/lip-sync benchmark review before top-tier claims.",
            recommendation="Benchmark InfiniteTalk/MultiTalk/LipSync candidates for this market.",
        )
    elif niche in _CLAIMS_REVIEW_NICHES:
        add(
            "claims_review",
            "warn",
            "This niche needs claim/safety review even with good references.",
            recommendation="Require human/model review of script, caption, and final claims.",
        )
    else:
        add("market_reference_fit", "pass", f"Reference policy fits target market {target_market or 'auto'}.")


def _minimum_contract(*, niche: str, runtime_class: str, has_dialogue: bool) -> list[str]:
    contract = ["idea + one concrete visual subject/action"]
    if niche in _PRODUCT_NICHES:
        contract.append("one product or creator/product image anchor")
    if niche in _CHARACTER_NICHES:
        contract.append("one character identity or approved asset pin")
    if runtime_class in {"micro_film", "short_film", "episode"}:
        contract.append("one visual anchor plus scene memory/last-frame handoffs")
    if has_dialogue:
        contract.append("dialogue route review; audio ref preferred")
    return contract


def _optimal_contract(*, niche: str, runtime_class: str, has_dialogue: bool) -> list[str]:
    contract = ["identity/product/style image refs prioritized under Seedance cap"]
    if niche in _PRODUCT_NICHES:
        contract.extend(["product hero image", "product detail image", "creator/style image"])
    if niche in _LOCATION_NICHES:
        contract.extend(["environment/location image", "camera walkthrough or motion video"])
    if niche in _CHARACTER_NICHES:
        contract.extend(["character face/outfit image", "environment/style image"])
    if runtime_class in {"micro_film", "short_film", "episode"}:
        contract.extend(["previous-scene final frame bridge", "scene opening/closing image intent"])
    if has_dialogue:
        contract.append("voice/audio sample plus benchmarked dialogue model lane")
    return list(dict.fromkeys(contract))


def _quality_gap_penalty(*, niche: str, runtime_class: str, refs: dict[str, int], has_dialogue: bool) -> int:
    penalty = 0
    visual = refs["images"] + refs["pinned_assets"]
    if runtime_class in {"micro_film", "short_film", "episode"} and visual < 2:
        penalty += 8
    if niche in _PRODUCT_NICHES and visual < 2:
        penalty += 6
    if has_dialogue and refs["audios"] == 0:
        penalty += 5
    return penalty


def _next_best_action(checks: list[dict[str, Any]]) -> str:
    for item in checks:
        if item["status"] == "fail":
            return str(item.get("recommendation") or item.get("detail") or "fix_reference_caps")
    for item in checks:
        if item["status"] == "warn":
            return str(item.get("recommendation") or item.get("detail") or "add_stronger_references")
    return "references_are_sufficient_for_current_route"


__all__ = ["build_reference_sufficiency_report"]
