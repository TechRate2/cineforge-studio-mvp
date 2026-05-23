"""
IMAGE MODEL SPECS — single source of truth cho AtlasCloud image models.

Verified 2026-05-20 từ doc CHÍNH THỨC scrape qua Playwright.

Schema khác nhau giữa các vendor:
    - Seedream: dùng `size` "WxH" preset (vd "2048*2048")
    - Nano Banana: dùng `aspect_ratio` + `resolution` ("1k|2k|4k")
    - Wan 2.7: dùng `size` ("1K"|"2K") + `n` multiple outputs
    - Qwen Image: dùng `size` integer 512-2048

KHÔNG đoán — chỉ dùng spec đã verify.
"""

from typing import Any, Optional


IMAGE_MODEL_SPECS: dict[str, dict[str, Any]] = {
    # ============== BYTEDANCE SEEDREAM ==============
    "seedream_v45": {
        "endpoint": "bytedance/seedream-v4.5",
        "name_vn": "Seedream v4.5 — Text to Image",
        "variant": "text-to-image",
        "vendor": "bytedance",
        "required": ["model", "prompt"],
        "images_field": None,
        "max_references": 0,
        "size": {
            "field_name": "size",
            "options": [
                "2048*2048", "2304*1728", "1728*2304", "2848*1600", "1600*2848",
                "2496*1664", "1664*2496", "3136*1344", "4096*4096", "4704*3520",
                "3520*4704", "5504*3040", "3040*5504", "4992*3328", "3328*4992",
                "6240*2656",
            ],
            "default": "2048*2048",
        },
        "aspect_ratio": None,
        "resolution": None,
        "extras": {
            "enable_base64_output": {"type": "bool", "default": False},
        },
        "cost_per_image_usd": 0.036,  # verified live API 2026-05-20
        "submit_path": "/model/generateVideo",   # ⚠️ Seedream dùng generateVideo (per official schema 2026-05)
        "poll_path": "/model/result",            # ⚠️ Seedream poll qua /result thay vì /prediction
        "available": True,
    },
    "seedream_v45_edit": {
        "endpoint": "bytedance/seedream-v4.5/edit",
        "name_vn": "Seedream v4.5 — Edit",
        "variant": "edit",
        "vendor": "bytedance",
        "required": ["model", "prompt", "images"],
        "images_field": "images",
        "min_references": 1,
        "max_references": 10,
        "size": {
            "field_name": "size",
            "options": [
                "2048*2048", "2304*1728", "1728*2304", "2848*1600", "1600*2848",
                "2496*1664", "1664*2496", "3136*1344", "4096*4096", "4704*3520",
                "3520*4704", "5504*3040", "3040*5504", "4992*3328", "3328*4992",
                "6240*2656",
            ],
            "default": "2048*2048",
        },
        "aspect_ratio": None,
        "resolution": None,
        "extras": {
            "enable_base64_output": {"type": "bool", "default": False},
        },
        "cost_per_image_usd": 0.036,  # verified live API 2026-05-20
        "submit_path": "/model/generateVideo",   # ⚠️ Seedream edit cũng dùng generateVideo
        "poll_path": "/model/result",            # ⚠️ Seedream poll qua /result thay vì /prediction
        "available": True,
    },

    # ============== GOOGLE NANO BANANA PRO ==============
    "nano_banana_pro_t2i": {
        "endpoint": "google/nano-banana-pro/text-to-image",
        "name_vn": "Nano Banana Pro — Text to Image",
        "variant": "text-to-image",
        "vendor": "google",
        "required": ["model", "prompt"],
        "images_field": None,
        "max_references": 0,
        "size": None,
        "aspect_ratio": {
            "field_name": "aspect_ratio",
            "options": ["1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
            "default": "1:1",
        },
        "resolution": {
            "field_name": "resolution",
            "options": ["1k", "2k", "4k"],
            "default": "1k",
        },
        "extras": {
            "output_format": {"type": "enum", "options": ["default", "png", "jpeg"], "default": "default"},
            "enable_web_search": {"type": "bool", "default": False},
            "enable_base64_output": {"type": "bool", "default": False},
            "enable_sync_mode": {"type": "bool", "default": False},
        },
        "cost_per_image_usd": 0.084,  # verified live API 2026-05-20
        "available": True,
    },
    "nano_banana_pro_edit": {
        "endpoint": "google/nano-banana-pro/edit",
        "name_vn": "Nano Banana Pro — Edit",
        "variant": "edit",
        "vendor": "google",
        "required": ["model", "prompt", "images"],
        "images_field": "images",
        "min_references": 1,
        "max_references": 10,
        "size": None,
        "aspect_ratio": {
            "field_name": "aspect_ratio",
            "options": ["1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
            "default": "16:9",
        },
        "resolution": {
            "field_name": "resolution",
            "options": ["1k", "2k", "4k"],
            "default": "2k",
        },
        "extras": {
            "output_format": {"type": "enum", "options": ["default", "png", "jpeg"], "default": "default"},
            "enable_web_search": {"type": "bool", "default": False},
            "enable_base64_output": {"type": "bool", "default": False},
        },
        "cost_per_image_usd": 0.084,  # verified live API 2026-05-20
        "available": True,
    },

    # ============== GOOGLE NANO BANANA 2 (cheaper) ==============
    "nano_banana_2_t2i": {
        "endpoint": "google/nano-banana-2/text-to-image",
        "name_vn": "Nano Banana 2 — Text to Image",
        "variant": "text-to-image",
        "vendor": "google",
        "required": ["model", "prompt"],
        "images_field": None,
        "max_references": 0,
        "size": None,
        "aspect_ratio": {
            "field_name": "aspect_ratio",
            "options": ["1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
            "default": "16:9",
        },
        "resolution": {
            "field_name": "resolution",
            "options": ["1k", "2k", "4k"],
            "default": "1k",
        },
        "extras": {
            "output_format": {"type": "enum", "options": ["default", "png", "jpeg"], "default": "default"},
            "media_resolution": {"type": "enum", "options": ["default", "low", "medium", "high"], "default": "default"},
            "thinking_level": {"type": "enum", "options": ["default", "high", "minimal"], "default": "default"},
            "enable_web_search": {"type": "bool", "default": False},
            "enable_image_search": {"type": "bool", "default": False},
        },
        "cost_per_image_usd": 0.048,  # verified live API 2026-05-20
        "available": True,
    },
    "nano_banana_2_edit": {
        "endpoint": "google/nano-banana-2/edit",
        "name_vn": "Nano Banana 2 — Edit",
        "variant": "edit",
        "vendor": "google",
        "required": ["model", "prompt", "images"],
        "images_field": "images",
        "min_references": 1,
        "max_references": 14,
        "size": None,
        "aspect_ratio": {
            "field_name": "aspect_ratio",
            "options": ["1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
            "default": "16:9",
        },
        "resolution": {
            "field_name": "resolution",
            "options": ["1k", "2k", "4k"],
            "default": "1k",
        },
        "extras": {
            "output_format": {"type": "enum", "options": ["default", "png", "jpeg"], "default": "default"},
            "media_resolution": {"type": "enum", "options": ["default", "low", "medium", "high"], "default": "default"},
            "thinking_level": {"type": "enum", "options": ["default", "high", "minimal"], "default": "default"},
        },
        "cost_per_image_usd": 0.048,  # verified live API 2026-05-20
        "available": True,
    },

    # ============== ALIBABA WAN 2.7 IMAGE ==============
    "wan_2_7_t2i": {
        "endpoint": "alibaba/wan-2.7/text-to-image",
        "name_vn": "Wan 2.7 — Text to Image",
        "variant": "text-to-image",
        "vendor": "alibaba",
        "required": ["model", "prompt"],
        "images_field": None,
        "max_references": 0,
        "size": {
            "field_name": "size",
            "options": ["1K", "2K"],
            "default": "2K",
        },
        "aspect_ratio": None,
        "resolution": None,
        "extras": {
            "n": {"type": "int", "default": 1, "min": 1, "max": 4},
            "thinking_mode": {"type": "bool", "default": True},
            "seed": {"type": "int", "default": -1, "min": -1, "max": 2147483647},
            "enable_sync_mode": {"type": "bool", "default": False},
            "enable_base64_output": {"type": "bool", "default": False},
        },
        "cost_per_image_usd": 0.03,  # verified live API 2026-05-20
        "available": True,
    },
    "wan_2_7_edit": {
        "endpoint": "alibaba/wan-2.7/image-edit",
        "name_vn": "Wan 2.7 — Image Edit",
        "variant": "edit",
        "vendor": "alibaba",
        "required": ["model", "prompt", "images"],
        "images_field": "images",
        "min_references": 1,
        "max_references": 9,
        "size": {
            "field_name": "size",
            "options": ["1K", "2K"],
            "default": "2K",
        },
        "aspect_ratio": None,
        "resolution": None,
        "extras": {
            "n": {"type": "int", "default": 1, "min": 1, "max": 4},
            "thinking_mode": {"type": "bool", "default": True},
            "seed": {"type": "int", "default": -1, "min": -1, "max": 2147483647},
            "enable_sync_mode": {"type": "bool", "default": False},
            "enable_base64_output": {"type": "bool", "default": False},
        },
        "cost_per_image_usd": 0.03,  # verified live API 2026-05-20
        "available": True,
    },
}


MAX_COST_PER_IMAGE_USD = 1.0


def get_image_spec(model_key: str) -> dict:
    if model_key not in IMAGE_MODEL_SPECS:
        raise ValueError(
            f"Image model '{model_key}' không tồn tại. Available: {list(IMAGE_MODEL_SPECS.keys())}"
        )
    spec = IMAGE_MODEL_SPECS[model_key]
    if not spec.get("available", True):
        raise ValueError(f"Image model '{model_key}' KHÔNG available.")
    return spec


def build_image_payload(
    model_key: str,
    prompt: str,
    *,
    images: Optional[list[str]] = None,
    size: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    resolution: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    seed: Optional[int] = None,
    n: Optional[int] = None,
    output_format: Optional[str] = None,
    media_resolution: Optional[str] = None,
    thinking_level: Optional[str] = None,
    thinking_mode: Optional[bool] = None,
    enable_web_search: Optional[bool] = None,
    enable_image_search: Optional[bool] = None,
    enable_base64_output: Optional[bool] = None,
    enable_sync_mode: Optional[bool] = None,
) -> dict:
    """Build payload đúng spec per-image-model."""
    spec = get_image_spec(model_key)
    payload: dict = {"model": spec["endpoint"], "prompt": prompt}

    # Images (cho edit variants)
    if spec.get("images_field") == "images":
        if not images:
            if "images" in spec["required"]:
                raise ValueError(f"{model_key} bắt buộc `images` (1+ URLs)")
        else:
            max_n = spec.get("max_references", 10)
            min_n = spec.get("min_references", 1)
            if len(images) < min_n:
                raise ValueError(f"{model_key} cần tối thiểu {min_n} images")
            if len(images) > max_n:
                raise ValueError(f"{model_key} max {max_n} images, nhận {len(images)}")
            payload["images"] = images[:max_n]

    # Size (Seedream/Wan)
    if spec.get("size") and size:
        s_spec = spec["size"]
        if size not in s_spec["options"]:
            raise ValueError(f"{model_key} size invalid. Options: {s_spec['options']}")
        payload[s_spec["field_name"]] = size

    # Aspect ratio (Nano Banana)
    if spec.get("aspect_ratio") and aspect_ratio:
        ar = spec["aspect_ratio"]
        if aspect_ratio not in ar["options"]:
            raise ValueError(f"{model_key} aspect_ratio invalid. Options: {ar['options']}")
        payload[ar["field_name"]] = aspect_ratio

    # Resolution (Nano Banana 1k/2k/4k)
    if spec.get("resolution") and resolution:
        r = spec["resolution"]
        if resolution not in r["options"]:
            raise ValueError(f"{model_key} resolution invalid. Options: {r['options']}")
        payload[r["field_name"]] = resolution

    # Extras
    extras = spec.get("extras", {})
    locals_map = {
        "negative_prompt": negative_prompt,
        "seed": seed,
        "n": n,
        "output_format": output_format,
        "media_resolution": media_resolution,
        "thinking_level": thinking_level,
        "thinking_mode": thinking_mode,
        "enable_web_search": enable_web_search,
        "enable_image_search": enable_image_search,
        "enable_base64_output": enable_base64_output,
        "enable_sync_mode": enable_sync_mode,
    }
    for field, val in locals_map.items():
        if val is None or field not in extras:
            continue
        # Validate enum
        f_spec = extras[field]
        if f_spec.get("type") == "enum" and val not in f_spec["options"]:
            raise ValueError(f"{field}='{val}' invalid. Options: {f_spec['options']}")
        if f_spec.get("type") == "int":
            mn, mx = f_spec.get("min"), f_spec.get("max")
            if mn is not None and val < mn:
                raise ValueError(f"{field}={val} < min {mn}")
            if mx is not None and val > mx:
                raise ValueError(f"{field}={val} > max {mx}")
        payload[field] = val

    # Validate required
    for req in spec["required"]:
        if req not in payload:
            raise ValueError(f"{model_key} bắt buộc field '{req}'")

    return payload


def estimate_image_cost(model_key: str, n: int = 1) -> float:
    spec = get_image_spec(model_key)
    return spec.get("cost_per_image_usd", 0.05) * max(n, 1)


def list_image_models_for_ui() -> list[dict]:
    out = []
    for key, spec in IMAGE_MODEL_SPECS.items():
        if not spec.get("available", True):
            continue
        out.append({
            "key": key,
            "endpoint": spec["endpoint"],
            "name_vn": spec["name_vn"],
            "vendor": spec["vendor"],
            "variant": spec["variant"],
            "cost_per_image_usd": spec.get("cost_per_image_usd", 0.05),
            "max_references": spec.get("max_references", 0),
            "min_references": spec.get("min_references", 0),
            "size_options": spec["size"]["options"] if spec.get("size") else None,
            "aspect_ratio_options": spec["aspect_ratio"]["options"] if spec.get("aspect_ratio") else None,
            "resolution_options": spec["resolution"]["options"] if spec.get("resolution") else None,
            "extras": {k: v for k, v in spec.get("extras", {}).items()},
        })
    return out
