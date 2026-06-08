"""Direct media endpoints must fail closed when runtime env is missing."""
from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

import pytest
from fastapi import HTTPException, UploadFile


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _assert_missing_env(
    call: Callable[[], Awaitable[Any]],
    expected_env: str,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(call())

    exc = exc_info.value
    assert exc.status_code == 424
    assert exc.detail["code"] == "missing_env"
    assert exc.detail["missing_env"] == [expected_env]
    assert exc.detail["vendor_calls_performed"] is False


def test_direct_video_generation_reports_missing_env_before_job(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.routes import paid_guard, video_direct
    import vendors.atlascloud as atlascloud

    video_direct.DIRECT_JOBS.clear()
    monkeypatch.setattr(paid_guard.settings, "allow_direct_paid_generation", True, raising=False)
    monkeypatch.setattr(paid_guard.settings, "admin_api_key", "admin-secret", raising=False)
    monkeypatch.setattr(atlascloud, "atlas_client", None, raising=False)

    request = video_direct.DirectVideoRequest(
        model_key="seedance_2_0_fast_t2v",
        prompt="A simple 5 second product reveal on a clean table.",
        duration_s=5,
    )

    _assert_missing_env(
        lambda: video_direct.generate_direct(request, x_admin_key="admin-secret"),
        "ATLASCLOUD_API_KEY",
    )
    assert video_direct.DIRECT_JOBS == {}


def test_direct_image_generation_reports_missing_env_before_job(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.routes import image_direct, paid_guard
    import vendors.atlascloud as atlascloud

    image_direct.IMAGE_JOBS.clear()
    monkeypatch.setattr(paid_guard.settings, "allow_direct_paid_generation", True, raising=False)
    monkeypatch.setattr(paid_guard.settings, "admin_api_key", "admin-secret", raising=False)
    monkeypatch.setattr(atlascloud, "atlas_client", None, raising=False)

    request = image_direct.DirectImageRequest(
        model_key="seedream_v45",
        prompt="Premium skincare product photo on white acrylic.",
    )

    _assert_missing_env(
        lambda: image_direct.generate(request, x_admin_key="admin-secret"),
        "ATLASCLOUD_API_KEY",
    )
    assert image_direct.IMAGE_JOBS == {}


def test_direct_audio_generation_reports_missing_env_before_job(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.routes import audio_direct, paid_guard

    audio_direct.AUDIO_JOBS.clear()
    monkeypatch.setattr(paid_guard.settings, "allow_direct_paid_generation", True, raising=False)
    monkeypatch.setattr(paid_guard.settings, "admin_api_key", "admin-secret", raising=False)
    monkeypatch.setattr(audio_direct, "genmax_client", None, raising=False)

    request = audio_direct.TTSRequest(text="Xin chao, day la ban doc thu.", voice_preset="mai")

    _assert_missing_env(
        lambda: audio_direct.generate_tts(request, x_admin_key="admin-secret"),
        "GENMAX_API_KEY",
    )
    assert audio_direct.AUDIO_JOBS == {}


def test_media_upload_reports_missing_env_before_reading_file(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.routes import media_upload
    import vendors.atlascloud as atlascloud

    monkeypatch.setattr(atlascloud, "atlas_client", None, raising=False)
    upload = UploadFile(filename="ref.png", file=io.BytesIO(b"not-a-real-image"))

    _assert_missing_env(
        lambda: media_upload.upload_media(upload),
        "ATLASCLOUD_API_KEY",
    )


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAtlasHttpClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def get(self, url: str) -> _FakeResponse:
        return _FakeResponse(self.payload)


class _FakeAtlasClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.base_url = "https://atlas.test"
        self.client = _FakeAtlasHttpClient(payload)


def test_direct_video_poll_rejects_completed_local_output_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.routes import video_direct
    import vendors.atlascloud as atlascloud

    video_direct.DIRECT_JOBS.clear()
    video_direct.DIRECT_JOBS["video_local_output"] = {
        "job_id": "video_local_output",
        "prediction_id": "pred_video_local",
        "model_key": "seedance_2_0_fast_t2v",
        "requested_model_key": "seedance_2_0_fast_t2v",
        "payload": {},
        "cost_estimate_usd": 0.1,
        "poll_path": "/model/prediction",
        "status": "submitted",
    }
    monkeypatch.setattr(
        atlascloud,
        "atlas_client",
        _FakeAtlasClient({"data": {"status": "completed", "outputs": ["file:///tmp/video.mp4"]}}),
        raising=False,
    )

    result = asyncio.run(video_direct.poll_direct_job("video_local_output"))

    assert result["status"] == "failed"
    assert "HTTP(S)" in result["error"]
    assert "video_url" not in result
    assert video_direct.DIRECT_JOBS["video_local_output"]["status"] == "failed"


def test_direct_image_poll_rejects_completed_stub_output_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.routes import image_direct
    import vendors.atlascloud as atlascloud

    image_direct.IMAGE_JOBS.clear()
    image_direct.IMAGE_JOBS["image_stub_output"] = {
        "job_id": "image_stub_output",
        "prediction_id": "pred_image_stub",
        "model_key": "seedream_v45",
        "payload": {},
        "cost_estimate_usd": 0.1,
        "poll_path": "/model/prediction",
        "status": "submitted",
    }
    monkeypatch.setattr(
        atlascloud,
        "atlas_client",
        _FakeAtlasClient({"data": {"status": "succeeded", "outputs": ["stub://image/result"]}}),
        raising=False,
    )

    result = asyncio.run(image_direct.poll("image_stub_output"))

    assert result["status"] == "failed"
    assert "HTTP(S)" in result["error"]
    assert "image_url" not in result
    assert "image_urls" not in result
    assert image_direct.IMAGE_JOBS["image_stub_output"]["status"] == "failed"


class _FakeGenMaxClient:
    def text_to_speech(self, **kwargs: Any) -> dict[str, Any]:
        return {"id": "hist_local_audio"}

    def poll_until_done(self, history_id: str, timeout_s: int, interval_s: float) -> dict[str, Any]:
        return {
            "status": "completed",
            "result": {"audio_url": "file:///tmp/audio.mp3"},
            "credits_deducted": 1,
            "vendor_debug": {"secretish": "hidden"},
        }


def test_direct_audio_generation_rejects_completed_local_output_and_hides_raw(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.routes import audio_direct, paid_guard

    audio_direct.AUDIO_JOBS.clear()
    monkeypatch.setattr(paid_guard.settings, "allow_direct_paid_generation", True, raising=False)
    monkeypatch.setattr(paid_guard.settings, "admin_api_key", "admin-secret", raising=False)
    monkeypatch.setattr(audio_direct, "genmax_client", _FakeGenMaxClient(), raising=False)

    request = audio_direct.TTSRequest(text="Xin chao, day la ban doc thu.", voice_preset="mai")

    result = asyncio.run(audio_direct.generate_tts(request, x_admin_key="admin-secret"))
    cached = asyncio.run(audio_direct.get_job(result["job_id"]))

    assert result["status"] == "failed"
    assert result["audio_url"] is None
    assert "HTTP(S)" in result["error"]
    assert cached["status"] == "failed"
    assert cached["audio_url"] is None
    assert "raw_response" not in cached
