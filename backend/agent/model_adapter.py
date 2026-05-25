"""
MODEL ADAPTER — Convert generator output thành AtlasCloud API payload.

V6 — 3 user-facing models only. Detailed per-variant specs live in
`model_specs.VIDEO_MODEL_SPECS` (single source of truth). This registry is a
flat alias map kept for backward-compat with older callers that referenced
`MODEL_REGISTRY[user_model]["endpoint"]` directly.

═══════════════════════════════════════════════════════════════════════════
AtlasCloud endpoint format: <vendor>/<model>/<type>
  bytedance/seedance-2.0/reference-to-video       — $0.096/s, 9 refs
  bytedance/seedance-2.0/image-to-video           — $0.096/s
  bytedance/seedance-2.0/text-to-video            — $0.096/s
  bytedance/seedance-2.0-fast/reference-to-video  — $0.076/s
  bytedance/seedance-2.0-fast/image-to-video      — $0.076/s
  bytedance/seedance-2.0-fast/text-to-video       — $0.076/s
  alibaba/wan-2.7/image-to-video                  — $0.10/s, driven lip-sync
═══════════════════════════════════════════════════════════════════════════
"""

from typing import Optional


# Flat alias registry — for callers that need user_model → ref endpoint summary.
# Use model_specs.VIDEO_MODEL_SPECS for the authoritative per-variant fields.
MODEL_REGISTRY: dict[str, dict] = {
    "seedance_2_0": {
        "endpoint": "bytedance/seedance-2.0/reference-to-video",
        "max_duration_s": 15,
        "max_references": 9,
        "supports_audio_driven": False,
        "supports_native_audio": True,
        "supports_multi_shot_native": True,
        "supports_quad_modal": True,            # img + video + audio refs
        "cost_per_second_usd": 0.096,
        "name_vn": "Seedance 2.0 (multi-shot, quad-modal premium)",
        "available": True,
    },
    "seedance_2_0_fast": {
        "endpoint": "bytedance/seedance-2.0-fast/reference-to-video",
        "max_duration_s": 15,
        "max_references": 9,
        "supports_audio_driven": False,
        "supports_native_audio": True,
        "supports_multi_shot_native": True,
        "supports_quad_modal": True,
        "cost_per_second_usd": 0.076,
        "name_vn": "Seedance 2.0 Fast (mid tier, rẻ hơn 2.0 20%)",
        "available": True,
    },
    "wan_2_7": {
        "endpoint": "alibaba/wan-2.7/image-to-video",
        "max_duration_s": 10,                   # discrete [5, 10] enforced upstream
        "max_references": 1,
        "supports_audio_driven": True,
        "supports_native_audio": False,
        "supports_multi_shot_native": False,
        "supports_quad_modal": False,
        "cost_per_second_usd": 0.10,
        "name_vn": "Wan 2.7 (driven-audio lip-sync VN, fallback)",
        "available": True,
    },
}


MAX_COST_PER_VIDEO_USD = 5.0


def get_model_info(model_id: str) -> dict:
    """Get model metadata. Raise nếu model unknown HOẶC marked unavailable."""
    if model_id not in MODEL_REGISTRY:
        raise ValueError(
            f"Model '{model_id}' không tồn tại. "
            f"Available: {[k for k, v in MODEL_REGISTRY.items() if v.get('available')]}"
        )
    info = MODEL_REGISTRY[model_id]
    if not info.get("available", True):
        raise ValueError(f"Model '{model_id}' KHÔNG available trên AtlasCloud.")
    return info


def adapt_for_atlascloud(
    prompt: str,
    model_id: str,
    duration_s: int,
    aspect_ratio: str,
    references: list[str],
    audio_url: Optional[str] = None,
) -> dict:
    """Convert generation thành AtlasCloud API payload chuẩn (legacy path).

    Modern callers should use `model_specs.build_payload()` directly for full
    quad-modal support. This helper is kept for backward-compat with older
    routes that pass references via a single list.
    """
    info = get_model_info(model_id)

    if duration_s > info["max_duration_s"]:
        raise ValueError(
            f"Duration {duration_s}s > max {info['max_duration_s']}s của {model_id}."
        )

    refs = references[: info["max_references"]]

    if audio_url and not info.get("supports_audio_driven"):
        audio_url = None  # silent drop — model ignores audio_url

    payload: dict = {
        "model": info["endpoint"],
        "prompt": prompt,
        "duration": duration_s,
        "aspect_ratio": aspect_ratio,
        "reference_images": refs,
    }
    if audio_url and info.get("supports_audio_driven"):
        payload["audio_driven"] = True
        payload["audio_url"] = audio_url

    return payload


def estimate_cost(model_id: str, duration_s: int, num_generations: int = 1) -> float:
    """Estimate USD cho N generations × duration_s."""
    info = get_model_info(model_id)
    return info["cost_per_second_usd"] * duration_s * num_generations


def estimate_total_job_cost(
    model_id: str,
    duration_s: int,
    audio_mode: str,
) -> dict:
    """Tổng cost dự kiến 1 job UGC = video + Claude + audio."""
    video_cost = estimate_cost(model_id, duration_s)
    claude_cost_est = 0.024
    audio_cost_est = {
        "silent_native": 0.0,
        "dialogue_vo": 0.01,
        "asmr_macro": 0.15,
    }.get(audio_mode, 0.0)

    total = video_cost + claude_cost_est + audio_cost_est
    return {
        "video_usd": round(video_cost, 4),
        "claude_usd": claude_cost_est,
        "audio_usd": audio_cost_est,
        "total_usd": round(total, 4),
        "total_vnd": round(total * 24500),
        "exceeds_budget": total > MAX_COST_PER_VIDEO_USD,
    }
