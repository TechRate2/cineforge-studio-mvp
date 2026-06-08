from __future__ import annotations

import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_media_tool_resolver_uses_configured_binary_path(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from core import media_tools

    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.write_bytes(b"binary")
    monkeypatch.setattr(media_tools.settings, "ffmpeg_bin", str(ffmpeg), raising=False)
    monkeypatch.setattr(media_tools.shutil, "which", lambda _name: None)

    assert media_tools.resolve_media_tool("ffmpeg") == str(ffmpeg.resolve())


def test_media_tool_resolver_bad_configured_path_fails_closed(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from core import media_tools

    monkeypatch.setattr(media_tools.settings, "ffprobe_bin", str(tmp_path / "missing-ffprobe.exe"), raising=False)
    monkeypatch.setattr(media_tools.shutil, "which", lambda name: f"C:/tools/{name}.exe")

    assert media_tools.resolve_media_tool("ffprobe") is None
    assert media_tools.missing_media_tools(["ffprobe"]) == ["ffprobe"]


def test_final_assembly_and_delivery_qa_use_media_tool_resolver(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from workers.final_assembly import FinalVideoAssemblyService
    from workers.final_delivery_qa import FinalVideoDeliveryQAService
    import core.media_tools as media_tools

    ffmpeg = tmp_path / "ffmpeg.exe"
    ffprobe = tmp_path / "ffprobe.exe"
    ffmpeg.write_bytes(b"binary")
    ffprobe.write_bytes(b"binary")
    monkeypatch.setattr(media_tools.settings, "ffmpeg_bin", str(ffmpeg), raising=False)
    monkeypatch.setattr(media_tools.settings, "ffprobe_bin", str(ffprobe), raising=False)
    monkeypatch.setattr(media_tools.shutil, "which", lambda _name: None)

    assembly = FinalVideoAssemblyService(output_root=tmp_path / "assembly")
    delivery_qa = FinalVideoDeliveryQAService()

    assert assembly.ffmpeg_bin == str(ffmpeg.resolve())
    assert delivery_qa.ffprobe_bin == str(ffprobe.resolve())
