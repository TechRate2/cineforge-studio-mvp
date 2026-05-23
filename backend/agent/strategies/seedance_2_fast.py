"""Seedance 2.0 Fast Strategy — rapid single-shot i2v (preview/iteration).

Sweet spot:
    - Preview/iteration nhanh + rẻ
    - Duration ngắn 3-5s
    - 1 shot đơn giản (KHÔNG multi-shot timeline như 2.0 full)

Format prompt model "ăn" được:
    1 câu ngắn — motion verb + camera. Strip subordinate clauses.
    vd: "Woman uncaps serum bottle, slow push-in close-up, golden hour."

Pricing: $0.076/s (~$0.38 cho 5s) — rẻ hơn 2.0 full ~20%
Verified: AtlasCloud bytedance/seedance-2.0-fast/reference-to-video schema.
"""

from typing import Optional

from agent.strategies.base import (
    NEGATIVE_PROMPT_BASE,
    Script,
    VideoJob,
    WorkflowStrategy,
)


class SeedanceV2FastStrategy(WorkflowStrategy):
    user_model = "seedance_2_0_fast"
    atlas_model_key = "seedance_2_0_fast_ref"
    display_name_vn = "Seedance 2.0 Fast — Rapid single-shot preview"

    def needs_keyframe_gen(self) -> bool:
        return True  # 1 first-frame anchor

    def max_refs(self) -> int:
        return 9  # Spec hỗ trợ tới 9 nhưng Fast best với 1-2

    def storyboard_format_label(self) -> str:
        return "Single-sentence motion verb (rapid iteration)"

    def suitability_score(self, script: Script) -> float:
        """Wins khi: duration ngắn 3-5s, 1 cảnh, preview/iteration use case."""
        score = 0.0
        if 3 <= script.target_duration_s <= 5:
            score += 0.4
        elif script.target_duration_s <= 8:
            score += 0.2
        if len(script.scenes) == 1:
            score += 0.2
        if script.style in ("preview", "iteration", "ugc"):
            score += 0.2
        # Trừ điểm nếu cần multi-shot — Fast không support timeline
        if len(script.scenes) >= 3:
            score -= 0.2
        return max(0.0, min(score, 1.0))

    def reasoning_for_script(self, script: Script) -> str:
        bits: list[str] = []
        if script.target_duration_s <= 5:
            bits.append(f"{script.target_duration_s}s ngắn — Fast variant rẻ 20%")
        if len(script.scenes) == 1:
            bits.append("1 cảnh đơn")
        if script.style in ("preview", "iteration"):
            bits.append("preview iteration")
        return " · ".join(bits) or "Single-shot rapid preview"

    def build_prompt(
        self,
        script: Script,
        keyframes: Optional[list[str]] = None,
        audio_urls: Optional[list[str]] = None,
    ) -> VideoJob:
        """Compose 1-sentence prompt — Seedance 2.0 Fast sweet spot."""
        if not script.scenes:
            raise ValueError("[SeedanceV2Fast] Script không có scenes")
        primary = script.scenes[0]

        # Compress to 1 sentence — action + camera + lighting
        subject = primary.subject or ""
        for c in script.characters:
            subject = subject.replace(f"@{c.id}", c.physical_description())

        # Get first sentence/clause of action only
        action = primary.action.split(".")[0] if primary.action else ""

        parts: list[str] = []
        if subject and action:
            parts.append(f"{subject} {action}")
        elif subject:
            parts.append(subject)
        elif action:
            parts.append(action)

        if primary.camera:
            parts.append(primary.camera.lower())
        if primary.lighting:
            parts.append(primary.lighting.lower())

        prompt = ", ".join(parts) + "."

        # Build payload — Seedance 2.0 Fast ref-to-video schema
        refs = (keyframes or [])[:2]  # Fast best với 1-2 refs

        payload: dict = {
            "model": "bytedance/seedance-2.0-fast/reference-to-video",
            "prompt": prompt,
            "negative_prompt": self.negative_prompt(),
            "duration": min(max(script.target_duration_s, 4), 15),
            "ratio": script.aspect_ratio,
            "resolution": script.resolution_hint or "720p",
        }
        if refs:
            payload["reference_images"] = refs

        return VideoJob(
            model_key=self.atlas_model_key,
            submit_path="/model/generateVideo",
            payload=payload,
            refs=refs,
            strategy_name=self.display_name_vn,
            reasoning=self.reasoning_for_script(script),
        )
