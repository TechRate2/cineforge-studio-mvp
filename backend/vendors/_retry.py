"""Retry policy SAFE cho cost-sensitive API calls.

KHÔNG retry 4xx (client errors — request sai retry vẫn fail, tốn tiền).
CHỈ retry 5xx, 408, 429, network errors (transient).
"""

import httpx
from tenacity import (
    retry as _tenacity_retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
)


def mask_key(key: str) -> str:
    """FIX N5: Mask API key cho log/repr safety.

    Output: 'sk-1234...wxyz' (4 đầu + 4 cuối, ẩn middle). Tránh lộ full key
    qua exception trace, vendor.__repr__, log debug.
    """
    if not key:
        return "(unset)"
    if len(key) <= 12:
        return key[:2] + "***" + key[-2:]
    return f"{key[:6]}...{key[-4:]}"


def _is_retryable_http(exc: BaseException) -> bool:
    """Chỉ retry HTTP status 5xx, 408 (timeout), 429 (rate limit)."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (408, 429) or exc.response.status_code >= 500
    # Network/connection errors → retry
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout, httpx.PoolTimeout)):
        return True
    return False


def billable_retry(max_attempts: int = 3):
    """Decorator retry SAFE cho call billable API.

    - 4xx errors (400/401/402/403/404/422): KHÔNG retry (vô ích + waste $)
    - 5xx errors + 408/429: retry với exponential backoff
    - Network errors: retry
    """
    return _tenacity_retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception(_is_retryable_http),
        reraise=True,
    )


def _is_retryable_llm(exc: BaseException) -> bool:
    """Retry policy CHỈ cho LLM — KHÔNG retry ReadTimeout (model hangs, retry vô ích).

    - 5xx, 429: retry (transient server issue)
    - ConnectTimeout, ConnectError, ReadError: retry (network blip)
    - ReadTimeout: KHÔNG retry (model đang treo, retry = treo tiếp)
    - 4xx khác: KHÔNG retry
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429,) or exc.response.status_code >= 500
    if isinstance(
        exc,
        (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout, httpx.ReadError),
    ):
        return True
    # ReadTimeout intentionally excluded
    return False


def llm_retry(max_attempts: int = 4):
    """Retry policy cho LLM call.

    FIX (post-incident 2026-05-21): user gặp 429 AtlasCloud LLM khi pipeline gen
    10+ call song song. Tăng max_attempts 2→4 + tăng backoff 1-4s → 2-15s
    để pipeline tolerant với rate limit burst.

    Khác billable_retry: KHÔNG retry ReadTimeout (model hangs vô hạn = bug, retry vô ích).

    Behavior:
        - attempt 1 fail (429/5xx) → wait 2s
        - attempt 2 fail → wait 4s
        - attempt 3 fail → wait 8s
        - attempt 4 fail → reraise (~14s tổng cộng — đủ để AtlasCloud rate window reset)
    """
    return _tenacity_retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=2, min=2, max=15),
        retry=retry_if_exception(_is_retryable_llm),
        reraise=True,
    )
