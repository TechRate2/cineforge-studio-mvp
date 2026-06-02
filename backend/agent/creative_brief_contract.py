"""Creative brief contract for chat-first autonomous video input.

This is the Phase 1 input-intelligence layer. It turns loose chat such as
"make me a 45s TikTok serum ad with this image" into a stable, vendor-free
contract that downstream planners, preflight, and UI can inspect before any
LLM or video vendor call is made.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional


_PLATFORM_KEYWORDS = {
    "tiktok": ["tiktok", "tik tok", "tiktok shop"],
    "reels": ["reels", "instagram reels", "ig reels"],
    "youtube_short": ["youtube short", "shorts", "yt shorts"],
    "youtube_long": ["youtube", "youtube long", "long form"],
    "facebook": ["facebook", "fb"],
}

_GOAL_KEYWORDS = {
    "sell_product": [
        "sell", "sale", "launch", "ad", "ads", "promo", "promotion", "conversion",
        "ban hang", "quang cao", "ra mat", "chot don", "tang don", "tang doanh thu",
    ],
    "educate": [
        "explain", "teach", "tutorial", "how to", "guide", "lesson",
        "giai thich", "huong dan", "day", "bai hoc", "chia se kien thuc",
    ],
    "entertain": [
        "drama", "story", "twist", "funny", "viral", "short film",
        "phim ngan", "cau chuyen", "hai", "giai tri", "cu twist",
    ],
    "brand_story": [
        "founder story", "brand story", "documentary", "behind the scenes",
        "cau chuyen thuong hieu", "hanh trinh", "phong su", "tai lieu",
    ],
    "review_proof": [
        "review", "test", "before after", "proof", "demo", "compare",
        "danh gia", "kiem chung", "chung minh", "truoc sau", "so sanh",
    ],
}

_STYLE_KEYWORDS = {
    "cinematic": ["cinematic", "film", "movie", "short film", "dien anh", "phim"],
    "ugc": ["ugc", "creator", "selfie", "honest review", "review chan that"],
    "luxury": ["luxury", "premium", "cao cap", "sang trong"],
    "fast_social": ["fast", "viral", "scroll", "trend", "nhanh", "cuon", "bat trend"],
    "emotional": ["emotional", "touching", "cam xuc", "lay dong", "drama"],
    "asmr": ["asmr", "satisfying", "texture", "macro", "crunch"],
}

_AUDIENCE_KEYWORDS = {
    "gen_z": ["gen z", "genz", "young", "tre", "sinh vien"],
    "parents": ["parent", "mom", "dad", "family", "me bim", "phu huynh", "gia dinh"],
    "founders": ["founder", "startup", "ceo", "chu doanh nghiep", "nha sang lap"],
    "beauty_buyers": ["skincare", "beauty", "makeup", "serum", "my pham", "lam dep"],
    "local_vietnam": ["viet nam", "vietnam", "vn", "nguoi viet", "tiktok vn"],
}

_SUBJECT_HINTS = [
    "serum", "lipstick", "cream", "app", "saas", "restaurant", "cafe", "course",
    "product", "brand", "founder", "character", "drama", "phim", "my pham",
    "san pham", "ung dung", "phan mem", "nha hang", "quan cafe",
]


def build_creative_brief_contract(
    *,
    user_idea: str,
    target_market: str = "auto",
    target_platform: str = "tiktok",
    duration_hint_s: Optional[int] = None,
    reference_counts: Optional[dict[str, int]] = None,
    conversation_messages: Optional[list[dict[str, Any]]] = None,
    revision_notes: Optional[str] = None,
) -> dict[str, Any]:
    """Return a stable no-vendor-call contract for free-form user input."""
    idea = _clip_text(user_idea or "", 3000)
    conversation = _conversation_text(conversation_messages or [])
    revisions = _clip_text(revision_notes or "", 1200)
    combined = "\n".join(part for part in [idea, conversation, revisions] if part).strip()
    normalized = _normalize(combined)
    refs = _normalize_reference_counts(reference_counts or {})
    parsed_duration = _extract_duration_s(normalized)
    effective_duration = int(duration_hint_s or parsed_duration or 0) or None
    platform = _extract_platform(normalized, target_platform, duration_s=effective_duration)
    language = _detect_language(combined, normalized)
    goals = _rank_keyword_groups(normalized, _GOAL_KEYWORDS)
    styles = _rank_keyword_groups(normalized, _STYLE_KEYWORDS)
    audiences = _rank_keyword_groups(normalized, _AUDIENCE_KEYWORDS)
    subject = _extract_subject(normalized)
    missing = _missing_fields(
        normalized=normalized,
        subject=subject,
        goals=goals,
        duration_s=effective_duration,
        refs=refs,
    )
    completeness = _completeness_score(
        subject=subject,
        goals=goals,
        duration_s=effective_duration,
        refs=refs,
        missing=missing,
    )
    render_readiness = (
        "ready_for_preflight"
        if completeness >= 75
        else "needs_light_clarification"
        if completeness >= 55
        else "needs_user_input"
    )
    output_intent = _output_intent(goals)
    blocking_questions = _blocking_questions(missing, output_intent=output_intent)
    return {
        "schema_version": "cinejelly.creative_brief_contract.v1",
        "vendor_calls_performed": False,
        "paid_video_vendor_calls_allowed": False,
        "input": {
            "idea_chars": len(idea),
            "conversation_chars": len(conversation),
            "revision_chars": len(revisions),
            "language": language,
            "target_market_requested": target_market or "auto",
            "target_platform_requested": target_platform or "tiktok",
        },
        "parsed": {
            "request_intent": "create_video",
            "output_intent": output_intent,
            "subject": subject,
            "goals": goals[:3],
            "audiences": audiences[:3],
            "style_signals": styles[:4],
            "target_platform": platform["value"],
            "target_platform_source": platform["source"],
            "duration": {
                "requested_s": effective_duration,
                "source": "ui_hint" if duration_hint_s else "prompt_text" if parsed_duration else "unspecified",
                "raw_prompt_duration_s": parsed_duration,
            },
            "reference_counts": refs,
            "reference_expectation": _reference_expectation(refs, output_intent),
        },
        "quality_target": _quality_target(
            output_intent=output_intent,
            styles=styles,
            duration_s=effective_duration,
            refs=refs,
        ),
        "missing_fields": missing,
        "blocking_questions": blocking_questions,
        "readiness": {
            "status": render_readiness,
            "completeness_score": completeness,
            "can_build_preflight": completeness >= 45,
            "should_ask_before_paid_render": bool(blocking_questions),
        },
        "llm_input_plan": {
            "default_text_lane": "deepseek-ai/deepseek-v4-flash",
            "vision_lane": "qwen/qwen3-vl-30b-a3b-instruct" if refs["images"] or refs["pinned_assets"] else None,
            "pro_lane": "locked_until_explicit_approval",
            "why": "Use deterministic parsing plus Flash/Qwen first; escalate only if the approved plan is still weak.",
        },
    }


def _extract_duration_s(text: str) -> Optional[int]:
    patterns = [
        (r"\b(\d{1,2})\s*(?:s|sec|secs|second|seconds|giay)\b", 1),
        (r"\b(\d{1,2})\s*(?:m|min|mins|minute|minutes|phut)\b", 60),
        (r"\b(\d{1,2})\s*p\b", 60),
    ]
    for pattern, multiplier in patterns:
        match = re.search(pattern, text)
        if match:
            value = int(match.group(1)) * multiplier
            return max(4, min(value, 1800))
    return None


def _extract_platform(text: str, fallback: str, *, duration_s: Optional[int]) -> dict[str, str]:
    if "youtube" in text and duration_s and duration_s >= 60:
        return {"value": "youtube_long", "source": "prompt_text"}
    for platform, keywords in _PLATFORM_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return {"value": platform, "source": "prompt_text"}
    return {"value": fallback or "tiktok", "source": "ui_or_default"}


def _detect_language(raw: str, normalized: str) -> str:
    has_vietnamese_marks = any(
        char in raw
        for char in "ăâđêôơưĂÂĐÊÔƠƯáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ"
    )
    vi_tokens = {"toi", "hay", "lam", "video", "phim", "quang cao", "san pham", "viet nam"}
    en_tokens = {"make", "create", "video", "ad", "story", "product", "audience"}
    vi_hits = sum(1 for token in vi_tokens if token in normalized)
    en_hits = sum(1 for token in en_tokens if token in normalized)
    if has_vietnamese_marks or vi_hits > en_hits:
        return "vi"
    if en_hits > 0:
        return "en"
    return "unknown"


def _rank_keyword_groups(text: str, groups: dict[str, list[str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, keywords in groups.items():
        hits = [keyword for keyword in keywords if keyword in text]
        if hits:
            rows.append({"key": key, "score": len(hits), "hits": hits[:6]})
    rows.sort(key=lambda item: item["score"], reverse=True)
    return rows


def _output_intent(goals: list[dict[str, Any]]) -> str:
    if not goals:
        return "general_video"
    return str(goals[0]["key"])


def _extract_subject(text: str) -> dict[str, Any]:
    hits = [token for token in _SUBJECT_HINTS if token in text]
    quoted = re.findall(r"[\"']([^\"']{3,80})[\"']", text)
    return {
        "status": "detected" if hits or quoted else "missing",
        "hints": hits[:8],
        "quoted_candidates": quoted[:3],
        "summary": quoted[0] if quoted else hits[0] if hits else "",
    }


def _reference_expectation(refs: dict[str, int], output_intent: str) -> dict[str, Any]:
    needed_roles: list[str] = []
    if output_intent in {"sell_product", "review_proof"}:
        needed_roles.extend(["product_hero", "proof_or_demo_reference"])
    if output_intent in {"entertain", "brand_story"}:
        needed_roles.extend(["character_anchor", "location_or_style_reference"])
    if output_intent == "educate":
        needed_roles.extend(["presenter_or_topic_anchor"])
    if refs["images"] or refs["pinned_assets"]:
        status = "visual_refs_present"
    elif needed_roles:
        status = "visual_refs_recommended"
    else:
        status = "optional"
    return {
        "status": status,
        "needed_roles": needed_roles[:4],
        "has_visual_anchor": bool(refs["images"] or refs["pinned_assets"]),
        "has_motion_reference": bool(refs["videos"]),
        "has_audio_reference": bool(refs["audios"]),
    }


def _quality_target(
    *,
    output_intent: str,
    styles: list[dict[str, Any]],
    duration_s: Optional[int],
    refs: dict[str, int],
) -> dict[str, Any]:
    style_keys = {str(item["key"]) for item in styles}
    bars = ["clear first-3s hook", "single viewer promise", "model-specific prompt handoff"]
    if output_intent in {"sell_product", "review_proof"}:
        bars.extend(["product remains recognizable", "proof beat appears before CTA"])
    if output_intent in {"entertain", "brand_story"}:
        bars.extend(["character motivation stays consistent", "ending pays off the setup"])
    if "cinematic" in style_keys or (duration_s and duration_s >= 180):
        bars.append("scene continuity and handoff memory required")
    if refs["images"] or refs["pinned_assets"]:
        bars.append("reference identity/style must be preserved")
    return {
        "tier": "long_form_story" if duration_s and duration_s >= 180 else "short_social",
        "bars": bars[:8],
    }


def _missing_fields(
    *,
    normalized: str,
    subject: dict[str, Any],
    goals: list[dict[str, Any]],
    duration_s: Optional[int],
    refs: dict[str, int],
) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    if subject.get("status") == "missing":
        missing.append({
            "key": "subject",
            "severity": "blocking",
            "question": "What product, topic, character, or story outcome is the video about?",
        })
    if not goals:
        missing.append({
            "key": "goal",
            "severity": "recommended",
            "question": "Should the video sell, explain, entertain, review, or tell a brand story?",
        })
    if not duration_s:
        missing.append({
            "key": "duration",
            "severity": "recommended",
            "question": "How long should the video be: 15s, 30s, 3m, 5m, or longer?",
        })
    if (
        any(token in normalized for token in ["product", "san pham", "serum", "app", "my pham"])
        and refs["images"] + refs["pinned_assets"] == 0
    ):
        missing.append({
            "key": "product_reference",
            "severity": "recommended",
            "question": "Add a product image/reference if exact product identity matters.",
        })
    return missing[:5]


def _blocking_questions(missing: list[dict[str, str]], *, output_intent: str) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for item in missing:
        if item.get("severity") != "blocking":
            continue
        questions.append({
            "id": f"brief_{item['key']}",
            "question": item["question"],
            "why": "The agent needs this to avoid building a generic video.",
            "suggested_replies": _suggested_replies_for(item["key"], output_intent),
        })
    return questions[:3]


def _suggested_replies_for(key: str, output_intent: str) -> list[str]:
    if key == "subject" and output_intent == "entertain":
        return [
            "Story: [character]. Conflict: [problem]. Ending: [twist or transformation].",
            "Main character is [who], location is [where], emotion is [tone].",
        ]
    if key == "subject":
        return [
            "Product/topic: [name]. Audience: [who]. Main payoff: [visible result].",
            "Brand: [name]. Offer: [what]. Proof: [why viewers believe it].",
        ]
    return ["Add the missing detail in one sentence."]


def _completeness_score(
    *,
    subject: dict[str, Any],
    goals: list[dict[str, Any]],
    duration_s: Optional[int],
    refs: dict[str, int],
    missing: list[dict[str, str]],
) -> int:
    score = 35
    if subject.get("status") == "detected":
        score += 25
    if goals:
        score += 18
    if duration_s:
        score += 10
    if refs["images"] or refs["videos"] or refs["pinned_assets"]:
        score += 8
    score -= 10 * sum(1 for item in missing if item.get("severity") == "blocking")
    score -= 4 * sum(1 for item in missing if item.get("severity") == "recommended")
    return max(0, min(100, score))


def _normalize_reference_counts(counts: dict[str, int]) -> dict[str, int]:
    def n(*keys: str) -> int:
        for key in keys:
            if key in counts:
                try:
                    return max(0, int(counts.get(key) or 0))
                except (TypeError, ValueError):
                    return 0
        return 0

    return {
        "images": n("images", "image"),
        "videos": n("videos", "video"),
        "audios": n("audios", "audio"),
        "pinned_assets": n("pinned_assets", "pinned"),
    }


def _conversation_text(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in messages[-8:]:
        if str(item.get("role") or "").lower() != "user":
            continue
        text = _clip_text(str(item.get("text") or item.get("content") or ""), 500)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    ascii_text = ascii_text.replace("đ", "d").replace("Đ", "D")
    return " ".join(ascii_text.lower().split())


def _clip_text(value: str, limit: int) -> str:
    value = (value or "").strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


__all__ = ["build_creative_brief_contract"]
