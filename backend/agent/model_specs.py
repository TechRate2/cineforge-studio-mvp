"""
MODEL SPECS — Single source of truth cho TẤT CẢ AtlasCloud video models.

Verified ngày 2026-05-20 từ doc CHÍNH THỨC AtlasCloud
(scrape qua Playwright từ /vi/models/list/<vendor>/<model>/<variant>).

Mỗi spec định nghĩa:
    - endpoint: model ID gửi trong field `model`
    - payload_fields: tên field thật trong body + type + default + options/range
    - required: list field bắt buộc
    - audio_capability: native | driven | none
    - cost: USD per second

CRITICAL: AtlasCloud per-model có field names KHÁC NHAU:
    - Vidu Q3        → `images` (list), `aspect_ratio`
    - Wan 2.7        → `image` (string), `ratio` (NOT aspect_ratio)
    - Seedance 2.0   → `reference_images`/`image`, `ratio` (NOT aspect_ratio)

KHÔNG đoán — chỉ dùng spec đã verify ở đây.
"""

from typing import Any, Optional


# ============================================================
# MODEL SPECS — Verified từ doc atlascloud.ai/vi/models/list/...
# ============================================================

VIDEO_MODEL_SPECS: dict[str, dict[str, Any]] = {
    # ============== VIDU Q3 / Q3-MIX (reference-to-video) ==============
    "vidu_q3_ref": {
        "endpoint": "vidu/q3/reference-to-video",
        "name_vn": "Vidu Q3 Reference-to-Video",
        "variant": "reference-to-video",
        "vendor": "vidu",
        "cost_per_second_usd": 0.042,
        "duration": {"min": 3, "max": 16, "default": 5},
        "resolution": {"options": ["540p", "720p", "1080p"], "default": "720p"},
        "aspect_ratio": {
            "field_name": "aspect_ratio",  # ⚠️ vidu dùng aspect_ratio
            "options": ["16:9", "9:16", "3:4", "4:3", "1:1"],
            "default": "16:9",
        },
        "images_field": "images",  # ⚠️ plural "images"
        "max_references": 4,
        "min_references": 1,
        "required": ["model", "prompt", "images"],
        "extra_fields": {
            "negative_prompt": {"type": "string", "default": ""},  # V3.1 anti-artifact
            "generate_audio": {"type": "bool", "default": True},
            "movement_amplitude": {
                "type": "enum",
                "options": ["auto", "small", "medium", "large"],
                "default": "auto",
            },
            "seed": {"type": "int", "default": 0},
        },
        "audio_capability": "native",
        "available": True,
    },
    "vidu_q3_mix_ref": {
        "endpoint": "vidu/q3-mix/reference-to-video",
        "name_vn": "Vidu Q3-Mix Reference-to-Video",
        "variant": "reference-to-video",
        "vendor": "vidu",
        "cost_per_second_usd": 0.106,
        "duration": {"min": 1, "max": 16, "default": 5},
        "resolution": {"options": ["720p", "1080p"], "default": "720p"},  # KHÔNG có 540p
        "aspect_ratio": {
            "field_name": "aspect_ratio",
            "options": ["16:9", "9:16", "3:4", "4:3", "1:1"],
            "default": "16:9",
        },
        "images_field": "images",
        "max_references": 4,
        "min_references": 1,
        "required": ["model", "prompt", "images"],
        "extra_fields": {
            "negative_prompt": {"type": "string", "default": ""},  # V3.1 anti-artifact
            "generate_audio": {"type": "bool", "default": True},
            "movement_amplitude": {
                "type": "enum",
                "options": ["auto", "small", "medium", "large"],
                "default": "auto",
            },
            "seed": {"type": "int", "default": 0},
        },
        "audio_capability": "native",
        "available": True,
    },

    # ============== ALIBABA WAN 2.7 ==============
    "wan_2_7_i2v": {
        "endpoint": "alibaba/wan-2.7/image-to-video",
        # AtlasCloud docs 2026-05 verified:
        #   - POST /api/v1/model/generateVideo (NOT generateImage)
        #   - resolution LOWERCASE 480p/720p/1080p (per Wan 2.5 docs, 2.7 inherits)
        #   - duration discrete: 5 hoặc 10 seconds ONLY (per Wan 2.5 docs)
        "submit_path": "/model/generateVideo",
        "name_vn": "Wan 2.7 Image-to-Video",
        "variant": "image-to-video",
        "vendor": "alibaba",
        "cost_per_second_usd": 0.10,
        "duration": {
            "min": 5, "max": 10, "default": 5,
            "discrete_values": [5, 10],  # V3.5 — Wan ONLY accept 5 or 10
        },
        "resolution": {
            "options": ["480p", "720p", "1080p"],
            "default": "720p",
        },  # V3.5 — fix UPPERCASE → lowercase per atlas docs
        "aspect_ratio": None,  # i2v không có aspect (đọc từ image)
        "images_field": "image",  # SINGULAR "image" string
        "max_references": 1,
        "min_references": 1,
        "required": ["model", "image"],  # prompt optional cho i2v
        "extra_fields": {
            "prompt": {"type": "string", "default": ""},
            "negative_prompt": {"type": "string", "default": ""},
            "last_image": {"type": "string", "default": None, "desc": "Last-frame URL"},
            "video": {"type": "string", "default": None, "desc": "Video continuation URL"},
            "audio": {"type": "string", "default": None, "desc": "Driving audio URL (audio-driven mode)"},
            "prompt_extend": {"type": "bool", "default": True},
            "seed": {"type": "int", "default": -1, "min": -1, "max": 2147483647},
        },
        "audio_capability": "driven",  # qua field `audio`
        "available": True,
    },
    "wan_2_7_t2v": {
        "endpoint": "alibaba/wan-2.7/text-to-video",
        # AtlasCloud docs 2026-05 verified: lowercase resolution + discrete duration
        "submit_path": "/model/generateVideo",
        "name_vn": "Wan 2.7 Text-to-Video",
        "variant": "text-to-video",
        "vendor": "alibaba",
        "cost_per_second_usd": 0.10,
        "duration": {
            "min": 5, "max": 10, "default": 5,
            "discrete_values": [5, 10],
        },
        "resolution": {"options": ["480p", "720p", "1080p"], "default": "720p"},
        "aspect_ratio": {
            "field_name": "ratio",  # ⚠️ Wan t2v dùng "ratio" KHÔNG aspect_ratio
            "options": ["16:9", "9:16", "1:1", "4:3", "3:4"],
            "default": "16:9",
        },
        "images_field": None,
        "max_references": 0,
        "required": ["model", "prompt"],
        "extra_fields": {
            "negative_prompt": {"type": "string", "default": ""},
            "audio": {"type": "string", "default": None, "desc": "Soundtrack URL"},
            "prompt_extend": {"type": "bool", "default": True},
            "seed": {"type": "int", "default": -1, "min": -1, "max": 2147483647},
        },
        "audio_capability": "driven",
        "available": True,
    },

    # ============== SEEDANCE V1.5 PRO (BUDGET TIER) ==============
    # Live endpoint là "bytedance/seedance-v1.5-pro/*" (có "v" trước số) — KHÔNG phải "seedance-1.5-pro"
    # Schema KHÁC 2.0: dùng aspect_ratio (không phải ratio), duration 4-12s, resolution 720p/480p only
    "seedance_v15_pro_i2v": {
        "endpoint": "bytedance/seedance-v1.5-pro/image-to-video",
        "poll_path": "/model/result",  # ⚠️ Seedance v1.5 poll qua /result thay vì /prediction
        "name_vn": "Seedance 1.5 Pro Image-to-Video",
        "variant": "image-to-video",
        "vendor": "bytedance",
        "cost_per_second_usd": 0.047,
        "duration": {"min": 4, "max": 12, "default": 5},
        "resolution": {"options": ["480p", "720p"], "default": "720p"},
        "aspect_ratio": {
            "field_name": "aspect_ratio",  # ⚠️ V1.5 dùng aspect_ratio, 2.0 dùng ratio
            "options": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
            "default": "16:9",
        },
        "images_field": "image",
        "max_references": 1,
        "min_references": 1,
        "required": ["model", "image"],
        "extra_fields": {
            "negative_prompt": {"type": "string", "default": ""},  # V3.1 anti-artifact
            "prompt": {"type": "string", "default": ""},
            "last_image": {"type": "string", "default": None},
            "generate_audio": {"type": "bool", "default": True},
            "camera_fixed": {"type": "bool", "default": False},
            "seed": {"type": "int", "default": -1},
        },
        "audio_capability": "native",
        "available": True,
    },
    "seedance_v15_pro_t2v": {
        "endpoint": "bytedance/seedance-v1.5-pro/text-to-video",
        "poll_path": "/model/result",  # ⚠️ Seedance v1.5 poll qua /result
        "name_vn": "Seedance 1.5 Pro Text-to-Video",
        "variant": "text-to-video",
        "vendor": "bytedance",
        "cost_per_second_usd": 0.047,
        "duration": {"min": 4, "max": 12, "default": 5},
        "resolution": {"options": ["480p", "720p"], "default": "720p"},
        "aspect_ratio": {
            "field_name": "aspect_ratio",
            "options": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
            "default": "16:9",
        },
        "images_field": None,
        "max_references": 0,
        "required": ["model", "prompt"],
        "extra_fields": {
            "negative_prompt": {"type": "string", "default": ""},  # V3.1 anti-artifact
            "generate_audio": {"type": "bool", "default": True},
            "camera_fixed": {"type": "bool", "default": False},
            "seed": {"type": "int", "default": -1},
        },
        "audio_capability": "native",
        "available": True,
    },
    "seedance_v15_pro_i2v_fast": {
        "endpoint": "bytedance/seedance-v1.5-pro/image-to-video-fast",
        "poll_path": "/model/result",  # ⚠️ Seedance v1.5 poll qua /result
        "name_vn": "Seedance 1.5 Pro i2v FAST",
        "variant": "image-to-video",
        "vendor": "bytedance",
        "cost_per_second_usd": 0.018,  # RẺ NHẤT
        "duration": {"min": 4, "max": 12, "default": 5},
        "resolution": {"options": ["720p"], "default": "720p"},  # FAST locked 720p
        "aspect_ratio": {
            "field_name": "aspect_ratio",
            "options": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
            "default": "16:9",
        },
        "images_field": "image",
        "max_references": 1,
        "min_references": 1,
        "required": ["model", "image"],
        "extra_fields": {
            "negative_prompt": {"type": "string", "default": ""},  # V3.1 anti-artifact
            "prompt": {"type": "string", "default": ""},
            "last_image": {"type": "string", "default": None},
            "generate_audio": {"type": "bool", "default": True},
            "camera_fixed": {"type": "bool", "default": False},
            "seed": {"type": "int", "default": -1},
        },
        "audio_capability": "native",
        "available": True,
    },

    # ============== BYTEDANCE SEEDANCE 2.0 ==============
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
            "field_name": "ratio",  # ⚠️ Seedance dùng "ratio"
            "options": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"],
            "default": "adaptive",
        },
        "images_field": "reference_images",  # ⚠️ plural list
        "max_references": 9,
        "min_references": 1,  # ⚠️ schema strict minItems=1
        "required": ["model", "prompt"],
        "extra_fields": {
            "negative_prompt": {"type": "string", "default": ""},  # V3.1 anti-artifact
            "reference_videos": {"type": "array", "default": []},
            "reference_audios": {"type": "array", "default": []},
            "generate_audio": {"type": "bool", "default": True},
            "watermark": {"type": "bool", "default": False},
            "return_last_frame": {"type": "bool", "default": False},
        },
        "audio_capability": "native",
        "supports_multi_shot": True,  # @image1, @image2 syntax trong prompt
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
        "images_field": "image",  # SINGULAR
        "max_references": 1,
        "min_references": 1,
        "required": ["model", "image"],
        "extra_fields": {
            "negative_prompt": {"type": "string", "default": ""},  # V3.1 anti-artifact
            "prompt": {"type": "string", "default": ""},
            "last_image": {"type": "string", "default": None},
            "generate_audio": {"type": "bool", "default": True},
            "watermark": {"type": "bool", "default": False},
            "return_last_frame": {"type": "bool", "default": False},
        },
        "audio_capability": "native",
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
            "negative_prompt": {"type": "string", "default": ""},  # V3.1 anti-artifact
            "generate_audio": {"type": "bool", "default": True},
            "watermark": {"type": "bool", "default": False},
            "return_last_frame": {"type": "bool", "default": False},
        },
        "audio_capability": "native",
        "available": True,
    },

    # ============== SEEDANCE 2.0 FAST (MIDDLE TIER — cheaper 2.0) ==============
    # Schema giống 2.0 chuẩn, resolution KHÔNG có "1080p" thường (chỉ 480p/720p/720p-SR/1080p-SR/1440p-SR)
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
            "negative_prompt": {"type": "string", "default": ""},  # V3.1 anti-artifact
            "generate_audio": {"type": "bool", "default": True},
            "watermark": {"type": "bool", "default": False},
            "return_last_frame": {"type": "bool", "default": False},
        },
        "audio_capability": "native",
        "supports_multi_shot": True,
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
            "negative_prompt": {"type": "string", "default": ""},  # V3.1 anti-artifact
            "prompt": {"type": "string", "default": ""},
            "last_image": {"type": "string", "default": None},
            "generate_audio": {"type": "bool", "default": True},
            "watermark": {"type": "bool", "default": False},
            "return_last_frame": {"type": "bool", "default": False},
        },
        "audio_capability": "native",
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
            "negative_prompt": {"type": "string", "default": ""},  # V3.1 anti-artifact
            "generate_audio": {"type": "bool", "default": True},
            "watermark": {"type": "bool", "default": False},
            "return_last_frame": {"type": "bool", "default": False},
        },
        "audio_capability": "native",
        "available": True,
    },
}


# Cost hard cap per video (USD)
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


def build_payload(
    model_key: str,
    prompt: str,
    *,
    images: Optional[list[str]] = None,           # ref images (cho ref/i2v)
    image: Optional[str] = None,                  # first-frame (cho i2v)
    duration_s: Optional[int] = None,
    resolution: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    seed: Optional[int] = None,
    generate_audio: Optional[bool] = None,
    movement_amplitude: Optional[str] = None,
    audio_url: Optional[str] = None,
    last_image: Optional[str] = None,
    prompt_extend: Optional[bool] = None,
    watermark: Optional[bool] = None,
    return_last_frame: Optional[bool] = None,
    camera_fixed: Optional[bool] = None,
) -> dict:
    """Build payload đúng theo per-model spec.

    Tự động:
    - Map field names per-model (aspect_ratio vs ratio, images vs image vs reference_images)
    - Validate value range (duration min/max, resolution options)
    - Drop fields model không support
    """
    spec = get_spec(model_key)

    payload: dict = {"model": spec["endpoint"]}

    if prompt:
        payload["prompt"] = prompt

    # Duration validate (incl. discrete-values enforcement for Wan 2.7 — 5 or 10 only)
    if duration_s is not None:
        d = spec["duration"]
        if d.get("auto_sentinel") is not None and duration_s == d["auto_sentinel"]:
            payload["duration"] = duration_s  # -1 = auto
        elif duration_s < d["min"] or duration_s > d["max"]:
            raise ValueError(
                f"Duration {duration_s}s ngoài range {d['min']}-{d['max']}s cho {model_key}"
            )
        else:
            # BUG #2 fix — when the spec declares discrete_values (Wan 2.7 = [5, 10]),
            # snap to the closest allowed value rather than failing the render. This
            # protects downstream code from `7s` slipping through (range-check pass
            # but AtlasCloud 400 reject).
            discrete = d.get("discrete_values")
            if isinstance(discrete, list) and discrete:
                if duration_s not in discrete:
                    snapped = min(discrete, key=lambda v: abs(v - duration_s))
                    # Log a clear warning so callers see the snap happened.
                    import logging as _log
                    _log.getLogger(__name__).warning(
                        f"[model_specs] {model_key} duration {duration_s}s snapped to "
                        f"{snapped}s (allowed discrete: {discrete})"
                    )
                    duration_s = snapped
            payload["duration"] = duration_s

    # Resolution validate
    if resolution is not None:
        if resolution not in spec["resolution"]["options"]:
            raise ValueError(
                f"Resolution '{resolution}' không support cho {model_key}. "
                f"Options: {spec['resolution']['options']}"
            )
        payload["resolution"] = resolution

    # Aspect ratio — field name khác giữa các model
    if aspect_ratio is not None and spec.get("aspect_ratio"):
        ar_spec = spec["aspect_ratio"]
        if aspect_ratio not in ar_spec["options"]:
            raise ValueError(
                f"Aspect ratio '{aspect_ratio}' không support. "
                f"Options: {ar_spec['options']}"
            )
        payload[ar_spec["field_name"]] = aspect_ratio  # "aspect_ratio" hoặc "ratio"

    # Images — field name khác giữa các model
    img_field = spec.get("images_field")
    if img_field == "images":
        # Vidu: list — enforce minItems strict
        max_n = spec.get("max_references", 4)
        min_n = spec.get("min_references", 1)
        n_images = len(images) if images else 0
        if min_n > 0 and n_images < min_n:
            raise ValueError(
                f"{model_key} cần tối thiểu {min_n} images (nhận {n_images})"
            )
        if n_images > max_n:
            raise ValueError(f"{model_key} max {max_n} images, nhận {n_images}")
        if images:
            payload["images"] = images[:max_n]
    elif img_field == "image":
        # Wan/Seedance i2v: single string
        single = image or (images[0] if images else None)
        if not single and "image" in spec["required"]:
            raise ValueError(f"{model_key} bắt buộc field 'image' (first-frame URL)")
        if single:
            payload["image"] = single
    elif img_field == "reference_images":
        # Seedance ref: list — enforce minItems strict
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

    # Per-model extra fields
    extras = spec.get("extra_fields", {})

    if negative_prompt is not None and "negative_prompt" in extras:
        # Sprint2 M3 — cap to a safe length so we don't 400 the request at
        # vendor edge. AtlasCloud doesn't document per-model max but 1000
        # chars is comfortably below the typical 2000-char body cap and
        # plenty for "no watermark, no extra fingers, no deformed face, …".
        _NEG_MAX = extras["negative_prompt"].get("max_length", 1000)
        if len(negative_prompt) > _NEG_MAX:
            import logging as _log
            _log.getLogger(__name__).warning(
                f"[model_specs] {model_key} negative_prompt {len(negative_prompt)} "
                f"→ truncated to {_NEG_MAX} chars"
            )
            negative_prompt = negative_prompt[:_NEG_MAX]
        payload["negative_prompt"] = negative_prompt
    if seed is not None and "seed" in extras:
        payload["seed"] = seed
    if generate_audio is not None and "generate_audio" in extras:
        payload["generate_audio"] = generate_audio
    if movement_amplitude is not None and "movement_amplitude" in extras:
        if movement_amplitude not in extras["movement_amplitude"]["options"]:
            raise ValueError(
                f"movement_amplitude '{movement_amplitude}' invalid. "
                f"Options: {extras['movement_amplitude']['options']}"
            )
        payload["movement_amplitude"] = movement_amplitude
    if audio_url is not None and "audio" in extras:
        payload["audio"] = audio_url
    if last_image is not None and "last_image" in extras:
        payload["last_image"] = last_image
    if prompt_extend is not None and "prompt_extend" in extras:
        payload["prompt_extend"] = prompt_extend
    if watermark is not None and "watermark" in extras:
        payload["watermark"] = watermark
    if return_last_frame is not None and "return_last_frame" in extras:
        payload["return_last_frame"] = return_last_frame
    if camera_fixed is not None and "camera_fixed" in extras:
        payload["camera_fixed"] = camera_fixed

    # Final validate required
    for req in spec["required"]:
        if req not in payload:
            raise ValueError(f"{model_key} bắt buộc field '{req}' nhưng chưa có trong payload")

    return payload


def estimate_cost(model_key: str, duration_s: int) -> float:
    """Cost = rate × actual billed duration.

    Sprint3 B6: snap to discrete options (Wan 2.7 = [5,10]) BEFORE multiply so
    the FE estimate matches the AtlasCloud billed seconds. Without this, asking
    Wan 2.7 for 7s would show 7×rate but vendor charges for the snapped 10s.
    """
    spec = get_spec(model_key)
    dur_spec = spec["duration"]
    actual_duration = max(duration_s, dur_spec["min"])
    discrete = dur_spec.get("discrete_values")
    if discrete:
        # Round UP to nearest discrete option (vendor billing semantic)
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
            "aspect_ratio_options": spec.get("aspect_ratio", {}).get("options") if spec.get("aspect_ratio") else None,
            "max_references": spec.get("max_references", 0),
            "audio_capability": spec["audio_capability"],
            "extra_fields": list(spec.get("extra_fields", {}).keys()),
        })
    return out
