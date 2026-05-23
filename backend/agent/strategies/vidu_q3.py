"""Vidu Q3 Strategy — reference-to-video với multi-entity consistency.

Sweet spot:
    - 2-4 nhân vật cần giữ identity xuyên video
    - Duration ≤ 16s (Vidu Q3 max)
    - Style ads/marketing/UGC budget
    - KHÔNG cần native audio (Vidu output silent default)

Format prompt model "ăn" được:
    "Elena (25-year-old Vietnamese woman, bob cut, white t-shirt) and
     Marcus (28-year-old man, casual suit) at Saigon cafe rooftop.
     Elena reaches for product while Marcus leans in curious.
     Soft golden hour lighting, handheld 35mm POV."

Refs là POSITIONAL — prompt PHẢI gọi tên từng entity. Tối đa 4 refs.

Pricing: $0.042/s (~$0.67 cho 16s)
Verified: AtlasCloud vidu/q3/reference-to-video schema.
"""

from typing import Optional

from agent.strategies.base import (
    NEGATIVE_PROMPT_MULTI_CHARACTER,
    Script,
    VideoJob,
    WorkflowStrategy,
)


class ViduQ3Strategy(WorkflowStrategy):
    user_model = "vidu_q3"
    atlas_model_key = "vidu_q3_ref"
    display_name_vn = "Vidu Q3 — Multi-character ref-to-video"

    def needs_keyframe_gen(self) -> bool:
        # Cần 1 ref ảnh per character — Phase 2.5 storyboard gen sẽ tạo
        return True

    def max_refs(self) -> int:
        return 4  # Vidu Q3 hard cap

    def storyboard_format_label(self) -> str:
        return "Inline-named entities prose: 'Elena (descr)... Marcus (descr)...'"

    def negative_prompt(self) -> str:
        # Vidu Q3 sweet spot multi-entity → priority chống identity blend.
        # Cũng chống product warp khi có product trong scene.
        return (
            NEGATIVE_PROMPT_MULTI_CHARACTER
            + ", "
            + "warped product, deformed packaging, wrong brand label, Vietnamese text mangled"
        )

    def suitability_score(self, script: Script) -> float:
        """Wins khi: 2-4 characters, ≤16s, ads/marketing style, KHÔNG lipsync."""
        score = 0.0
        n_chars = len(script.characters)
        if 2 <= n_chars <= 4:
            score += 0.5  # sweet spot
        elif n_chars == 1:
            score += 0.25
        if script.target_duration_s <= 16:
            score += 0.2
        if script.needs_lipsync:
            score -= 0.3  # Vidu không sync môi tốt
        if script.style in ("ads", "ugc", "marketing"):
            score += 0.2
        if not script.needs_native_audio:
            score += 0.1
        return max(0.0, min(score, 1.0))

    def reasoning_for_script(self, script: Script) -> str:
        n = len(script.characters)
        bits: list[str] = []
        if 2 <= n <= 4:
            bits.append(f"{n} nhân vật cần consistency — Vidu Q3 anchor 4 refs")
        if script.target_duration_s <= 16:
            bits.append(f"{script.target_duration_s}s ≤ 16s")
        if script.style in ("ads", "marketing"):
            bits.append("Style ads/marketing fit Vidu Q3")
        return " · ".join(bits) or "Ref-to-video multi-entity"

    def build_prompt(
        self,
        script: Script,
        keyframes: Optional[list[str]] = None,
        audio_urls: Optional[list[str]] = None,
    ) -> VideoJob:
        """Compose inline-named prompt — Vidu Q3 sweet spot."""
        # 1. Character entity descriptions inline (max 4)
        char_descs = ", ".join(
            f"{c.name_vn} ({c.physical_description()})"
            for c in script.characters[: self.max_refs()]
        )

        # 2. Compose action narrative — concat scenes thành 1 paragraph
        action_parts: list[str] = []
        for sc in script.scenes:
            sub = sc.subject or ""
            # Replace @char_id với tên Việt (vd "@main_character" → "Elena")
            for c in script.characters:
                sub = sub.replace(f"@{c.id}", c.name_vn)

            parts: list[str] = [sub] if sub else []
            if sc.action:
                parts.append(sc.action)
            if parts:
                action_parts.append(" ".join(parts))

        action_narrative = ". ".join(action_parts)

        # 3. Style + camera + lighting closing
        style_parts: list[str] = []
        if script.scenes:
            first = script.scenes[0]
            if first.camera:
                style_parts.append(first.camera.lower())
            if first.lighting:
                style_parts.append(first.lighting.lower())
        style_parts.append(f"{script.style} style")
        style_parts.append(f"{script.resolution_hint or '720p'}")

        prompt = (
            f"{char_descs}. {action_narrative}. "
            f"{', '.join(style_parts)}."
        )

        # 4. Build payload — Vidu Q3 schema
        payload: dict = {
            "model": "vidu/q3/reference-to-video",
            "prompt": prompt,
            "negative_prompt": self.negative_prompt(),
            "duration": min(max(script.target_duration_s, 3), 16),  # spec min 3s, max 16s
            "aspect_ratio": script.aspect_ratio,
            "resolution": script.resolution_hint or "720p",
        }

        # 5. Reference images — 1 per character (max 4)
        refs = (keyframes or [])[: self.max_refs()]
        if refs:
            payload["images"] = refs

        if script.needs_native_audio:
            payload["generate_audio"] = True

        return VideoJob(
            model_key=self.atlas_model_key,
            submit_path="/model/generateVideo",
            payload=payload,
            refs=refs,
            strategy_name=self.display_name_vn,
            reasoning=self.reasoning_for_script(script),
        )
