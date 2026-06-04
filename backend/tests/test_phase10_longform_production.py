"""Phase 10 tests for long-form production enablement."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_final_video_assembly_writes_metadata_and_final_url(tmp_path, monkeypatch) -> None:
    """Final assembly should upload to R2 and return a presigned URL."""
    from pipeline.approval_lock import ApprovalLockVerification
    from vendors.r2_storage import R2UploadResult
    from workers.final_assembly import FinalVideoAssemblyService
    from workers.longform_render_executor import LongFormRenderResult
    from workers.render_dry_run import RenderDryRunReport
    from workers.segment_renderer import SegmentRenderResult

    source_a = tmp_path / "a.mp4"
    source_b = tmp_path / "b.mp4"
    source_a.write_bytes(b"a")
    source_b.write_bytes(b"b")

    def fake_run(cmd: list[str], **kwargs: Any) -> None:
        Path(cmd[-1]).write_bytes(b"final")

    uploaded: dict[str, Any] = {}

    def fake_upload(local_path: str | Path, key: str, **kwargs: Any) -> R2UploadResult:
        uploaded["local_path"] = str(local_path)
        uploaded["key"] = key
        uploaded["kwargs"] = dict(kwargs)
        return R2UploadResult(
            bucket="cineforge-test",
            key=key,
            content_type=kwargs.get("content_type") or "video/mp4",
            size_bytes=Path(local_path).stat().st_size,
            storage_type="private",
            access_strategy="private_presigned",
            delivery_url="https://r2.test/presigned-final.mp4?sig=abc",
            public_url="https://cdn.test/longform/longform_test/final.mp4",
            presigned_url="https://r2.test/presigned-final.mp4?sig=abc",
            presigned_expires_s=3600,
            presigned_expires_at="2026-06-04T00:00:00+00:00",
            refresh_supported=True,
            attempts=2,
        )

    monkeypatch.setattr("workers.final_assembly.subprocess.run", fake_run)

    render_result = LongFormRenderResult(
        status="completed",
        longform_plan_id="longform_test",
        approval_lock_id="approval_test",
        approval_verification=ApprovalLockVerification(valid=True),
        dry_run_report=RenderDryRunReport(
            execution_plan_id="plan_test",
            approval_lock_id="approval_test",
            approval_valid=True,
            model="seedance_2_0",
            duration_s=30,
            aspect_ratio="9:16",
            resolution="720p",
        ),
        rendered_segments=[
            SegmentRenderResult(shot_id="segment_01_shot_0", index=0, video_url=str(source_a)),
            SegmentRenderResult(shot_id="segment_02_shot_0", index=1, video_url=str(source_b)),
        ],
    )
    result = FinalVideoAssemblyService(
        output_root=tmp_path / "out",
        ffmpeg_bin="ffmpeg",
        upload_result_sync=fake_upload,
    ).assemble(
        job_id="longform_test",
        longform_plan_id="longform_test",
        render_result=render_result,
        editor_preview={
            "distribution_package": {
                "title_en": "Launch film",
                "caption_en": "A polished launch story.",
                "hashtags_en": ["#CineForge", "#AIvideo"],
            }
        },
    )

    assert result.status == "completed"
    assert result.final_video_url == "https://r2.test/presigned-final.mp4?sig=abc"
    assert result.storage_type == "private"
    assert result.storage_access_strategy == "private_presigned"
    assert result.storage_delivery_url == "https://r2.test/presigned-final.mp4?sig=abc"
    assert result.storage_refresh_supported is True
    assert result.storage_key == "longform/longform_test/final.mp4"
    assert uploaded["key"] == "longform/longform_test/final.mp4"
    assert uploaded["kwargs"]["access_mode"] in {"auto", "public", "private"}
    assert uploaded["kwargs"]["presigned_expires_s"] >= 3600
    assert result.final_video_path is None
    assert uploaded["local_path"] and not Path(uploaded["local_path"]).exists()
    assert all(segment.local_path is None for segment in result.segments)
    assert all(segment.source_url is None for segment in result.segments)
    assert result.metadata_path is None
    assert result.title == "Launch film"
    assert result.caption == "A polished launch story."


def test_final_video_endpoint_returns_r2_url() -> None:
    """The final-video API should return object-storage URL metadata, not a local FileResponse."""
    import asyncio

    from api.routes import director

    async def run_case() -> None:
        director._JOBS_STORE.clear()
        director._JOBS_STORE["longform_job"] = {
            "status": "done",
            "assembly_result": {
                "final_video_url": "https://r2.test/final.mp4?sig=abc",
                "storage_bucket": "cineforge-test",
                "storage_key": "longform/longform_job/final.mp4",
                "storage_type": "private",
                "storage_access_strategy": "private_presigned",
                "storage_delivery_url": "https://r2.test/final.mp4?sig=abc",
                "storage_public_url": "https://cdn.test/longform/longform_job/final.mp4",
                "storage_presigned_url": "https://r2.test/final.mp4?sig=abc",
                "storage_presigned_expires_s": 3600,
                "storage_presigned_expires_at": "2099-01-01T00:00:00+00:00",
                "storage_refresh_supported": True,
            },
        }
        response = await director.get_job_final_video("longform_job")
        assert response["final_video_url"] == "https://r2.test/final.mp4?sig=abc"
        assert response["delivery_url"] == "https://r2.test/final.mp4?sig=abc"
        assert response["storage_key"] == "longform/longform_job/final.mp4"
        assert response["storage_type"] == "private"
        assert response["access_strategy"] == "private_presigned"
        assert response["cdn_url"] == "https://cdn.test/longform/longform_job/final.mp4"
        assert response["is_public"] is False
        assert response["presigned_expires_at"] == "2099-01-01T00:00:00+00:00"
        assert response["refresh_supported"] is True
        assert response["storage_refresh_supported"] is True

    asyncio.run(run_case())


def test_final_video_endpoint_refreshes_private_url(monkeypatch) -> None:
    """Private final video URLs should be refreshable from the persisted R2 object key."""
    import asyncio

    from api.routes import director

    async def run_case() -> None:
        director._JOBS_STORE.clear()
        director._JOBS_STORE["refresh_job"] = {
            "status": "done",
            "assembly_result": {
                "final_video_url": "https://r2.test/old.mp4?sig=old",
                "storage_bucket": "cineforge-test",
                "storage_key": "longform/refresh_job/final.mp4",
                "storage_type": "private",
                "storage_access_strategy": "private_presigned",
                "storage_presigned_url": "https://r2.test/old.mp4?sig=old",
                "storage_presigned_expires_at": "2020-01-01T00:00:00+00:00",
                "storage_refresh_supported": True,
            },
            "pipeline_trace": {
                "schema_version": "cineforge.pipeline_trace.v1",
                "trace_id": "trace_refresh_test",
                "input_id": "input_refresh_test",
                "entries": [],
            },
        }
        monkeypatch.setattr(
            director.r2_storage,
            "refresh_presigned_url_sync",
            lambda key: {
                "storage_presigned_url": f"https://r2.test/{key}?sig=fresh",
                "storage_presigned_expires_s": 7776000,
                "storage_presigned_expires_at": "2099-01-01T00:00:00+00:00",
                "refresh_supported": True,
            },
        )

        response = await director.get_job_final_video("refresh_job", refresh=True)

        assert response["final_video_url"] == "https://r2.test/longform/refresh_job/final.mp4?sig=fresh"
        assert response["storage_presigned_expires_s"] == 7776000
        assert response["refreshed"] is True
        assert director._JOBS_STORE["refresh_job"]["assembly_result"]["storage_presigned_url"].endswith("sig=fresh")
        assert director._JOBS_STORE["refresh_job"]["output_url"].endswith("sig=fresh")
        assert director._JOBS_STORE["refresh_job"]["output_path"].endswith("sig=fresh")
        trace_entries = director._JOBS_STORE["refresh_job"]["pipeline_trace"]["entries"]
        assert trace_entries[-1]["stage"] == "final_video_url_refresh"

    asyncio.run(run_case())


def test_r2_upload_result_retries_and_returns_presigned_url(tmp_path, monkeypatch) -> None:
    """R2 upload helper should retry transient failures and return structured URL metadata."""
    from vendors import r2_storage

    source = tmp_path / "final.mp4"
    source.write_bytes(b"final")

    class FlakyClient:
        def __init__(self) -> None:
            self.upload_calls = 0

        def upload_file(self, **kwargs: Any) -> None:
            self.upload_calls += 1
            if self.upload_calls == 1:
                raise RuntimeError("temporary upstream failure")

        def generate_presigned_url(self, *args: Any, **kwargs: Any) -> str:
            return "https://r2.test/presigned-final.mp4?sig=retry"

    client = FlakyClient()
    monkeypatch.setattr(r2_storage.settings, "r2_bucket_name", "cineforge-test")
    monkeypatch.setattr(r2_storage.settings, "r2_presigned_url_expires_s", 3600)
    monkeypatch.setattr(r2_storage.time, "sleep", lambda *_args, **_kwargs: None)

    result = r2_storage.upload_file_result_sync(
        source,
        "longform/job_retry/final.mp4",
        client=client,
        max_attempts=2,
        presign=True,
        presigned_expires_s=7776000,
        access_mode="private",
    )

    assert client.upload_calls == 2
    assert result.attempts == 2
    assert result.key == "longform/job_retry/final.mp4"
    assert result.storage_type == "private"
    assert result.access_strategy == "private_presigned"
    assert result.delivery_url == "https://r2.test/presigned-final.mp4?sig=retry"
    assert result.presigned_expires_s == 7776000
    assert result.refresh_supported is True
    assert result.presigned_url == "https://r2.test/presigned-final.mp4?sig=retry"


def test_r2_upload_result_uses_public_cdn_strategy(tmp_path, monkeypatch) -> None:
    """Public access mode should return a stable CDN/public delivery URL."""
    from vendors import r2_storage

    source = tmp_path / "final.mp4"
    source.write_bytes(b"final")

    class Client:
        def upload_file(self, **kwargs: Any) -> None:
            return None

        def generate_presigned_url(self, *args: Any, **kwargs: Any) -> str:
            return "https://r2.test/private-backup.mp4?sig=backup"

    monkeypatch.setattr(r2_storage.settings, "r2_bucket_name", "cineforge-test")
    monkeypatch.setattr(r2_storage.settings, "r2_public_url", "https://cdn.test")
    monkeypatch.setattr(r2_storage.settings, "r2_presigned_refresh_enabled", True)

    result = r2_storage.upload_file_result_sync(
        source,
        "longform/public_job/final.mp4",
        client=Client(),
        access_mode="public",
        presign=True,
    )

    assert result.storage_type == "public"
    assert result.access_strategy == "public_cdn"
    assert result.is_public is True
    assert result.delivery_url == "https://cdn.test/longform/public_job/final.mp4"
    assert result.cdn_url == "https://cdn.test/longform/public_job/final.mp4"
    assert result.refresh_supported is False


def test_r2_public_mode_requires_public_url_before_upload(tmp_path, monkeypatch) -> None:
    """Public mode must fail before creating an object when no public URL is configured."""
    import pytest

    from vendors import r2_storage

    source = tmp_path / "final.mp4"
    source.write_bytes(b"final")

    class Client:
        def __init__(self) -> None:
            self.upload_calls = 0

        def upload_file(self, **kwargs: Any) -> None:
            self.upload_calls += 1

    client = Client()
    monkeypatch.setattr(r2_storage.settings, "r2_bucket_name", "cineforge-test")
    monkeypatch.setattr(r2_storage.settings, "r2_public_url", "")

    with pytest.raises(RuntimeError, match="R2 public access mode requires"):
        r2_storage.upload_file_result_sync(
            source,
            "longform/no_public/final.mp4",
            client=client,
            access_mode="public",
        )

    assert client.upload_calls == 0
