"""GenMax TTS client — PRIMARY TTS provider VN.

Doc: https://genmax.io/app/api-docs

GenMax aggregate 2 underlying providers (chọn qua `model_id`):
    1. ElevenLabs  — model_id="eleven_flash_v2_5" (multilingual_v2 KHÔNG support
                     tiếng Việt — verified GET /v1/models)
    2. MiniMax     — model_id="speech-2.8-turbo", provider="minimax"

Pattern:
    POST {GENMAX_BASE_URL}/v1/text-to-speech/{voice_id}
    Header: xi-api-key: {GENMAX_API_KEY}
    Body  : { text, model_id, language_code, voice_settings: {...} }

Voice ID resolution:
    - ElevenLabs : dùng voice_id UUID từ voice library
    - MiniMax    : dùng numeric voice_id (e.g. "226905123659939")
                   hoặc uniq_id (e.g. "English_ManWithDeepVoice")
                   hoặc UUID cho cloned voices
"""

from typing import Optional, Union
import httpx
from loguru import logger

from core.config import settings
from vendors._retry import billable_retry


# Preset alias → voice_id từ GenMax voice library.
# 12 giọng VN tổng:
#   • 6 ElevenLabs (premium quality, anh chọn): Mai, Ngân, Trân, Đức Huy, Ninh Đôn, Quân
#   • 6 MiniMax    (budget tier, discovered):   Tú Anh, Ngọc Huyền, Nghị Lực, Vui Vẻ, Anh Khôi, Voice Phật Pháp
VIETNAMESE_VOICE_PRESETS: dict[str, dict] = {
    # ============ ELEVENLABS (premium) ============
    # Female
    "mai": {
        "voice_id": "d5HVupAWCwe4e6GvMCAL",
        "provider": "elevenlabs",
        "label_vn": "Mai — Tự nhiên, sáng, thân thiện",
        "gender": "female",
        "tier": "premium",
    },
    "ngan": {
        "voice_id": "a3AkyqGG4v8Pg7SWQ0Y3",
        "provider": "elevenlabs",
        "label_vn": "Ngân — Dễ thương",
        "gender": "female",
        "tier": "premium",
    },
    "tran": {
        "voice_id": "MfnRBJHBrGwMSVFTatjK",
        "provider": "elevenlabs",
        "label_vn": "Trân — Điềm tĩnh",
        "gender": "female",
        "tier": "premium",
    },
    # Male
    "duc_huy": {
        "voice_id": "w2KTJ6MO4SIK6nWK4YH8",
        "provider": "elevenlabs",
        "label_vn": "Đức Huy",
        "gender": "male",
        "tier": "premium",
    },
    "ninh_don": {
        "voice_id": "aN7cv9yXNrfIR87bDmyD",
        "provider": "elevenlabs",
        "label_vn": "Ninh Đôn — Trầm ấm",
        "gender": "male",
        "tier": "premium",
    },
    "quan": {
        "voice_id": "puBBfOSRT9Dbk3FUJQGd",
        "provider": "elevenlabs",
        "label_vn": "Quân — Ấm áp, sâu sắc, lịch lãm",
        "gender": "male",
        "tier": "premium",
    },
    # ============ MINIMAX (budget) ============
    # Female
    "tu_anh": {
        "voice_id": "65df0a3c-f898-4c55-a1e1-f484c1458578",
        "provider": "minimax",
        "label_vn": "Tú Anh",
        "gender": "female",
        "tier": "budget",
    },
    "ngoc_huyen": {
        "voice_id": "19725c22-f795-4fa1-bfc5-88c5a82f9440",
        "provider": "minimax",
        "label_vn": "Ngọc Huyền — nữ trẻ chuẩn miền Bắc",
        "gender": "female",
        "tier": "budget",
    },
    # Male
    "anh_khoi": {
        "voice_id": "4c2fdd0e-1062-4888-93a9-1edcae71fcb0",
        "provider": "minimax",
        "label_vn": "Anh Khôi",
        "gender": "male",
        "tier": "budget",
    },
    "nghi_luc": {
        "voice_id": "4ef2cf86-58fd-4379-9177-8072a5fba1da",
        "provider": "minimax",
        "label_vn": "Nghị Lực — motivational",
        "gender": "male",
        "tier": "budget",
    },
    "vui_ve": {
        "voice_id": "86ba3c68-f9be-4c2e-957f-307e42c0ba61",
        "provider": "minimax",
        "label_vn": "Vui Vẻ — cheerful",
        "gender": "male",
        "tier": "budget",
    },
    "phat_phap": {
        "voice_id": "33aac688-e734-4acf-9e3f-7eb7519b6515",
        "provider": "minimax",
        "label_vn": "Voice Phật Pháp — religious/spiritual",
        "gender": "male",
        "tier": "budget",
    },
}

# Default preset (override qua .env.local: GENMAX_DEFAULT_VOICE_ID=<uuid>)
DEFAULT_FEMALE_PRESET = "mai"        # ElevenLabs premium
DEFAULT_MALE_PRESET = "ninh_don"     # ElevenLabs premium
DEFAULT_FEMALE_BUDGET = "tu_anh"     # MiniMax fallback
DEFAULT_MALE_BUDGET = "anh_khoi"     # MiniMax fallback


class GenMaxClient:
    """Client GenMax TTS — primary TTS provider VN."""

    def __init__(self):
        self.base_url = settings.genmax_base_url.rstrip("/")
        self.api_key = settings.genmax_api_key
        self.client = httpx.Client(
            timeout=120.0,
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
            },
        )
        self._closed = False
        # FIX N4 + CRITICAL C12: atexit-only cleanup (no __del__).
        import atexit
        atexit.register(self.close)

    def close(self) -> None:
        """Idempotent close — C12 fix."""
        if self._closed:
            return
        self._closed = True
        try:
            if self.client is not None:
                self.client.close()
        except Exception:
            pass

    def __repr__(self) -> str:
        # FIX N5: mask key
        from vendors._retry import mask_key
        return f"GenMaxClient(base={self.base_url}, key={mask_key(self.api_key)})"

    # ============================================
    # AUTH / CREDITS
    # ============================================

    def get_credits(self) -> dict:
        """GET /v1/auth/me → user info + credit_balance."""
        response = self.client.get(f"{self.base_url}/v1/auth/me")
        response.raise_for_status()
        return response.json()

    # ============================================
    # TEXT-TO-SPEECH
    # ============================================

    @billable_retry()
    def text_to_speech(
        self,
        text: str,
        voice_id: str,
        provider: str = "minimax",  # "elevenlabs" | "minimax"
        model_id: Optional[str] = None,
        language_code: str = "Vietnamese",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        speed: float = 1.0,
    ) -> dict:
        """POST /v1/text-to-speech/{voice_id}

        Args:
            text          : nội dung tiếng Việt có dấu
            voice_id      : path param — voice ElevenLabs UUID hoặc MiniMax numeric/uniq/UUID
            provider      : "minimax" (default) | "elevenlabs"
            model_id      : override default model. ElevenLabs="eleven_multilingual_v2",
                            MiniMax="speech-2.8-turbo"
            language_code : "Vietnamese" | "English" | ...
            stability/similarity_boost: chỉ ElevenLabs (0-1)
            speed         : 0.5-2.0

        Returns:
            dict — response GenMax (cần verify schema thật: audio_url hay history_id?)
        """
        # ⚠️ ElevenLabs default = eleven_flash_v2_5 (hỗ trợ tiếng Việt + rẻ 2× vs multilingual_v2)
        # eleven_multilingual_v2 KHÔNG support 'vi' — verified GET /v1/models (chỉ 29 lang, vi không có)
        default_model = {
            "elevenlabs": "eleven_flash_v2_5",
            "minimax":    "speech-2.8-turbo",
        }
        body: dict = {
            "text": text,
            "model_id": model_id or default_model[provider],
            "language_code": language_code,
        }
        # voice_settings = ElevenLabs only (stability/similarity_boost). MiniMax
        # has different voice-control schema; sending these would 400 or be
        # silently ignored. `speed` is supported by ElevenLabs only too.
        if provider == "elevenlabs":
            body["voice_settings"] = {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "speed": speed,
            }
        elif provider == "minimax":
            body["provider"] = "minimax"
            if speed != 1.0:
                body["speed"] = speed  # MiniMax supports top-level speed

        response = self.client.post(
            f"{self.base_url}/v1/text-to-speech/{voice_id}",
            json=body,
        )
        response.raise_for_status()
        data = response.json()
        logger.info(
            f"GenMax TTS [{provider}/{voice_id}]: {len(text)} chars → response keys={list(data.keys())}"
        )
        return data

    def text_to_speech_by_preset(self, text: str, preset: str, **kwargs) -> dict:
        """Wrapper dùng preset alias VN."""
        cfg = VIETNAMESE_VOICE_PRESETS.get(preset)
        if not cfg:
            raise ValueError(
                f"Preset '{preset}' không tồn tại. Có sẵn: {list(VIETNAMESE_VOICE_PRESETS.keys())}"
            )
        return self.text_to_speech(
            text=text,
            voice_id=cfg["voice_id"],
            provider=cfg["provider"],
            **kwargs,
        )

    # ============================================
    # HISTORY (async / retry pattern)
    # ============================================

    def get_history(self) -> list[dict]:
        """GET /v1/history — list recent TTS tasks (verified 2026-05)."""
        response = self.client.get(f"{self.base_url}/v1/history?limit=20")
        response.raise_for_status()
        data = response.json()
        return data.get("tasks", data.get("items", data)) if isinstance(data, dict) else data

    def get_history_detail(self, history_id: str) -> dict:
        """GET /v1/history/{id} — chứa result.audio_url khi status=completed (verified 2026-05).

        Shape: { id, status: "pending|completed|failed", progress, result: { audio_url }, error, ... }
        """
        response = self.client.get(f"{self.base_url}/v1/history/{history_id}")
        response.raise_for_status()
        return response.json()

    def poll_until_done(self, history_id: str, timeout_s: int = 60, interval_s: float = 2.0) -> dict:
        """Poll history/{id} until status terminal. Trả full task obj."""
        import time as _time
        start = _time.time()
        while _time.time() - start < timeout_s:
            d = self.get_history_detail(history_id)
            status = d.get("status", "pending")
            if status in ("completed", "succeeded", "success", "failed", "error"):
                return d
            _time.sleep(interval_s)
        return self.get_history_detail(history_id)  # final snapshot

    def delete_history(self, history_id: str) -> None:
        """DELETE /v1/history/{id} — verified path 2026-05."""
        response = self.client.delete(f"{self.base_url}/v1/history/{history_id}")
        response.raise_for_status()

    def retry_task(self, task_id: str) -> dict:
        """POST /v1/history/{id}/retry — UNVERIFIED (cần probe trước khi dùng prod)."""
        response = self.client.post(f"{self.base_url}/v1/history/{task_id}/retry")
        response.raise_for_status()
        return response.json()

    # ============================================
    # VOICES (list để pick voice_id thật)
    # ============================================

    def list_elevenlabs_default_voices(self) -> list[dict]:
        """GET /v1/voices/elevenlabs/default."""
        response = self.client.get(f"{self.base_url}/v1/voices/elevenlabs/default")
        response.raise_for_status()
        data = response.json()
        return data.get("voices", data) if isinstance(data, dict) else data

    def list_minimax_system_voices(self) -> list[dict]:
        """GET /v1/voices/minimax/system."""
        response = self.client.get(f"{self.base_url}/v1/voices/minimax/system")
        response.raise_for_status()
        data = response.json()
        return data.get("voices", data) if isinstance(data, dict) else data

    def list_languages(self) -> list[dict]:
        """GET /v1/languages."""
        response = self.client.get(f"{self.base_url}/v1/languages")
        response.raise_for_status()
        return response.json()

    def list_models(self) -> list[dict]:
        """GET /v1/models."""
        response = self.client.get(f"{self.base_url}/v1/models")
        response.raise_for_status()
        return response.json()


genmax_client = GenMaxClient() if settings.genmax_api_key else None
