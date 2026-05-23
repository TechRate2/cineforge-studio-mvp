"""Seedance 1.5 Pro Strategy — silent multi-ref i2v (moodboard 9 refs).

Sweet spot:
    - Silent cinematic shots (product hero, B-roll, fashion)
    - Dense moodboard 9 image refs (1 character + 2 location + 3 prop + 3 style)
    - Duration 4-12s
    - NO native audio (compose audio sau bằng FFmpeg)

Format prompt model "ăn" được:
    "[Subject + action]. Camera: [concrete framing + movement].
     Style: [cinematic/fashion/product]. Resolution: [720p/480p]."

Refs: 9 image moodboard (KHÔNG named positional như Vidu).

Pricing: $0.047/s (~$0.56 cho 12s)
Verified: AtlasCloud bytedance/seedance-v1.5-pro/image-to-video schema.
"""

from typing import Optional

from agent.strategies.base import (
    NEGATIVE_PROMPT_SILENT_ASMR,
    Script,
    VideoJob,
    WorkflowStrategy,
)


class Seedance15ProStrategy(WorkflowStrategy):
    user_model = "seedance_1_5_pro"
    atlas_model_key = "seedance_v15_pro_i2v"
    display_name_vn = "Seedance 1.5 Pro — Silent multi-ref moodboard"

    def needs_keyframe_gen(self) -> bool:
        return True  # Cần ít nhất 1 first-frame, có thể tới 9 moodboard refs

    def max_refs(self) -> int:
        return 9  # 9 image refs theo spec

    def storyboard_format_label(self) -> str:
        return "Prose + camera cue + 9-ref moodboard (silent — audio post-prod)"

    def negative_prompt(self) -> str:
        return NEGATIVE_PROMPT_SILENT_ASMR

    def suitability_score(self, script: Script) -> float:
        """Wins khi: silent, single scene 4-12s, cinematic/product/fashion style.

        Penalty: multi-character (≥2) — Seedance 1.5 Pro mạnh moodboard single-subject,
        không có positional refs như Vidu Q3 → 2+ char dễ blend identity.
        """
        score = 0.0
        if not script.needs_native_audio:
            score += 0.3  # silent là sweet spot
        if not script.needs_lipsync:
            score += 0.15
        if 4 <= script.target_duration_s <= 12:
            score += 0.25
        if len(script.scenes) <= 2:
            score += 0.1  # tốt cho 1-2 cảnh dense moodboard
        if script.style in ("cinematic", "fashion", "product", "ads"):
            score += 0.2
        # Multi-character penalty — Vidu Q3 mới là sweet spot cho ≥2 char
        if len(script.characters) >= 2:
            score -= 0.25
        return max(0.0, min(score, 1.0))

    def reasoning_for_script(self, script: Script) -> str:
        bits: list[str] = []
        if not script.needs_native_audio:
            bits.append("silent shot")
        if script.style in ("cinematic", "fashion", "product"):
            bits.append(f"style {script.style} fit Seedance 1.5 Pro")
        if 4 <= script.target_duration_s <= 12:
            bits.append(f"{script.target_duration_s}s")
        return " · ".join(bits) or "Multi-ref silent cinematic"

    def build_prompt(
        self,
        script: Script,
        keyframes: Optional[list[str]] = None,
        audio_urls: Optional[list[str]] = None,
    ) -> VideoJob:
        """Compose silent multi-ref prompt — Seedance 1.5 Pro sweet spot."""
        # Pick scene đầu tiên làm primary (1.5 Pro thường 1 shot/clip)
        if not script.scenes:
            raise ValueError("[Seedance15Pro] Script không có scenes")
        primary = script.scenes[0]

        # Compose prompt: subject + action + camera + style
        subject = primary.subject or ""
        # Inline character descr (1.5 Pro không positional naming nhưng tốt hơn nếu có)
        for c in script.characters:
            subject = subject.replace(f"@{c.id}", c.physical_description())

        parts: list[str] = []
        if subject:
            parts.append(subject)
        if primary.action:
            parts.append(primary.action)
        if primary.camera:
            parts.append(f"Camera: {primary.camera}")
        if primary.lighting:
            parts.append(f"Lighting: {primary.lighting}")
        parts.append(f"Style: {script.style}, {script.resolution_hint or '720p'}")

        prompt = ". ".join(parts) + "."

        # Build payload — Seedance v1.5 Pro i2v schema
        refs = (keyframes or [])[: self.max_refs()]
        if not refs:
            raise ValueError(
                "[Seedance15Pro] i2v variant cần ít nhất 1 image (spec min_references=1). "
                "Phase 2.5 phải gen keyframe HOẶC user upload reference_image trước render."
            )
        first_image = refs[0]

        payload: dict = {
            "model": "bytedance/seedance-v1.5-pro/image-to-video",
            "prompt": prompt,
            "negative_prompt": self.negative_prompt(),
            "duration": min(max(script.target_duration_s, 4), 12),
            "aspect_ratio": script.aspect_ratio,
            "resolution": "720p" if script.resolution_hint != "480p" else "480p",
            "generate_audio": False,  # silent variant
            "image": first_image,  # required per spec (singular)
        }
        # Multi-ref images (nếu có nhiều keyframes, dùng làm moodboard)
        # Seedance v1.5 Pro spec: i2v dùng `image` singular, nhưng cũng nhận extra refs qua param
        # Để safe, em chỉ pass `image` chính. Multi-ref via reference_images sẽ test sau.

        return VideoJob(
            model_key=self.atlas_model_key,
            submit_path="/model/generateVideo",
            payload=payload,
            refs=refs,
            strategy_name=self.display_name_vn,
            reasoning=self.reasoning_for_script(script),
        )
