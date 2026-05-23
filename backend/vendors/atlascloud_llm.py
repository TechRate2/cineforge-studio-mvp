"""AtlasCloud LLM client — OpenAI-compat /v1/chat/completions.

Hỗ trợ DeepSeek V4 Flash/Pro + Qwen VL + Claude (qua AtlasCloud) + bất kỳ model Text nào trong catalog.

Pricing snapshot (verified 2026-05, $ per 1M tokens):
    deepseek-ai/deepseek-v4-flash     $0.14 / $0.28   ← default, rẻ nhất + đủ smart
    deepseek-ai/deepseek-v4-pro       $1.68 / $3.38   ← reasoning nặng
    qwen/qwen3-vl-30b-a3b-instruct    $0.15 / $0.60   ← vision (analyze ảnh sản phẩm)
    qwen/qwen3-vl-8b-instruct         $0.08 / $0.50   ← vision rẻ
    anthropic/claude-sonnet-4.6       $3    / $15     ← premium fallback (same Claude direct)
    anthropic/claude-haiku-4.5        $1    / $5      ← premium mid-tier

Endpoint: POST https://api.atlascloud.ai/v1/chat/completions
Auth: Authorization: Bearer {ATLASCLOUD_API_KEY}
"""

from typing import Optional, Any
import threading
import time as _time
import httpx
from loguru import logger

from core.config import settings
from vendors._retry import llm_retry


# FIX B (post-429 incident): Global semaphore throttle MAX concurrent LLM calls.
# AtlasCloud Coding Plan rate limit: ~30 RPM. Pipeline có 10+ persona LLM calls
# (VisualPlanner, Strategist, Director, 4 Copywriter sub, Critic) — nếu spam parallel
# tất cả → 429. Semaphore(3) đảm bảo max 3 đồng thời, KHÔNG block hoàn toàn (vẫn parallel
# vừa phải) nhưng giãn pace để vendor xử lý kịp.
_LLM_CONCURRENCY = threading.BoundedSemaphore(value=3)
_LLM_MIN_INTERVAL_S = 0.25  # min gap giữa 2 call liên tiếp (chống burst)
_last_call_lock = threading.Lock()
_last_call_ts: float = 0.0


def _throttle_before_call():
    """Block đến khi semaphore + min-interval đều OK."""
    _LLM_CONCURRENCY.acquire()
    global _last_call_ts
    with _last_call_lock:
        now = _time.monotonic()
        delta = now - _last_call_ts
        if delta < _LLM_MIN_INTERVAL_S:
            sleep_s = _LLM_MIN_INTERVAL_S - delta
            _time.sleep(sleep_s)
        _last_call_ts = _time.monotonic()


def _throttle_after_call():
    _LLM_CONCURRENCY.release()


# ============================================
# Known model IDs verified live trên AtlasCloud (2026-05-21).
# Fail-fast nếu code request model NGOÀI list này.
# Source: https://www.atlascloud.ai/models/list/llm
# ============================================
KNOWN_MODEL_IDS = {
    # DeepSeek
    "deepseek-ai/deepseek-v4-flash",
    "deepseek-ai/deepseek-v4-pro",
    "deepseek-ai/deepseek-v3.2",
    "deepseek-ai/deepseek-v3.2-speciale",
    "deepseek-ai/DeepSeek-V3.2-Exp",
    "deepseek-ai/DeepSeek-V3-0324",
    "deepseek-ai/DeepSeek-V3.1",
    "deepseek-ai/deepseek-r1-0528",
    # Qwen3-VL
    "qwen/qwen3-vl-30b-a3b-instruct",
    "qwen/qwen3-vl-30b-a3b-thinking",
    "qwen/qwen3-vl-8b-instruct",
    "qwen/qwen3-vl-235b-a22b-thinking",
    "Qwen/Qwen3-VL-235B-A22B-Instruct",
    # Anthropic (qua AtlasCloud proxy)
    "anthropic/claude-haiku-4.5",
    "anthropic/claude-haiku-4.5-20251001",
    "anthropic/claude-sonnet-4.6",
    "anthropic/claude-opus-4.7",
    # Others
    "zai-org/glm-5-turbo",
    "moonshotai/kimi-k2.5",
}

# Max tokens cap thực tế ở vendor — phòng request quá tải gây 400/server error
MAX_TOKENS_HARD_CAP = 8192


def _validate_chat_body(body: dict) -> None:
    """Defensive validate body /chat/completions trước khi gửi.

    Raise ValueError ngay tại client thay vì để AtlasCloud trả 400 confusing.
    """
    model = body.get("model")
    if not model:
        raise ValueError("[AtlasLLM] body missing 'model' field")
    if model not in KNOWN_MODEL_IDS:
        # Soft warn — KHÔNG raise (có thể là model mới chưa update list)
        logger.warning(
            f"[AtlasLLM] model '{model}' không có trong KNOWN_MODEL_IDS — "
            f"có thể là model mới. Nếu 400 → kiểm tra spelling."
        )
    messages = body.get("messages") or []
    if not isinstance(messages, list) or len(messages) == 0:
        raise ValueError("[AtlasLLM] body 'messages' phải là list non-empty")
    # max_tokens không vượt cap
    mt = body.get("max_tokens", 0)
    if mt > MAX_TOKENS_HARD_CAP:
        logger.warning(
            f"[AtlasLLM] max_tokens={mt} vượt cap {MAX_TOKENS_HARD_CAP} — clamp"
        )
        body["max_tokens"] = MAX_TOKENS_HARD_CAP


def _summarize_body_for_log(body: dict) -> dict:
    """Compact body summary cho log — KHÔNG dump full base64 images."""
    msgs = body.get("messages") or []
    msg_summary = []
    for m in msgs:
        role = m.get("role")
        content = m.get("content")
        if isinstance(content, str):
            msg_summary.append({"role": role, "text_len": len(content), "head": content[:80]})
        elif isinstance(content, list):
            parts = []
            for p in content:
                if p.get("type") == "text":
                    parts.append({"type": "text", "len": len(p.get("text", ""))})
                elif p.get("type") == "image_url":
                    url = (p.get("image_url") or {}).get("url", "")
                    is_data = url.startswith("data:")
                    parts.append({
                        "type": "image_url",
                        "is_data_url": is_data,
                        "size_kb": round(len(url) / 1024, 1) if is_data else None,
                    })
            msg_summary.append({"role": role, "parts": parts})
    return {
        "model": body.get("model"),
        "max_tokens": body.get("max_tokens"),
        "temperature": body.get("temperature"),
        "n_messages": len(msgs),
        "messages": msg_summary,
    }


# Cost table — $ per 1M tokens (input, output)
PRICING_PER_1M: dict[str, tuple[float, float]] = {
    "deepseek-ai/deepseek-v4-flash": (0.14, 0.28),
    "deepseek-ai/deepseek-v4-pro": (1.68, 3.38),
    "qwen/qwen3-vl-8b-instruct": (0.08, 0.50),
    "qwen/qwen3-vl-30b-a3b-instruct": (0.15, 0.60),
    "qwen/qwen3-vl-30b-a3b-thinking": (0.15, 1.50),
    "anthropic/claude-haiku-4.5-20251001": (1.0, 5.0),
    "anthropic/claude-sonnet-4.6": (3.0, 15.0),
    "anthropic/claude-opus-4.7": (5.0, 25.0),
}


class AtlasCloudLLMClient:
    """OpenAI-compat client cho AtlasCloud LLM catalog.

    Per docs (https://www.atlascloud.ai/docs/api-keys):
        Base URL  : https://api.atlascloud.ai/v1   (OpenAI-compat)
        Endpoint  : POST /chat/completions
        Auth      : Authorization: Bearer <api-key>

    Verified live (2026-05): cả 2 key đều dùng được LLM
      - Pay-as-you-go key → deduct từ general balance ($50)
      - Coding Plan key   → deduct từ Coding Plan subscription (cheaper khi có active sub)
    Strategy: thử Coding Plan trước (rẻ hơn), fallback Pay-as-you-go khi 402.
    """

    # Per-call timeout (s) — fail fast tránh hang vô hạn. Override qua arg nếu cần.
    # 90s đủ cho prompt nặng (Ranker với 5 variants × 3 fields) trên Flash model.
    DEFAULT_CALL_TIMEOUT_S = 90.0

    def __init__(self):
        self.base_url = settings.atlascloud_llm_base_url.rstrip("/")
        # 2 key — Coding Plan ưu tiên (subscription rate rẻ hơn token), Pay-as-you-go fallback
        self.coding_plan_key = settings.atlascloud_llm_api_key
        self.pay_as_you_go_key = settings.atlascloud_api_key
        # Default header dùng Coding Plan (rẻ hơn nếu có sub), fallback Pay-as-you-go
        self.api_key = self.coding_plan_key or self.pay_as_you_go_key
        # Cache: Coding Plan đã hết balance → all subsequent calls dùng Pay-as-you-go trực tiếp
        self._coding_plan_exhausted = False
        self.client = httpx.Client(
            timeout=self.DEFAULT_CALL_TIMEOUT_S,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        self._closed = False
        # FIX N4 + CRITICAL C12: atexit-only cleanup (no __del__ double-close).
        import atexit
        atexit.register(self.close)

    def close(self) -> None:
        """Idempotent close — C12 fix: guard with `_closed` flag."""
        if self._closed:
            return
        self._closed = True
        try:
            if self.client is not None:
                self.client.close()
        except Exception:
            pass

    def __repr__(self) -> str:
        # FIX N5: mask cả 2 key
        from vendors._retry import mask_key
        return (
            f"AtlasCloudLLMClient(base={self.base_url}, "
            f"coding={mask_key(self.coding_plan_key)}, "
            f"payg={mask_key(self.pay_as_you_go_key)}, "
            f"exhausted={self._coding_plan_exhausted})"
        )

    def _active_key(self) -> str:
        """Trả key hiện tại nên dùng dựa state cache."""
        if self._coding_plan_exhausted and self.pay_as_you_go_key:
            return self.pay_as_you_go_key
        return self.api_key

    @llm_retry()
    def chat_completions(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        response_format: Optional[dict] = None,
        timeout_s: Optional[float] = None,
    ) -> dict:
        """OpenAI-compat call. Trả raw response để caller xử lý.

        2-key fallback: Coding Plan → Pay-as-you-go khi 402.
        Sau lần 402 đầu tiên, cache state để skip thử Coding Plan ở call sau.
        """
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format:
            body["response_format"] = response_format

        active_key = self._active_key()
        call_timeout = timeout_s or self.DEFAULT_CALL_TIMEOUT_S

        # Defensive validate body trước khi gửi — phát hiện bug sớm
        _validate_chat_body(body)

        # FIX B: Throttle trước call — Semaphore(3) + min-interval 0.25s
        _throttle_before_call()
        try:
            # Direct httpx.post với timeout cụ thể (không qua self.client để header per-call)
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {active_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=call_timeout,
            )
        finally:
            _throttle_after_call()

        # FIX 1 (post-400-incident): Khi 400 — dump body summary để debug
        # KHÔNG dump full base64 images (quá dài), chỉ dump structure
        if response.status_code == 400:
            try:
                err_body = response.json()
            except Exception:
                err_body = {"raw_text": response.text[:500]}
            summary = _summarize_body_for_log(body)
            logger.error(
                f"[AtlasLLM] 400 Bad Request — server msg: {err_body}. "
                f"Request summary: {summary}"
            )

        # 402 từ Coding Plan → cache + fallback Pay-as-you-go MỘT lần duy nhất
        if (
            response.status_code == 402
            and active_key == self.coding_plan_key
            and self.pay_as_you_go_key
            and self.coding_plan_key
            and self.pay_as_you_go_key != self.coding_plan_key
        ):
            if not self._coding_plan_exhausted:
                logger.warning(
                    "[AtlasLLM] Coding Plan 402 → cached exhausted, all future calls use Pay-as-you-go"
                )
                self._coding_plan_exhausted = True
            # Fallback call cũng phải throttle
            _throttle_before_call()
            try:
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.pay_as_you_go_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=call_timeout,
                )
            finally:
                _throttle_after_call()
        response.raise_for_status()
        return response.json()

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        few_shot_examples: Optional[list[dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Compat với ClaudeClient.complete() — chỉ trả text.

        FIX 2: LLM cache lookup trước → save cost + latency khi user submit trùng.
        """
        model = model or settings.llm_model_analyzer

        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        if few_shot_examples:
            for ex in few_shot_examples:
                messages.append({"role": "user", "content": ex["input"]})
                messages.append({"role": "assistant", "content": ex["output"]})
        messages.append({"role": "user", "content": user_message})

        # FIX 2: Cache lookup (chỉ với temp ≤ 0.5 — analytical tasks consistent)
        from core import llm_cache as _cache
        hit = _cache.lookup(model, messages, max_tokens, temperature)
        if hit:
            return hit["text"]

        resp = self.chat_completions(model, messages, max_tokens=max_tokens, temperature=temperature)
        usage = resp.get("usage", {})
        cost = estimate_cost_usd(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        logger.info(
            f"[AtlasLLM] {model} in={usage.get('prompt_tokens')} out={usage.get('completion_tokens')} cost=${cost:.5f}"
        )
        text = resp["choices"][0]["message"]["content"]
        # FIX 2: Store cache
        _cache.store(
            model, messages, max_tokens, temperature, text,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )
        return text

    def complete_with_image(
        self,
        system_prompt: str,
        user_message: str,
        image_urls: list[str],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        """Vision call — image_urls phải public URL hoặc base64 data URI.

        FIX 2: Cache hash bao gồm image data URL → same ảnh + same prompt = hit 100%.
        """
        model = model or settings.llm_model_vision

        content_parts: list[dict] = [{"type": "text", "text": user_message}]
        for url in image_urls:
            content_parts.append({"type": "image_url", "image_url": {"url": url}})

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content_parts},
        ]

        # FIX 2: Cache lookup (vision analyzer thường temp ≤ 0.3 → cacheable)
        from core import llm_cache as _cache
        hit = _cache.lookup(model, messages, max_tokens, temperature)
        if hit:
            return hit["text"]

        resp = self.chat_completions(model, messages, max_tokens=max_tokens, temperature=temperature)
        usage = resp.get("usage", {})
        cost = estimate_cost_usd(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        logger.info(
            f"[AtlasLLM-Vision] {model} imgs={len(image_urls)} in={usage.get('prompt_tokens')} out={usage.get('completion_tokens')} cost=${cost:.5f}"
        )
        text = resp["choices"][0]["message"]["content"]
        _cache.store(
            model, messages, max_tokens, temperature, text,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )
        return text


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Tính cost USD dựa pricing table."""
    rates = PRICING_PER_1M.get(model)
    if not rates:
        return 0.0
    in_rate, out_rate = rates
    return (prompt_tokens / 1_000_000) * in_rate + (completion_tokens / 1_000_000) * out_rate


# Lazy singleton — chỉ init nếu có ít nhất 1 key
atlas_llm: Optional[AtlasCloudLLMClient] = None
if settings.atlascloud_llm_api_key or settings.atlascloud_api_key:
    atlas_llm = AtlasCloudLLMClient()
