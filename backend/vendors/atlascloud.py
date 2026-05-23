"""AtlasCloud API client — image + video + media upload.

Endpoints (theo doc https://www.atlascloud.ai/docs):
    POST {base_url}/model/generateImage     — image gen async
    POST {base_url}/model/generateVideo     — video gen async
    POST {base_url}/model/uploadMedia       — upload local file → URL
    GET  {base_url}/model/prediction/{id}   — poll status

Auth: Authorization: Bearer {ATLASCLOUD_API_KEY}
Base URL: https://api.atlascloud.ai/api/v1
"""

import time
import httpx
from pathlib import Path
from typing import Optional, Union
from loguru import logger

from core.config import settings
from vendors._retry import billable_retry
from agent.model_specs import build_payload as build_video_payload, get_spec


def _unwrap(data: dict) -> dict:
    """Unwrap AtlasCloud response — doc thật wrap trong {"data": {...}}.

    Some endpoint return flat, some nested. Handle cả 2.
    """
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        return data["data"]
    return data


class AtlasCloudClient:
    """Client cho AtlasCloud — image + video gen với async polling."""

    def __init__(self):
        self.base_url = settings.atlascloud_base_url.rstrip("/")
        self.api_key = settings.atlascloud_api_key
        self.client = httpx.Client(
            timeout=120.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        self._closed = False
        # FIX N4: register atexit close để httpx pool không leak
        import atexit
        atexit.register(self.close)

    def close(self) -> None:
        """Idempotent close — safe to call multiple times via atexit + GC.

        CRITICAL C12 fix: trước đây `__del__` cũng gọi `close()` → race với
        atexit khi process exit → double-close httpx pool, exception noise.
        Giờ guard bằng `_closed` flag + xoá `__del__` (atexit là điểm dọn dẹp).
        """
        if self._closed:
            return
        self._closed = True
        try:
            if self.client is not None:
                self.client.close()
        except Exception:
            pass

    def __repr__(self) -> str:
        # FIX N5: mask api key trong repr — tránh lộ qua exception trace
        from vendors._retry import mask_key
        return f"AtlasCloudClient(base_url={self.base_url}, key={mask_key(self.api_key)})"

    # ============================================
    # MEDIA UPLOAD — local file → atlas-hosted URL
    # ============================================

    @billable_retry()
    def upload_media(self, file_path: Union[str, Path]) -> str:
        """Upload local file → return public URL atlas-hosted.

        Response shape thực tế (verified 2026-05):
            {"code": 200, "message": "success", "data": {
                "type": "image|video|audio",
                "download_url": "https://atlas-img.oss-accelerate-overseas.aliyuncs.com/...",
                "filename": "<uuid>.png",
                "size": <bytes>
            }}
        """
        file_path = Path(file_path)
        # Guess MIME từ extension để AtlasCloud nhận đúng type (ảnh hưởng OSS routing)
        import mimetypes
        mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        with open(file_path, "rb") as f:
            response = httpx.post(
                f"{self.base_url}/model/uploadMedia",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (file_path.name, f, mime)},
                timeout=120.0,
            )
        response.raise_for_status()
        body = _unwrap(response.json())
        url = body.get("download_url") or body.get("url") or body.get("file_url")
        if not url:
            raise RuntimeError(f"AtlasCloud uploadMedia không trả URL. Body: {body}")
        return url

    # ============================================
    # IMAGE GENERATION
    # ============================================

    @billable_retry()
    def generate_image(
        self,
        prompt: str,
        model: str = "bytedance/seedream-v4.5",
        size: str = "2048*2048",
        n: int = 1,
        poll_interval_s: int = 3,
        timeout_s: int = 180,
    ) -> dict:
        """Gen image — async pattern: submit → poll prediction.

        ⚠️ Đối với production dùng routes/image_direct.py + build_image_payload()
        để build per-model schema chuẩn. Method này chỉ dùng cho test/demo nhanh.
        """
        response = self.client.post(
            f"{self.base_url}/model/generateImage",
            json={
                "model": model,
                "prompt": prompt,
                "size": size,
                "n": n,
            },
        )
        response.raise_for_status()
        body = _unwrap(response.json())
        prediction_id = body.get("id") or body.get("prediction_id")
        if not prediction_id:
            raise RuntimeError(f"AtlasCloud image submit không trả prediction_id: {body}")
        result = self._poll_prediction(prediction_id, poll_interval_s, timeout_s)
        outputs = result.get("outputs", [])
        return {
            "url": outputs[0] if outputs else result.get("output_url"),
            "model": model,
            "size": size,
            "prediction_id": prediction_id,
        }

    # ============================================
    # VIDEO GENERATION
    # ============================================

    def generate_video(
        self,
        *,
        model_key: str,
        prompt: str,
        images: Optional[list[str]] = None,
        image: Optional[str] = None,
        duration_s: Optional[int] = None,
        resolution: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        generate_audio: Optional[bool] = None,
        movement_amplitude: Optional[str] = None,
        audio_url: Optional[str] = None,
        last_image: Optional[str] = None,
        prompt_extend: Optional[bool] = None,
        watermark: Optional[bool] = None,
        return_last_frame: Optional[bool] = None,
        poll_interval_s: int = 5,
        timeout_s: int = 600,
    ) -> dict:
        """Submit video job + poll until done.

        ⚠️ Dùng build_payload() để build per-model spec chuẩn (Vidu aspect_ratio
        vs Wan/Seedance ratio, images vs image, ...). KHÔNG hardcode field.

        Args:
            model_key: key trong VIDEO_MODEL_SPECS (vidu_q3_ref, wan_2_7_i2v, ...)
            timeout_s: default 600 (10min). Sprint3 B8: callers MUST override
                for slow tiers — Vidu Q3-Mix 1080p 16s ≈ 8-12min, 1440p-SR
                ≈ 10-15min. Recommended: 900s for ≥1080p OR ≥12s, 1200s for
                1440p-SR. Job rate-limit may push higher on busy days.
        """
        # Sprint3 B8: warn when caller picks default timeout for a slow tier
        try:
            spec = get_spec(model_key)
            d = duration_s or spec.get("duration", {}).get("default", 0)
            res = (resolution or spec.get("resolution", {}).get("default") or "").lower()
            slow_tier = (
                d >= 12 or "1440" in res or "1080p-sr" in res
            )
            if slow_tier and timeout_s <= 600:
                logger.warning(
                    f"[AtlasCloud] {model_key} duration={d}s res={res} timeout={timeout_s}s "
                    f"may be insufficient (recommend ≥900s for slow tiers)"
                )
        except Exception:
            pass  # never block render on a sanity warning
        payload = build_video_payload(
            model_key=model_key,
            prompt=prompt,
            images=images,
            image=image,
            duration_s=duration_s,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            negative_prompt=negative_prompt,
            seed=seed,
            generate_audio=generate_audio,
            movement_amplitude=movement_amplitude,
            audio_url=audio_url,
            last_image=last_image,
            prompt_extend=prompt_extend,
            watermark=watermark,
            return_last_frame=return_last_frame,
        )
        # Per-model endpoint overrides (Wan 2.7 video dùng /generateImage,
        # Seedance v1.5 Pro poll qua /model/result thay vì /model/prediction)
        from agent.model_specs import VIDEO_MODEL_SPECS
        spec = VIDEO_MODEL_SPECS.get(model_key, {}) or {}
        submit_path = spec.get("submit_path", "/model/generateVideo")
        poll_path = spec.get("poll_path", "/model/prediction")
        prediction_id = self._submit_video_job(payload, submit_path=submit_path)
        result = self._poll_prediction(
            prediction_id, poll_interval_s, timeout_s, poll_path=poll_path,
        )
        outputs = result.get("outputs", [])
        # last_frame_url for Reference Chaining (Director V3 universal ref pattern).
        # AtlasCloud variants: last_frame_url | lastFrameUrl | last_frame | extra.last_frame_url
        last_frame = (
            result.get("last_frame_url")
            or result.get("lastFrameUrl")
            or result.get("last_frame")
            or (result.get("extra") or {}).get("last_frame_url")
        )
        return {
            "prediction_id": prediction_id,
            "video_url": outputs[0] if outputs else result.get("output_url"),
            "last_frame_url": last_frame,
            "duration_s": result.get("duration") or duration_s,
            "model": payload["model"],
        }

    # ============================================
    # REFERENCE CHAINING (V3 — Director Agent universal ref)
    # ============================================

    def generate_video_chain(
        self,
        *,
        scenes: list[dict],
        reference_image_pool: list[str],
        aspect_ratio: str = "9:16",
        resolution: str = "720p",
        negative_prompt: Optional[str] = None,
        poll_interval_s: int = 5,
        timeout_s: int = 600,
    ) -> list[dict]:
        """High-level helper: render N shots với Reference Chaining.

        Mỗi scene dict format (xuất từ Scene Generation Agent):
            {
                "shot_id":               "S1",
                "model_key":             "seedance_2_0_ref",   # ref-mode for shot 0
                "model_key_chain":       "seedance_2_0_i2v",   # i2v for chained shots
                "prompt":                "...",
                "negative_prompt":       "...",
                "duration_s":            5,
                "reference_image_urls":  [url, ...]            # primary refs (shot 0)
                "previous_shot_id":      None | "S0",          # chain anchor
                "movement_amplitude":    "auto",
                "generate_audio":        False,
            }

        Returns list of {shot_id, video_url, last_frame_url, prediction_id, duration_s}.
        Caller (worker) downloads + concats với FFmpeg.
        """
        results: list[dict] = []
        last_frame_url: Optional[str] = None

        for i, scene in enumerate(scenes):
            is_chain = bool(scene.get("previous_shot_id")) and last_frame_url is not None
            is_last = i == len(scenes) - 1
            model_key = scene.get("model_key_chain", scene["model_key"]) if is_chain else scene["model_key"]

            call_kwargs: dict = {
                "model_key": model_key,
                "prompt": scene["prompt"],
                "duration_s": scene["duration_s"],
                "resolution": resolution,
                "aspect_ratio": aspect_ratio,
                "negative_prompt": scene.get("negative_prompt") or negative_prompt,
                "return_last_frame": not is_last,
                "poll_interval_s": poll_interval_s,
                "timeout_s": timeout_s,
                "generate_audio": scene.get("generate_audio"),
                "movement_amplitude": scene.get("movement_amplitude") or "auto",
            }
            if is_chain:
                call_kwargs["image"] = last_frame_url
            else:
                refs = scene.get("reference_image_urls") or reference_image_pool
                if refs:
                    if len(refs) == 1:
                        call_kwargs["image"] = refs[0]
                        call_kwargs["images"] = refs
                    else:
                        call_kwargs["images"] = refs

            logger.info(
                f"[chain] {scene['shot_id']} → {model_key} "
                f"mode={'i2v_chain' if is_chain else ('ref' if call_kwargs.get('images') else 't2v')} "
                f"dur={scene['duration_s']}s"
            )
            result = self.generate_video(**{k: v for k, v in call_kwargs.items() if v is not None})
            last_frame_url = result.get("last_frame_url")
            results.append({"shot_id": scene["shot_id"], **result})

        return results

    @billable_retry()
    def _submit_video_job(self, payload: dict, submit_path: str = "/model/generateVideo") -> str:
        """Submit prebuilt payload (đã qua build_payload).

        Args:
            submit_path: per-spec override (Wan 2.7 video dùng /model/generateImage).

        Doc response shape: { "data": { "id": "<prediction_id>", ... } }
        """
        response = self.client.post(
            f"{self.base_url}{submit_path}",
            json=payload,
        )
        # CRITICAL C13 — Explicit 402 handling BEFORE generic raise_for_status.
        # billable_retry already skips retry on 4xx, but without this branch the
        # final exception is a generic HTTPStatusError(402) — worker callers
        # sometimes retry the whole job which re-submits and risks a second
        # charge if the balance recovers between attempts. Raise a clearer
        # RuntimeError so the worker layer halts the job immediately.
        if response.status_code == 402:
            logger.error(
                f"[AtlasCloud] 402 INSUFFICIENT BALANCE on {submit_path} — "
                f"aborting to avoid double-charge on retry. Top-up at "
                f"atlascloud.ai/dashboard then retry."
            )
            raise RuntimeError(
                "AtlasCloud 402 insufficient balance — render aborted to prevent "
                "duplicate charges. Top-up wallet then re-submit."
            )
        response.raise_for_status()
        body = _unwrap(response.json())
        prediction_id = body.get("id") or body.get("prediction_id")
        if not prediction_id:
            raise RuntimeError(
                f"AtlasCloud video submit không trả prediction_id. Body: {body}"
            )
        logger.info(
            f"Video prediction {prediction_id} submitted (model={payload.get('model')})"
        )
        return prediction_id

    def _poll_prediction(
        self,
        prediction_id: str,
        poll_interval_s: int = 5,
        timeout_s: int = 600,  # Sprint2 M13 — 10min budget hợp lý cho video 15s.
                                # Vendor typically 60-300s; cap 600s phòng spike +
                                # đủ headroom cho 1440p-SR render.
                                # Caller có thể override per-call nếu cần.
        poll_path: str = "/model/prediction",
    ) -> dict:
        """Poll prediction status (image hoặc video).

        V3.5 — Tolerant polling:
            - 500/502/503/504 transient → log warning + retry (consecutive 5xx cap = 5
              trước khi raise — tránh re-submit waste cost)
            - 4xx (auth/notfound) → raise ngay (genuine error)

        Doc response shape: { "data": { "status": "...", "outputs": [...], "error": ... } }
        Status terminal: 'completed' | 'succeeded' | 'failed'
        """
        start_time = time.time()
        last_status = None
        consecutive_5xx = 0
        MAX_CONSECUTIVE_5XX = 5  # ~25s of 5s polls = give up

        while time.time() - start_time < timeout_s:
            try:
                response = self.client.get(
                    f"{self.base_url}{poll_path}/{prediction_id}"
                )
            except (httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                # Network transient — keep polling
                consecutive_5xx += 1
                if consecutive_5xx >= MAX_CONSECUTIVE_5XX:
                    raise RuntimeError(
                        f"Prediction {prediction_id} unreachable after {consecutive_5xx} attempts: {e}"
                    )
                logger.warning(
                    f"Prediction {prediction_id} poll network err {consecutive_5xx}/{MAX_CONSECUTIVE_5XX}: {e}"
                )
                time.sleep(poll_interval_s)
                continue

            # 5xx transient — KHÔNG raise ngay, tolerate đến cap rồi mới fail
            if 500 <= response.status_code < 600:
                consecutive_5xx += 1
                if consecutive_5xx >= MAX_CONSECUTIVE_5XX:
                    logger.error(
                        f"Prediction {prediction_id} HTTP {response.status_code} sau "
                        f"{consecutive_5xx} consecutive attempts — fail"
                    )
                    response.raise_for_status()  # raise now
                logger.warning(
                    f"Prediction {prediction_id} HTTP {response.status_code} (transient) "
                    f"{consecutive_5xx}/{MAX_CONSECUTIVE_5XX} — keep polling"
                )
                time.sleep(poll_interval_s)
                continue

            # Reset counter sau 1 lần OK
            consecutive_5xx = 0

            # 4xx (auth/notfound) → raise ngay
            response.raise_for_status()

            body = _unwrap(response.json())
            status = body.get("status", "pending")
            if status != last_status:
                logger.info(f"Prediction {prediction_id}: {status}")
                last_status = status

            if status in ("completed", "succeeded"):
                return body
            if status in ("failed", "cancelled", "canceled", "error"):
                raise RuntimeError(
                    f"Prediction {prediction_id} {status}: {body.get('error', 'unknown')}"
                )
            time.sleep(poll_interval_s)

        raise TimeoutError(
            f"Prediction {prediction_id} timeout sau {timeout_s}s (last status: {last_status})"
        )

    @billable_retry()
    def cancel_prediction(self, prediction_id: str) -> dict:
        """Cancel running prediction để tránh charge tiếp.

        ⚠️ AtlasCloud doc chưa khẳng định endpoint cancel.
        Thử cả 2 pattern phổ biến: DELETE /prediction/{id} hoặc POST /prediction/{id}/cancel.
        """
        for attempt in (
            ("DELETE", f"{self.base_url}/model/prediction/{prediction_id}"),
            ("POST", f"{self.base_url}/model/prediction/{prediction_id}/cancel"),
        ):
            method, url = attempt
            try:
                if method == "DELETE":
                    r = self.client.delete(url)
                else:
                    r = self.client.post(url)
                if r.status_code in (200, 202, 204):
                    logger.info(f"Cancelled prediction {prediction_id} ({method})")
                    return {"cancelled": True, "prediction_id": prediction_id}
            except Exception as e:
                logger.warning(f"Cancel attempt {method} fail: {e}")
        # Không cancel được — log để follow up
        logger.warning(f"Cancel prediction {prediction_id} không success — vẫn có thể bị charge")
        return {"cancelled": False, "prediction_id": prediction_id}


atlas_client = AtlasCloudClient() if settings.atlascloud_api_key else None
