"""
MODEL ADAPTER — Convert generator output thành AtlasCloud API payload.

⚠️ MODEL ID format CHUẨN AtlasCloud (verify từ doc):
    https://www.atlascloud.ai/docs/models/video
    https://www.atlascloud.ai/models/list

Format: <vendor>/<model>/<type>
    vidu/q3/reference-to-video                 — $0.042/s (1-4 refs)
    vidu/q3-mix/reference-to-video             — $0.106/s (premium variant)
    alibaba/wan-2.7/image-to-video             — $0.10/s
    alibaba/wan-2.7/text-to-video              — $0.10/s
    alibaba/wan-2.7/reference-to-video         — $0.10/s
    bytedance/seedance-2.0/reference-to-video  — $0.096/s (1-9 refs)
    bytedance/seedance-2.0/image-to-video      — $0.096/s
    bytedance/seedance-2.0/text-to-video       — $0.096/s

⚠️ Seedance 1.5 Pro KHÔNG xuất hiện trong AtlasCloud model list hiện tại.
    Có thể đã deprecate hoặc tên khác. Set available=False để UI cảnh báo.

CHẠY `scripts/discover_atlascloud.py` SAU KHI nạp ATLASCLOUD_API_KEY để verify
model IDs thực sự available trên account của anh.
"""

from typing import Optional


# Mapping internal model alias → AtlasCloud model ID chuẩn slash-format
# AUDIT-C1+C2 fix: sync với VIDEO_MODEL_SPECS ground truth.
# - REMOVED: wan_2_2_turbo (KHÔNG có endpoint Atlas — em thêm nhầm trước đó)
# - FIXED:   seedance_1_5_pro endpoint thật là "seedance-v1.5-pro" (có "v") + available=True
# - ADDED:   seedance_2_0_fast (cost $0.076/s middle tier)
MODEL_REGISTRY: dict[str, dict] = {
    "vidu_q3": {
        "endpoint": "vidu/q3/reference-to-video",
        "max_duration_s": 16,
        "max_references": 4,
        "supports_audio_driven": False,
        "supports_native_audio": True,
        "cost_per_second_usd": 0.042,
        "name_vn": "Vidu Q3 (rẻ, multi-entity consistency)",
        "available": True,
    },
    "vidu_q3_mix": {
        "endpoint": "vidu/q3-mix/reference-to-video",
        "max_duration_s": 16,
        "max_references": 4,
        "supports_audio_driven": False,
        "supports_native_audio": True,
        "cost_per_second_usd": 0.106,
        "name_vn": "Vidu Q3-Mix (premium, 1080p)",
        "available": True,
    },
    "wan_2_7": {
        "endpoint": "alibaba/wan-2.7/image-to-video",
        # Sprint3 B9 fix: Wan 2.7 ONLY accepts discrete [5, 10] (per AtlasCloud
        # 2026-05 docs verified in model_specs.py:106). build_payload snaps to
        # nearest discrete. Listed as 10 here for max-bound validation only.
        "max_duration_s": 10,
        "max_references": 1,    # i2v singular image
        "supports_audio_driven": True,
        "supports_native_audio": False,  # ✅ AUDIT-H1 fix: add missing key
        "cost_per_second_usd": 0.10,
        "name_vn": "Wan 2.7 (audio-driven khớp môi VN)",
        "available": True,
    },
    "seedance_1_5_pro": {
        # ✅ AUDIT-C2 fix: endpoint thật là "v1.5-pro" (có "v"), i2v variant (KHÔNG có ref variant)
        "endpoint": "bytedance/seedance-v1.5-pro/image-to-video",
        "max_duration_s": 12,  # spec 4-12s
        "max_references": 1,   # i2v singular
        "supports_audio_driven": False,
        "supports_native_audio": True,
        "cost_per_second_usd": 0.047,
        "name_vn": "Seedance 1.5 Pro (i2v, budget mid)",
        "available": True,  # ✅ AUDIT-C2 fix: thật là available trên Atlas
    },
    "seedance_2_0": {
        "endpoint": "bytedance/seedance-2.0/reference-to-video",
        "max_duration_s": 15,
        "max_references": 9,
        "supports_audio_driven": False,
        "supports_native_audio": True,
        "supports_multi_shot_native": True,
        "cost_per_second_usd": 0.096,
        "name_vn": "Seedance 2.0 (multi-shot cao cấp)",
        "available": True,
    },
    "seedance_2_0_fast": {
        # ✅ AUDIT-C1 fix: NEW — middle tier giữa Seedance 1.5 Pro và 2.0
        "endpoint": "bytedance/seedance-2.0-fast/reference-to-video",
        "max_duration_s": 15,
        "max_references": 9,
        "supports_audio_driven": False,
        "supports_native_audio": True,
        "supports_multi_shot_native": True,
        "cost_per_second_usd": 0.076,
        "name_vn": "Seedance 2.0 Fast (middle tier, rẻ hơn 2.0 20%)",
        "available": True,
    },
}

# Trần cost cứng — fail-safe để KHÔNG gen 1 video > $5
# Override qua env MAX_COST_PER_VIDEO_USD nếu cần
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
        raise ValueError(
            f"Model '{model_id}' KHÔNG available trên AtlasCloud hiện tại. "
            f"Note: {info.get('note', '')}"
        )
    return info


def adapt_for_atlascloud(
    prompt: str,
    model_id: str,
    duration_s: int,
    aspect_ratio: str,
    references: list[str],
    audio_url: Optional[str] = None,
) -> dict:
    """Convert generation thành AtlasCloud API payload chuẩn."""
    model_info = get_model_info(model_id)

    if duration_s > model_info["max_duration_s"]:
        raise ValueError(
            f"Duration {duration_s}s > max {model_info['max_duration_s']}s "
            f"của {model_id}. Dùng duration_extender chia nhỏ trước."
        )

    refs = references[: model_info["max_references"]]

    if audio_url:
        if model_info.get("supports_silent_only"):
            raise ValueError(f"{model_id} silent-only. Bỏ audio_url hoặc đổi model.")
        if not model_info.get("supports_audio_driven") and not model_info.get("supports_native_audio"):
            audio_url = None  # Audio sẽ overlay post, không inject

    payload: dict = {
        "model": model_info["endpoint"],
        "prompt": prompt,
        "duration": duration_s,
        "aspect_ratio": aspect_ratio,
        "reference_images": refs,
    }
    if audio_url and model_info.get("supports_audio_driven"):
        payload["audio_driven"] = True
        payload["audio_url"] = audio_url

    return payload


def estimate_cost(model_id: str, duration_s: int, num_generations: int = 1) -> float:
    """Estimate USD cho N generations × duration_s."""
    model_info = get_model_info(model_id)
    return model_info["cost_per_second_usd"] * duration_s * num_generations


def estimate_total_job_cost(
    model_id: str,
    duration_s: int,
    audio_mode: str,
) -> dict:
    """Tổng cost dự kiến 1 job UGC = video + Claude + audio.

    Dùng để pre-flight check trước khi accept job.
    """
    video_cost = estimate_cost(model_id, duration_s)

    # Claude Sonnet 4.6 thực tế ~3-5k input + 1k output, cached 90%
    # ≈ (4000 × $3 + 1000 × $15) / 1M × 0.5 (cached saving avg)
    claude_cost_est = 0.024  # $0.024 / call (analyzer + generator cached)

    # Audio
    audio_cost_est = {
        "silent_native": 0.0,  # KHÔNG TTS
        "dialogue_vo": 0.01,    # GenMax ~50 credit ≈ $0.01
        "asmr_macro": 0.15,     # ElevenLabs ~5 SFX × $0.03
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
