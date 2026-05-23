"""Seedance 2.0 Strategy — multi-shot time-coded native (3-act trong 1 call).

Sweet spot:
    - Cinematic story 10-15s với 3 hồi rõ ràng (hook → body → CTA)
    - Cần native audio (BGM/SFX sync với video)
    - User muốn chuyển cảnh đẹp trong 1 video gen (KHÔNG cần concat sau)

Format prompt model "ăn" được:
    [00:00-00:05] Shot 1: Camera close-up. Action: ...
    [00:05-00:10] Shot 2: Camera medium pull-back. Action: ...
    [00:10-00:15] Shot 3: Camera wide. Action: ...
    @Audio1 as background music, cinematic score.

Pricing: $0.096/s (~$1.44 cho 15s 1080p)
Verified: AtlasCloud bytedance/seedance-2.0/reference-to-video schema.
"""

from typing import Optional

from agent.strategies.base import (
    NEGATIVE_PROMPT_CINEMATIC,
    Script,
    VideoJob,
    WorkflowStrategy,
)


class SeedanceV2Strategy(WorkflowStrategy):
    user_model = "seedance_2_0"
    atlas_model_key = "seedance_2_0_ref"
    display_name_vn = "Seedance 2.0 — Multi-shot time-coded"

    def needs_keyframe_gen(self) -> bool:
        # 1 first-frame keyframe giúp anchor identity ở Shot 1, nhưng KHÔNG bắt buộc
        return True

    def max_refs(self) -> int:
        # Seedance 2.0 hỗ trợ 9 image refs + 3 video + 3 audio
        return 9

    def storyboard_format_label(self) -> str:
        return "Time-coded shot timeline [00:00-00:05] Shot 1: ..."

    def negative_prompt(self) -> str:
        return NEGATIVE_PROMPT_CINEMATIC

    def suitability_score(self, script: Script) -> float:
        """Wins khi: 3+ shots, có native audio, duration 10-15s, cinematic style."""
        score = 0.0
        n_scenes = len(script.scenes)
        if n_scenes >= 3:
            score += 0.4
        elif n_scenes == 2:
            score += 0.2
        if script.needs_native_audio:
            score += 0.25
        if 10 <= script.target_duration_s <= 15:
            score += 0.2
        elif script.target_duration_s > 5:
            score += 0.1
        if script.style in ("cinematic", "ugc", "ads"):
            score += 0.15
        return min(score, 1.0)

    def reasoning_for_script(self, script: Script) -> str:
        n = len(script.scenes)
        bits: list[str] = []
        if n >= 3:
            bits.append(f"{n} cảnh — Seedance 2.0 chuyển cảnh đỉnh trong 1 call")
        if script.needs_native_audio:
            bits.append("cần BGM native")
        if 10 <= script.target_duration_s <= 15:
            bits.append(f"{script.target_duration_s}s sweet spot")
        return " · ".join(bits) or "Multi-shot cinematic"

    def build_prompt(
        self,
        script: Script,
        keyframes: Optional[list[str]] = None,
        audio_urls: Optional[list[str]] = None,
    ) -> VideoJob:
        """Compose TIME-CODED multi-shot prompt — Seedance 2.0 sweet spot."""
        # 1. Build time-code shot headers
        timeline_lines: list[str] = []
        t_cursor = 0.0
        for i, sc in enumerate(script.scenes, start=1):
            t_start = t_cursor
            t_end = t_cursor + sc.duration_s
            start_str = _fmt_time(t_start)
            end_str = _fmt_time(t_end)

            # Compose shot description — concat MCSLA fields concrete
            shot_parts: list[str] = []
            if sc.camera:
                shot_parts.append(f"Camera: {sc.camera}")
            if sc.subject:
                # Inline character description (anchor identity)
                sub = _inject_character_descriptions(sc.subject, script.characters)
                shot_parts.append(f"Subject: {sub}")
            if sc.lighting:
                shot_parts.append(f"Lighting: {sc.lighting}")
            if sc.action:
                shot_parts.append(f"Action: {sc.action}")
            shot_desc = ". ".join(shot_parts) + "."

            timeline_lines.append(
                f"[{start_str}-{end_str}] Shot {i} ({sc.purpose}): {shot_desc}"
            )
            t_cursor = t_end

        prompt = "\n".join(timeline_lines)

        # 2. Native audio tag (Seedance 2.0 hỗ trợ @Audio1)
        if script.needs_native_audio:
            prompt += "\n@Audio1 as background music, cinematic score matching mood."

        # 3. Build payload — Seedance 2.0 ref-to-video schema
        payload: dict = {
            "model": "bytedance/seedance-2.0/reference-to-video",
            "prompt": prompt,
            "negative_prompt": self.negative_prompt(),
            "duration": min(max(script.target_duration_s, 4), 15),  # spec min 4s, max 15s
            "ratio": script.aspect_ratio,
            "resolution": script.resolution_hint or "720p",
            "generate_audio": script.needs_native_audio,
        }

        # 4. Reference images — Seedance 2.0 spec hỗ trợ tới 9 images
        # Industry-tested: 1 keyframe per shot (Director shots[]) cho identity strong nhất.
        # Empirical: 3-5 refs là sweet spot quality/cost (>5 marginal improvement).
        refs = (keyframes or [])[: self.max_refs()]
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


def _fmt_time(t: float) -> str:
    """Convert seconds → 'MM:SS' format Seedance ăn."""
    total = int(round(t))
    return f"{total // 60:02d}:{total % 60:02d}"


def _inject_character_descriptions(subject: str, characters: list) -> str:
    """Thay @character_id bằng descr inline.

    vd 'subject = "@main_character cau mày"' + characters[main_character: 25yo Hanoi woman]
       → '25-year-old Hanoi woman with bob cut, white t-shirt cau mày'
    """
    if not characters or "@" not in subject:
        return subject
    result = subject
    for c in characters:
        token = f"@{c.id}"
        if token in result:
            result = result.replace(token, c.physical_description())
    return result
