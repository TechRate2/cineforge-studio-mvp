"""Resolve local media tool binaries used by real assembly and QA paths."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal, Sequence

from core.config import settings

MediaToolName = Literal["ffmpeg", "ffprobe"]


def resolve_media_tool(name: MediaToolName, *, override: str | None = None) -> str | None:
    """Return a usable tool path from explicit config or PATH.

    Explicit `FFMPEG_BIN` / `FFPROBE_BIN` config is treated as authoritative:
    a bad configured path fails closed instead of silently falling back to PATH.
    """
    configured = str(override if override is not None else getattr(settings, f"{name}_bin", "") or "").strip()
    if configured:
        return _resolve_configured_tool(configured)
    return shutil.which(name)


def missing_media_tools(required: Sequence[MediaToolName] = ("ffmpeg", "ffprobe")) -> list[str]:
    """Return media tools unavailable through explicit config or PATH."""
    return [name for name in required if resolve_media_tool(name) is None]


def _resolve_configured_tool(value: str) -> str | None:
    path_markers = ("/", "\\")
    if not any(marker in value for marker in path_markers) and not Path(value).drive:
        return shutil.which(value)
    path = Path(value).expanduser()
    if path.is_file():
        return str(path.resolve())
    return None


__all__ = ["MediaToolName", "missing_media_tools", "resolve_media_tool"]
