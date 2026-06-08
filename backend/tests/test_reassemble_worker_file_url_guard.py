from __future__ import annotations

import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.mark.asyncio
async def test_reassemble_refuses_file_url_without_explicit_dev_fallback(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from workers import reassemble_worker

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"local-dev-clip")
    dest = tmp_path / "out.mp4"
    monkeypatch.setattr(reassemble_worker.settings, "app_env", "production")
    monkeypatch.setattr(reassemble_worker.settings, "allow_r2_local_fallback", False)

    with pytest.raises(RuntimeError, match="file:// clip URLs require explicit development local fallback opt-in"):
        await reassemble_worker._download_clip(f"file://{source.as_posix()}", dest)

    assert not dest.exists()


@pytest.mark.asyncio
async def test_reassemble_file_url_requires_development_and_opt_in(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from workers import reassemble_worker

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"local-dev-clip")
    dest = tmp_path / "out.mp4"
    monkeypatch.setattr(reassemble_worker.settings, "app_env", "development")
    monkeypatch.setattr(reassemble_worker.settings, "allow_r2_local_fallback", True)

    await reassemble_worker._download_clip(f"file://{source.as_posix()}", dest)

    assert dest.read_bytes() == b"local-dev-clip"
