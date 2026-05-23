"""System prompts loader — mtime-aware cache (CRITICAL C10 fix).

Đọc .md files trong thư mục này. Tách markdown để dễ iterate, KHÔNG hardcode
prompts trong .py code.

Multi-worker invalidation strategy:
  Trước (V3): `@lru_cache` function-level — admin PUT /admin/prompts/{name}
  clear cache trong CHÍNH process đó; uvicorn workers khác serve stale prompt
  cho đến khi natural eviction hoặc restart (30s–5min lag).

  Sau (V3 C10): module-level dict cache keyed by `(name, mtime_ns)`. Mỗi gọi
  `load(name)` stat() file (~µs) so sánh mtime với cached entry — match thì
  trả từ memory, mismatch thì re-read disk. Mọi worker tự discover update
  ngay khi file thay đổi. Không cần Redis pub-sub.

Cost: 1 os.stat() syscall mỗi call vào prompts (4 prompts × ~few hundred
calls/min = vài ngàn stats/min — negligible).
"""
from __future__ import annotations

import threading
from pathlib import Path

_DIR = Path(__file__).parent
_LOCK = threading.Lock()
# Cache: name → (mtime_ns, content)
_CACHE: dict[str, tuple[int, str]] = {}


def load(name: str) -> str:
    """Load 1 system prompt file theo name (vd: 'director', 'scene', 'evaluation').

    Multi-worker safe: when the file's mtime changes (admin PUT updates it on
    disk), every worker re-reads on next call. No cross-process IPC needed.

    Raises FileNotFoundError nếu file thiếu — fail-fast, KHÔNG silent fallback.
    """
    path = _DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"system_prompt '{name}' not found at {path}")

    mtime_ns = path.stat().st_mtime_ns
    cached = _CACHE.get(name)
    if cached and cached[0] == mtime_ns:
        return cached[1]

    # Stale or missing → re-read disk under lock (avoid duplicate reads under
    # concurrent first-access)
    with _LOCK:
        cached = _CACHE.get(name)
        if cached and cached[0] == mtime_ns:
            return cached[1]
        content = path.read_text(encoding="utf-8")
        _CACHE[name] = (mtime_ns, content)
        return content


def cache_clear() -> None:
    """Compatibility shim for callers expecting the old `load.cache_clear()` API.

    With mtime-keyed cache this is rarely needed (file edit is auto-detected),
    but the admin route still calls it for defensive correctness.
    """
    with _LOCK:
        _CACHE.clear()


# Backward compat: `load.cache_clear()` API used by `api/routes/admin.py`
load.cache_clear = cache_clear  # type: ignore[attr-defined]
