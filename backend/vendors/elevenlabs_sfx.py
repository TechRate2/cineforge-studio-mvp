"""ElevenLabs Sound Effects client — cho Mode ASMR.

Text-to-SFX: "crisp cardboard box opening" → MP3 audio
Giá ~$0.02/effect, dùng 5-8 effect/video ASMR.
"""

import httpx
from loguru import logger

from core.config import settings


class ElevenLabsSFXClient:
    """Client ElevenLabs Sound Effects API."""

    def __init__(self):
        self.api_key = settings.elevenlabs_api_key
        self.base_url = "https://api.elevenlabs.io/v1"
        self.client = httpx.Client(
            timeout=60.0,
            headers={"xi-api-key": self.api_key},
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
        return f"ElevenLabsSFXClient(base={self.base_url}, key={mask_key(self.api_key)})"

    def generate_sfx(
        self,
        text_prompt: str,
        duration_s: float = 2.0,
        prompt_influence: float = 0.5,
    ) -> bytes:
        """Generate sound effect MP3 từ text prompt.

        Args:
            text_prompt: VD "crisp cardboard box opening with tape ripping"
            duration_s: 0.5-22s
            prompt_influence: 0-1 (0=creative, 1=strict to prompt)

        Returns:
            bytes MP3 audio
        """
        response = self.client.post(
            f"{self.base_url}/sound-generation",
            headers={"Content-Type": "application/json"},
            json={
                "text": text_prompt,
                "duration_seconds": duration_s,
                "prompt_influence": prompt_influence,
            },
        )
        response.raise_for_status()
        logger.info(f"ElevenLabs SFX gen: '{text_prompt}' → {len(response.content)} bytes")
        return response.content

    def generate_sfx_batch(
        self,
        prompts: list[dict],  # [{"text": "...", "duration_s": 2.0, "filename": "sfx1.mp3"}]
        output_dir: str,
    ) -> list[str]:
        """Generate nhiều SFX cùng lúc, save xuống disk."""
        from pathlib import Path

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        files = []
        for p in prompts:
            audio_bytes = self.generate_sfx(
                text_prompt=p["text"],
                duration_s=p.get("duration_s", 2.0),
            )

            filepath = output_path / p["filename"]
            filepath.write_bytes(audio_bytes)
            files.append(str(filepath))
            logger.info(f"Saved SFX: {filepath}")

        return files


elevenlabs_sfx_client = ElevenLabsSFXClient() if settings.elevenlabs_api_key else None
