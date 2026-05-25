"""
MODEL SPECS — Single source of truth cho AtlasCloud video models.

═══════════════════════════════════════════════════════════════════════════
REFACTOR 2026-05-25 (V6) — 7-MODEL CORE
═══════════════════════════════════════════════════════════════════════════
Sau khi audit chất lượng + cost + market signal, project ổn định trên:

  CORE — Seedance 2.0 family (6 variants, $0.076-0.096/s):
    seedance_2_0_ref         — reference-to-video, multi-shot inline, 9 refs
    seedance_2_0_i2v         — image-to-video, single frame
    seedance_2_0_t2v         — text-to-video
    seedance_2_0_fast_ref    — 20% rẻ hơn 2.0 chuẩn, same capability
    seedance_2_0_fast_i2v    — fast image-to-video
    seedance_2_0_fast_t2v    — fast text-to-video

  FALLBACK — Alibaba Wan 2.7 i2v (1 variant, $0.10/s, discrete duration [5,10]):
    wan_2_7_i2v              — driven audio (lip-sync TTS), single image input

KHÔNG hỗ trợ nữa (đã xoá khỏi spec): Vidu Q3 / Vidu Q3-Mix / Seedance 1.5 Pro
(* variants) / Wan 2.7 t2v. Lý do: Seedance 2.0 thống trị Elo 2026, chi phí
ngang Vidu nhưng chất lượng vượt trội (physics +31.7, multi-ref 9 + 3 video
+ 3 audio). Wan 2.7 i2v giữ vì là model DUY NHẤT có driven-audio lip-sync
tiếng Việt khớp môi — không thể thay thế bằng Seedance.

═══════════════════════════════════════════════════════════════════════════
SEEDANCE 2.0 — QUAD-MODAL REFERENCE BINDING (mới Sprint6)
═══════════════════════════════════════════════════════════════════════════
Seedance 2.0 (cả 6 variants) nhận đồng thời:
  - reference_images[]   0-9 ảnh tham chiếu (character / product / style / env)
  - reference_videos[]   0-3 video tham chiếu (camera trajectory / motion / pacing)
  - reference_audios[]   0-3 audio tham chiếu (beat / lip-sync source / SFX)
  - prompt với @image_N / @video_N tag inline

Quad-modal là sức mạnh CỐT LÕI của Seedance 2.0 — KHÔNG model nào khác
trên thị trường có. Pipeline phải tận dụng tối đa.
"""

from typing import Any, Optional


# ============================================================
# VIDEO MODEL SPECS — 7 models (6 Seedance 2.0 + 1 Wan 2.7 i2v)
# ============================================================

VIDEO_MODEL_SPECS: dict[str, dict[str, Any]] = {

    # ══════════════════════════════════════════════════════════
    # SEEDANCE 2.0 CORE PATH — multi-shot inline + quad-modal refs
    # ══════════════════════════════════════════════════════════
    "seedance_2_0_ref": {
        "endpoint": "bytedance/seedance-2.0/reference-to-video",
        "name_vn": "Seedance 2.0 Reference-to-Video",
        "variant": "reference-to-video",
        "vendor": "bytedance",
        "cost_per_second_usd": 0.096,
        "duration": {"min": 4, "max": 15, "default": 5, "auto_sentinel": -1},
        "resolution": {
            "options": ["480p", "720p", "720p-SR", "1080p", "1080p-SR", "1440p-SR"],
            "default": "720p",
        },
        "aspect_ratio": {
            "field_name": "ratio",
            "options": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"],
            "default": "adaptive",
        },
        "images_field": "reference_images",  # plural list (0-9)
        "max_references": 9,
        "min_references": 1,
        "required": ["model", "prompt"],
        "extra_fields": {
            "negative_prompt": {"type": "string", "default": "", "max_length": 1000},
            "reference_videos": {"type": "array", "default": [], "max_items": 3},
            "reference_audios": {"type": "array", "default": [], "max_items": 3},
            "generate_audio": {"type": "bool", "default": True},
            "watermark": {"type": "bool", "default": False},
            "return_last_frame": {"type": "bool", "default": False},
        },
        "audio_capability": "native",
        "supports_multi_shot": True,        # @image_N / @video_N + [Shot N] notation
        "supports_quad_modal": True,        # img + video + audio refs in 1 call
        "available": True,
    },
    "seedance_2_0_i2v": {
        "endpoint": "bytedance/seedance-2.0/image-to-video",
        "name_vn": "Seedance 2.0 Image-to-Video",
        "variant": "image-to-video",
        "vendor": "bytedance",
        "cost_per_second_usd": 0.096,
        "duration": {"min": 4, "max": 15, "default": 5, "auto_sentinel": -1},
        "resolution": {
            "options": ["480p", "720p", "720p-SR", "1080p", "1080p-SR", "1440p-SR"],
            "default": "720p",
        },
        "aspect_ratio": {
            "field_name": "ratio",
            "options": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"],
            "default": "adaptive",
        },
        "images_field": "image",            # singular
        "max_references": 1,
        "min_references": 1,
        "required": ["model", "image"],
        "extra_fields": {
            "negative_prompt": {"type": "string", "default": "", "max_length": 1000},
            "prompt": {"type": "string", "default": ""},
            "last_image": {"type": "string", "default": None},
            "reference_audios": {"type": "array", "default": [], "max_items": 3},
            "generate_audio": {"type": "bool", "default": True},
            "watermark": {"type": "bool", "default": False},
            "return_last_frame": {"type": "bool", "default": False},
        },
        "audio_capability": "native",
        "supports_multi_shot": False,       # i2v = single shot
        "supports_quad_modal": False,       # i2v: image + audio only (no video refs)
        "available": True,
    },
    "seedance_2_0_t2v": {
        "endpoint": "bytedance/seedance-2.0/text-to-video",
        "name_vn": "Seedance 2.0 Text-to-Video",
        "variant": "text-to-video",
        "vendor": "bytedance",
        "cost_per_second_usd": 0.096,
        "duration": {"min": 4, "max": 15, "default": 5, "auto_sentinel": -1},
        "resolution": {
            "options": ["480p", "720p", "720p-SR", "1080p", "1080p-SR", "1440p-SR"],
            "default": "720p",
        },
        "aspect_ratio": {
            "field_name": "ratio",
            "options": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"],
            "default": "adaptive",
        },
        "images_field": None,
        "max_references": 0,
        "required": ["model", "prompt"],
        "extra_fields": {
            "negative_prompt": {"type": "string", "default": "", "max_length": 1000},
            "reference_audios": {"type": "array", "default": [], "max_items": 3},
            "generate_audio": {"type": "bool", "default": True},
            "watermark": {"type": "bool", "default": False},
            "return_last_frame": {"type": "bool", "default": False},
        },
        "audio_capability": "native",
        "supports_multi_shot": True,        # t2v supports [Shot N] notation
        "supports_quad_modal": False,       # t2v: audio refs only (no image/video refs)
        "available": True,
    },

    # ── Seedance 2.0 FAST tier — same capability, 20% rẻ ─────────
    "seedance_2_0_fast_ref": {
        "endpoint": "bytedance/seedance-2.0-fast/reference-to-video",
        "name_vn": "Seedance 2.0 Fast Reference-to-Video",
        "variant": "reference-to-video",
        "vendor": "bytedance",
        "cost_per_second_usd": 0.076,
        "duration": {"min": 4, "max": 15, "default": 5, "auto_sentinel": -1},
        "resolution": {
            "options": ["480p", "720p", "720p-SR", "1080p-SR", "1440p-SR"],
            "default": "720p",
        },
        "aspect_ratio": {
            "field_name": "ratio",
            "options": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"],
            "default": "adaptive",
        },
        "images_field": "reference_images",
        "max_references": 9,
        "min_references": 1,
        "required": ["model", "prompt"],
        "extra_fields": {
            "negative_prompt": {"type": "string", "default": "", "max_length": 1000},
            "reference_videos": {"type": "array", "default": [], "max_items": 3},
            "reference_audios": {"type": "array", "default": [], "max_items": 3},
            "generate_audio": {"type": "bool", "default": True},
            "watermark": {"type": "bool", "default": False},
            "return_last_frame": {"type": "bool", "default": False},
        },
        "audio_capability": "native",
        "supports_multi_shot": True,
        "supports_quad_modal": True,
        "available": True,
    },
    "seedance_2_0_fast_i2v": {
        "endpoint": "bytedance/seedance-2.0-fast/image-to-video",
        "name_vn": "Seedance 2.0 Fast Image-to-Video",
        "variant": "image-to-video",
        "vendor": "bytedance",
        "cost_per_second_usd": 0.076,
        "duration": {"min": 4, "max": 15, "default": 5, "auto_sentinel": -1},
        "resolution": {
            "options": ["480p", "720p", "720p-SR", "1080p-SR", "1440p-SR"],
            "default": "720p",
        },
        "aspect_ratio": {
            "field_name": "ratio",
            "options": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"],
            "default": "adaptive",
        },
        "images_field": "image",
        "max_references": 1,
        "min_references": 1,
        "required": ["model", "image"],
        "extra_fields": {
            "negative_prompt": {"type": "string", "default": "", "max_length": 1000},
            "prompt": {"type": "string", "default": ""},
            "last_image": {"type": "string", "default": None},
            "reference_audios": {"type": "array", "default": [], "max_items": 3},
            "generate_audio": {"type": "bool", "default": True},
            "watermark": {"type": "bool", "default": False},
            "return_last_frame": {"type": "bool", "default": False},
        },
        "audio_capability": "native",
        "supports_multi_shot": False,
        "supports_quad_modal": False,
        "available": True,
    },
    "seedance_2_0_fast_t2v": {
        "endpoint": "bytedance/seedance-2.0-fast/text-to-video",
        "name_vn": "Seedance 2.0 Fast Text-to-Video",
        "variant": "text-to-video",
        "vendor": "bytedance",
        "cost_per_second_usd": 0.076,
        "duration": {"min": 4, "max": 15, "default": 5, "auto_sentinel": -1},
        "resolution": {
            "options": ["480p", "720p", "720p-SR", "1080p-SR", "1440p-SR"],
            "default": "720p",
        },
        "aspect_ratio": {
            "field_name": "ratio",
            "options": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"],
            "default": "adaptive",
        },
        "images_field": None,
        "max_references": 0,
        "required": ["model", "prompt"],
        "extra_fields": {
            "negative_prompt": {"type": "string", "default": "", "max_length": 1000},
            "reference_audios": {"type": "array", "default": [], "max_items": 3},
            "generate_audio": {"type": "bool", "default": True},
            "watermark": {"type": "bool", "default": False},
            "return_last_frame": {"type": "bool", "default": False},
        },
        "audio_capability": "native",
        "supports_multi_shot": True,
        "supports_quad_modal": False,
        "available": True,
    },

    # ══════════════════════════════════════════════════════════
    # FALLBACK PATH — Wan 2.7 i2v (driven-audio lip-sync VN)
    # ══════════════════════════════════════════════════════════
    # Lý do giữ: Wan 2.7 là model DUY NHẤT trên AtlasCloud có driven-audio
    # field — đưa file TTS tiếng Việt vào, model tự sync môi nhân vật. Seedance
    # KHÔNG có khả năng này. Dùng khi user cần talking-head VN.
    "wan_2_7_i2v": {
        "endpoint": "alibaba/wan-2.7/image-to-video",
        "submit_path": "/model/generateVideo",
        "name_vn": "Wan 2.7 Image-to-Video (lip-sync VN)",
        "variant": "image-to-video",
        "vendor": "alibaba",
        "cost_per_second_usd": 0.10,
        "duration": {
            "min": 5, "max": 10, "default": 5,
            "discrete_values": [5, 10],   # Wan ONLY accept 5 hoặc 10
        },
        "resolution": {"options": ["480p", "720p", "1080p"], "default": "720p"},
        "aspect_ratio": None,             # i2v đọc từ image
        "images_field": "image",
        "max_references": 1,
        "min_references": 1,
        "required": ["model", "image"],
        "extra_fields": {
            "prompt": {"type": "string", "default": ""},
            "negative_prompt": {"type": "string", "default": "", "max_length": 1000},
            "last_image": {"type": "string", "default": None},
            "video": {"type": "string", "default": None},
            "audio": {"type": "string", "default": None, "desc": "Driven audio URL (lip-sync)"},
            "prompt_extend": {"type": "bool", "default": True},
            "seed": {"type": "int", "default": -1, "min": -1, "max": 2147483647},
        },
        "audio_capability": "driven",     # ★ unique on this model
        "supports_multi_shot": False,
        "supports_quad_modal": False,
        "available": True,
    },
}


# Cost hard cap per video (USD) — fail-safe để KHÔNG gen 1 video > $5
MAX_COST_PER_VIDEO_USD = 5.0


def get_spec(model_key: str) -> dict:
    """Get spec by key. Raise nếu unknown/unavailable."""
    if model_key not in VIDEO_MODEL_SPECS:
        raise ValueError(
            f"Model '{model_key}' không tồn tại. Available: {list(VIDEO_MODEL_SPECS.keys())}"
        )
    spec = VIDEO_MODEL_SPECS[model_key]
    if not spec.get("available", True):
        raise ValueError(f"Model '{model_key}' KHÔNG available.")
    return spec


def is_seedance_2_0(model_key: str) -> bool:
    """SEEDANCE 2.0 CORE PATH check — dùng để gate quad-modal / multi-shot logic.

    True cho cả 6 variants (chuẩn + fast × ref/i2v/t2v).
    """
    return model_key.startswith("seedance_2_0")


def supports_quad_modal(model_key: str) -> bool:
    """True nếu model nhận đồng thời image + video + audio refs.

    Hiện tại CHỈ seedance_2_0_ref + seedance_2_0_fast_ref.
    """
    spec = VIDEO_MODEL_SPECS.get(model_key, {})
    return bool(spec.get("supports_quad_modal", False))


def build_payload(
    model_key: str,
    prompt: str,
    *,
    images: Optional[list[str]] = None,
    image: Optional[str] = None,
    reference_videos: Optional[list[str]] = None,    # ★ Seedance 2.0 quad-modal
    reference_audios: Optional[list[str]] = None,    # ★ Seedance 2.0 quad-modal
    duration_s: Optional[int] = None,
    resolution: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    seed: Optional[int] = None,
    generate_audio: Optional[bool] = None,
    audio_url: Optional[str] = None,                 # Wan 2.7 driven audio (single)
    last_image: Optional[str] = None,
    prompt_extend: Optional[bool] = None,
    watermark: Optional[bool] = None,
    return_last_frame: Optional[bool] = None,
) -> dict:
    """Build AtlasCloud payload đúng per-model spec.

    Tự động:
      - Map field names (images vs image vs reference_images, ratio vs aspect_ratio)
      - Validate value range (duration/resolution/aspect)
      - Snap Wan 2.7 duration sang discrete [5, 10]
      - Cap negative_prompt length
      - Inject quad-modal arrays cho Seedance 2.0 (reference_videos / reference_audios)
      - Drop field model không support
    """
    spec = get_spec(model_key)

    payload: dict = {"model": spec["endpoint"]}

    if prompt:
        payload["prompt"] = prompt

    # ─── Duration validate + Wan discrete snap ──────────────────
    if duration_s is not None:
        d = spec["duration"]
        if d.get("auto_sentinel") is not None and duration_s == d["auto_sentinel"]:
            payload["duration"] = duration_s  # -1 = auto
        elif duration_s < d["min"] or duration_s > d["max"]:
            raise ValueError(
                f"Duration {duration_s}s ngoài range {d['min']}-{d['max']}s cho {model_key}"
            )
        else:
            discrete = d.get("discrete_values")
            if isinstance(discrete, list) and discrete and duration_s not in discrete:
                snapped = min(discrete, key=lambda v: abs(v - duration_s))
                import logging as _log
                _log.getLogger(__name__).warning(
                    f"[model_specs] {model_key} duration {duration_s}s → "
                    f"{snapped}s (discrete only)"
                )
                duration_s = snapped
            payload["duration"] = duration_s

    # ─── Resolution validate ─────────────────────────────────────
    if resolution is not None:
        if resolution not in spec["resolution"]["options"]:
            raise ValueError(
                f"Resolution '{resolution}' không support cho {model_key}. "
                f"Options: {spec['resolution']['options']}"
            )
        payload["resolution"] = resolution

    # ─── Aspect ratio (field name khác giữa các model) ──────────
    if aspect_ratio is not None and spec.get("aspect_ratio"):
        ar_spec = spec["aspect_ratio"]
        if aspect_ratio not in ar_spec["options"]:
            raise ValueError(
                f"Aspect ratio '{aspect_ratio}' không support. Options: {ar_spec['options']}"
            )
        payload[ar_spec["field_name"]] = aspect_ratio

    # ─── Images field — singular `image` vs plural `reference_images` ──
    img_field = spec.get("images_field")
    if img_field == "image":
        # Wan 2.7 i2v / Seedance 2.0 i2v: single string
        single = image or (images[0] if images else None)
        if not single and "image" in spec["required"]:
            raise ValueError(f"{model_key} bắt buộc field 'image' (first-frame URL)")
        if single:
            payload["image"] = single
    elif img_field == "reference_images":
        # Seedance 2.0 ref: list — min/max enforced
        max_n = spec.get("max_references", 9)
        min_n = spec.get("min_references", 0)
        n_images = len(images) if images else 0
        if min_n > 0 and n_images < min_n:
            raise ValueError(
                f"{model_key} cần tối thiểu {min_n} reference_images (nhận {n_images})"
            )
        if n_images > max_n:
            raise ValueError(f"{model_key} max {max_n} reference_images, nhận {n_images}")
        if images:
            payload["reference_images"] = images[:max_n]

    # ─── Per-model extra fields ─────────────────────────────────
    extras = spec.get("extra_fields", {})

    # SEEDANCE 2.0 CORE PATH — quad-modal arrays
    if reference_videos and "reference_videos" in extras:
        max_v = extras["reference_videos"].get("max_items", 3)
        payload["reference_videos"] = list(reference_videos)[:max_v]
    if reference_audios and "reference_audios" in extras:
        max_a = extras["reference_audios"].get("max_items", 3)
        payload["reference_audios"] = list(reference_audios)[:max_a]

    if negative_prompt is not None and "negative_prompt" in extras:
        neg_max = extras["negative_prompt"].get("max_length", 1000)
        if len(negative_prompt) > neg_max:
            import logging as _log
            _log.getLogger(__name__).warning(
                f"[model_specs] {model_key} negative_prompt {len(negative_prompt)} "
                f"→ truncated to {neg_max}"
            )
            negative_prompt = negative_prompt[:neg_max]
        payload["negative_prompt"] = negative_prompt
    if seed is not None and "seed" in extras:
        payload["seed"] = seed
    if generate_audio is not None and "generate_audio" in extras:
        payload["generate_audio"] = generate_audio
    if audio_url is not None and "audio" in extras:
        payload["audio"] = audio_url    # Wan 2.7 driven audio
    if last_image is not None and "last_image" in extras:
        payload["last_image"] = last_image
    if prompt_extend is not None and "prompt_extend" in extras:
        payload["prompt_extend"] = prompt_extend
    if watermark is not None and "watermark" in extras:
        payload["watermark"] = watermark
    if return_last_frame is not None and "return_last_frame" in extras:
        payload["return_last_frame"] = return_last_frame

    # Final validate required
    for req in spec["required"]:
        if req not in payload:
            raise ValueError(f"{model_key} bắt buộc field '{req}' nhưng chưa có trong payload")

    return payload


def estimate_cost(model_key: str, duration_s: int) -> float:
    """Cost = rate × actual billed duration. Snap Wan discrete trước khi tính."""
    spec = get_spec(model_key)
    dur_spec = spec["duration"]
    actual_duration = max(duration_s, dur_spec["min"])
    discrete = dur_spec.get("discrete_values")
    if discrete:
        higher = [d for d in discrete if d >= actual_duration]
        actual_duration = min(higher) if higher else max(discrete)
    return spec["cost_per_second_usd"] * actual_duration


def list_models_for_ui() -> list[dict]:
    """Liệt cho frontend: id, name, vendor, variant, cost, capabilities."""
    out = []
    for key, spec in VIDEO_MODEL_SPECS.items():
        if not spec.get("available", True):
            continue
        out.append({
            "key": key,
            "endpoint": spec["endpoint"],
            "name_vn": spec["name_vn"],
            "vendor": spec["vendor"],
            "variant": spec["variant"],
            "cost_per_second_usd": spec["cost_per_second_usd"],
            "duration": spec["duration"],
            "resolution_options": spec["resolution"]["options"],
            "aspect_ratio_options": (
                spec.get("aspect_ratio", {}).get("options")
                if spec.get("aspect_ratio") else None
            ),
            "max_references": spec.get("max_references", 0),
            "audio_capability": spec["audio_capability"],
            "supports_quad_modal": spec.get("supports_quad_modal", False),
            "supports_multi_shot": spec.get("supports_multi_shot", False),
            "extra_fields": list(spec.get("extra_fields", {}).keys()),
        })
    return out
