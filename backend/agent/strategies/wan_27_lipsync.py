"""Wan 2.7 Lipsync Strategy — i2v audio-driven (KHÔNG có text prompt).

🌟 ĐẶC BIỆT: model này KHÔNG nhận prompt text. Nó nhận:
    - 1 image portrait (face fronting camera, clear)
    - 1 audio file (dialogue VN, ≤20s, MP3/WAV)
    → Model TỰ sync môi + biểu cảm theo audio.

Sweet spot:
    - Talking head VN có dialogue
    - User cần lipsync chuẩn không-thể-thiếu
    - Duration ≤ 8s (Wan 2.7 max)

LLM job ở đây KHÔNG phải viết prompt video. Nó là:
    1. Extract dialogue VN từ script
    2. Call GenMax TTS → MP3 URL
    3. Pick portrait image (Phase 2.5 đã gen hoặc user upload)
    4. Pass image + audio cho Wan 2.7 — model tự lo

Pricing: $0.10/s (~$0.80 cho 8s)
Verified: AtlasCloud alibaba/wan-2.7/image-to-video schema (i2v variant với audio).
"""

from typing import Optional

from agent.strategies.base import (
    NEGATIVE_PROMPT_TALKING_HEAD,
    Script,
    VideoJob,
    WorkflowStrategy,
)


class Wan27LipsyncStrategy(WorkflowStrategy):
    user_model = "wan_2_7"
    atlas_model_key = "wan_2_7_i2v"
    display_name_vn = "Wan 2.7 — Audio-driven lipsync VN"

    def needs_keyframe_gen(self) -> bool:
        # Cần 1 portrait ảnh fronting camera
        return True

    def max_refs(self) -> int:
        return 1  # i2v singular image

    def storyboard_format_label(self) -> str:
        return "TTS audio + portrait (NO text prompt — model tự sync môi)"

    def negative_prompt(self) -> str:
        return NEGATIVE_PROMPT_TALKING_HEAD

    def needs_tts_first(self) -> bool:
        return True  # Đây là pattern đặc biệt của Wan 2.7 lipsync

    def suitability_score(self, script: Script) -> float:
        """Wins khi: dialogue-only + lipsync mandatory + ≤8s."""
        score = 0.0
        if script.needs_lipsync:
            score += 0.5
        if script.is_dialogue_only():
            score += 0.2
        if script.target_duration_s <= 8:
            score += 0.2
        if len(script.characters) == 1:
            score += 0.1  # talking head single character
        # Trừ điểm nếu KHÔNG có dialogue (Wan không gen được scene-only)
        if not any(s.dialogue_vn for s in script.scenes):
            score -= 0.5
        return max(0.0, min(score, 1.0))

    def reasoning_for_script(self, script: Script) -> str:
        if script.needs_lipsync:
            return f"Talking head VN với dialogue · Wan 2.7 sync môi 99% chuẩn"
        return "Audio-driven lipsync (cần dialogue + portrait)"

    def build_prompt(
        self,
        script: Script,
        keyframes: Optional[list[str]] = None,
        audio_urls: Optional[list[str]] = None,
    ) -> VideoJob:
        """Build Wan 2.7 i2v job — KHÔNG có prompt text.

        Args:
            keyframes: list URLs ảnh portrait. Pick frame đầu tiên fronting camera.
            audio_urls: list URLs audio file. PHẢI có ít nhất 1 (TTS đã chạy trước).

        Raises:
            ValueError nếu thiếu image hoặc audio.
        """
        if not keyframes:
            raise ValueError(
                "[Wan27Lipsync] Cần ít nhất 1 portrait image. "
                "Phase 2.5 phải gen keyframe trước."
            )
        if not audio_urls:
            raise ValueError(
                "[Wan27Lipsync] Cần ít nhất 1 audio URL (TTS). "
                "Phase 2.5 phải call GenMax TTS trước với dialogue_vn."
            )

        portrait_url = keyframes[0]
        audio_url = audio_urls[0]

        # Wan 2.7 i2v schema — image + optional audio cho lipsync mode
        # V3.5: duration discrete {5, 10} per AtlasCloud Wan 2.5 docs (2.7 inherit)
        _user_dur = script.target_duration_s
        _wan_dur = 10 if _user_dur >= 8 else 5  # snap to nearest valid
        payload: dict = {
            "model": "alibaba/wan-2.7/image-to-video",
            "image": portrait_url,  # singular per Wan spec
            "audio": audio_url,  # drives lipsync
            "negative_prompt": self.negative_prompt(),
            "duration": _wan_dur,  # ONLY 5 or 10 valid
            "resolution": _normalize_wan_res(script.resolution_hint or "720p"),
        }

        # Optional: text prompt phụ trợ mood (Wan 2.7 ăn được nhưng audio mới chính)
        if script.scenes and script.scenes[0].action:
            payload["prompt"] = (
                f"Talking head, natural expression, {script.scenes[0].action}"
            )
        if script.scenes and script.scenes[0].lighting:
            payload["prompt"] = (
                payload.get("prompt", "Talking head") + f", {script.scenes[0].lighting}"
            )

        return VideoJob(
            model_key=self.atlas_model_key,
            submit_path="/model/generateVideo",  # AtlasCloud docs verified 2026-05
            payload=payload,
            refs=[portrait_url, audio_url],
            strategy_name=self.display_name_vn,
            reasoning=self.reasoning_for_script(script),
        )


def _normalize_wan_res(res: str) -> str:
    """V3.5 — Wan 2.7 dùng LOWERCASE '720p' / '1080p' / '480p' (per AtlasCloud docs Wan 2.5).

    Fix: trước đây hardcode UPPERCASE — sai per atlas docs, 400 response possible.
    """
    res_lower = res.lower()
    if res_lower in ("480p", "720p", "1080p"):
        return res_lower
    # Map các giá trị khác → 720p (default safe)
    return "720p"
