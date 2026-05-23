"""Shared utility — strip base64 data URLs + long URLs khỏi dict/list trước khi dump JSON cho LLM.

Defense against AtlasCloud 400 Bad Request khi user message vượt context window
(thường do frontend convert ảnh upload → data:image/...;base64,<~1-3MB> URL).

Usage:
    from core.llm_redact import safe_dumps
    user_msg = safe_dumps(visual_plan)  # base64 → "<base64_image_redacted len=2654832>"
"""

import json
from typing import Any


def redact_image_urls(obj: Any, max_url_len: int = 200) -> Any:
    """Recursively replace base64 data URLs + long HTTP URLs với placeholder.

    Args:
        obj: dict/list/str — payload chuẩn bị dump JSON cho LLM
        max_url_len: ngưỡng độ dài URL để giữ nguyên (default 200 chars)

    Returns:
        Same structure nhưng URLs > max_url_len bị redact.
    """
    if isinstance(obj, str):
        if obj.startswith("data:") and len(obj) > max_url_len:
            return f"<base64_image_redacted len={len(obj)}>"
        if (obj.startswith("http://") or obj.startswith("https://")) and len(obj) > max_url_len:
            return obj[:max_url_len] + f"...<truncated total={len(obj)}>"
        return obj
    if isinstance(obj, list):
        return [redact_image_urls(x, max_url_len) for x in obj]
    if isinstance(obj, dict):
        return {k: redact_image_urls(v, max_url_len) for k, v in obj.items()}
    return obj


def safe_dumps(obj: Any, indent: int = 2) -> str:
    """json.dumps SAU KHI redact image URLs — safe để pass cho LLM."""
    return json.dumps(redact_image_urls(obj), ensure_ascii=False, indent=indent)
