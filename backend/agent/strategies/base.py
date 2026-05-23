"""WorkflowStrategy abstract base + Pydantic dataclasses.

Mỗi video model có 1 strategy concrete implement:
    - build_prompt(): rewrite script thành prompt format model "ăn" được
    - needs_keyframe_gen(): có cần Phase 2.5 gen ảnh trước không
    - max_refs(): số ảnh ref tối đa support
    - suitability_score(): chấm 0-1 model fit script đến đâu (cho smart picker)
"""

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, Field


# ============================================
# DATACLASSES — model-agnostic intermediate types
# ============================================


class Character(BaseModel):
    """1 nhân vật xuất hiện trong video — output từ Strategist.

    Schema bắt nguồn từ character_sheet của Director (xem director_system.md).
    """

    id: str = Field(..., description="vd 'main_character'")
    name_vn: str = Field(..., description="vd 'Cô gái Hà Nội 25 tuổi'")
    age_apparent: Optional[int] = None
    gender: Optional[str] = Field(None, description="F | M")
    face: str = Field("", description="Mô tả khuôn mặt + tóc")
    outfit_top: Optional[str] = None
    outfit_bottom: Optional[str] = None
    personality_traits: list[str] = Field(default_factory=list)

    def physical_description(self) -> str:
        """Compact descr cho prompt inline (Vidu Q3 named inline pattern)."""
        parts: list[str] = []
        if self.age_apparent:
            gender_word = (
                "woman" if self.gender == "F" else "man" if self.gender == "M" else "person"
            )
            parts.append(f"{self.age_apparent}-year-old Vietnamese {gender_word}")
        if self.face:
            parts.append(self.face)
        if self.outfit_top or self.outfit_bottom:
            outfit = " ".join(filter(None, [self.outfit_top, self.outfit_bottom]))
            parts.append(f"wearing {outfit}")
        return ", ".join(parts) if parts else self.name_vn


class Scene(BaseModel):
    """1 shot/scene trong storyboard — output từ Director."""

    shot_id: str = Field(..., description="vd 'S1', 'S2'")
    duration_s: float
    purpose: str = Field(..., description="hook | problem | solution | proof | cta")
    # MCSLA fields (Higgsfield-style)
    camera: str = Field("", description="C: concrete framing + lens + movement")
    subject: str = Field("", description="S: ai/cái gì hiện, có thể chứa @character_id ref")
    lighting: str = Field("", description="L: ánh sáng concrete")
    action: str = Field("", description="A: hành động beats")
    # Voice + caption
    dialogue_vn: Optional[str] = None
    caption_on_screen: Optional[str] = None
    # Model hint (optional override)
    model_hint: Optional[str] = None


class Script(BaseModel):
    """Model-agnostic script — output từ ProductStrategist + Director.

    Strategy nhận Script → tự rewrite thành format đúng cho target model.
    """

    title: str = Field("", description="Tiêu đề ngắn cho job")
    product_name: str = ""
    audience_desc: str = ""

    scenes: list[Scene] = Field(default_factory=list)
    characters: list[Character] = Field(default_factory=list)

    target_duration_s: int = 15
    aspect_ratio: str = "9:16"
    resolution_hint: str = "720p"

    needs_lipsync: bool = Field(
        False, description="True nếu video chính là talking head có dialogue sync môi"
    )
    needs_native_audio: bool = Field(
        False, description="True nếu cần BGM/SFX native từ video model"
    )
    style: str = Field("ugc", description="ugc | cinematic | ads | anime | corporate")
    user_brief: str = ""

    def is_dialogue_only(self) -> bool:
        """True nếu tất cả scenes là dialogue (lipsync candidate)."""
        if not self.scenes:
            return False
        return all(bool(s.dialogue_vn) for s in self.scenes)


class VideoJob(BaseModel):
    """Output cuối của strategy — sẵn sàng submit AtlasCloud.

    `model_key` là AtlasCloud spec key (vd 'seedance_2_0_ref', 'vidu_q3_ref').
    `payload` là raw JSON body API.
    `refs` là list URLs upload (image / audio).
    """

    model_key: str = Field(..., description="AtlasCloud model_specs.py key")
    submit_path: str = Field(
        "/model/generateVideo", description="API path (per spec override)"
    )
    payload: dict
    refs: list[str] = Field(default_factory=list, description="Image/audio refs URLs")
    # Metadata cho UI / debug
    strategy_name: str = ""
    reasoning: str = Field("", description="1 câu giải thích vì sao strategy chọn format này")


# ============================================
# WorkflowStrategy abstract base
# ============================================


class WorkflowStrategy(ABC):
    """Interface mỗi strategy implement.

    Naming convention:
        user_model: key user chọn ở UI (vd 'seedance_2_0')
        atlas_model_key: key trong agent/model_specs.py (vd 'seedance_2_0_ref')
    """

    user_model: str  # 'seedance_2_0' | 'vidu_q3' | 'wan_2_7' | ...
    atlas_model_key: str  # 'seedance_2_0_ref' | 'vidu_q3_ref' | 'wan_2_7_i2v' | ...
    display_name_vn: str  # vd 'Seedance 2.0 — Multi-shot time-coded'

    @abstractmethod
    def needs_keyframe_gen(self) -> bool:
        """True nếu cần Phase 2.5 gen ảnh keyframe trước render."""
        raise NotImplementedError

    @abstractmethod
    def max_refs(self) -> int:
        """Số ảnh ref tối đa support."""
        raise NotImplementedError

    @abstractmethod
    def build_prompt(
        self,
        script: Script,
        keyframes: Optional[list[str]] = None,
        audio_urls: Optional[list[str]] = None,
    ) -> VideoJob:
        """Rewrite script + keyframes → VideoJob đúng format model "ăn" được."""
        raise NotImplementedError

    @abstractmethod
    def suitability_score(self, script: Script) -> float:
        """Chấm 0.0-1.0 model fit script đến đâu (cho smart picker)."""
        raise NotImplementedError

    @abstractmethod
    def reasoning_for_script(self, script: Script) -> str:
        """1 câu giải thích vì sao model này fit script (hiện UI badge)."""
        raise NotImplementedError

    # ============================================
    # Common helpers
    # ============================================

    def storyboard_format_label(self) -> str:
        """Label ngắn cho UI hiển thị format Director sẽ output."""
        return "Free-form prose"

    def needs_tts_first(self) -> bool:
        """True nếu phải gen TTS audio TRƯỚC video gen (Wan 2.7 s2v pattern)."""
        return False

    def negative_prompt(self) -> str:
        """Negative prompt per-model — chặn artifact thường gặp.

        Override per-strategy nếu cần custom. Default = base library.
        Industry-tested từ creator chia sẻ + ComfyUI workflow.
        """
        return NEGATIVE_PROMPT_BASE


# ============================================
# NEGATIVE PROMPTS LIBRARY (industry-tested 2026)
# ============================================
# Tổng hợp từ:
#   - Seedance 2.0 community prompts (seedance2prompt.com, seaart.ai)
#   - Vidu Q3 marketing case studies (atlascloud.ai blog)
#   - Wan 2.7 ComfyUI workflows (comfyui-wiki.com, runcomfy.com)
#   - Higgsfield/TopView V2 creator playbooks

NEGATIVE_PROMPT_BASE = (
    "warped face, morphing identity, multiple heads, extra limbs, "
    "AI artifacts, oversaturated, plastic skin, perfect symmetry, "
    "studio lighting, soap opera lighting, fake bokeh, "
    "subtitles, watermark, logo overlay, on-screen text, captions burned in, "
    "low resolution, blurry, jpeg artifacts, banding, frame interpolation glitch"
)

NEGATIVE_PROMPT_TALKING_HEAD = (
    NEGATIVE_PROMPT_BASE + ", "
    "mouth obstructed, hand covering mouth, lip-sync drift, "
    "robotic motion, frozen face, dead eyes, fake smile, "
    "English speech, foreign accent, mumbling"
)

NEGATIVE_PROMPT_SILENT_ASMR = (
    NEGATIVE_PROMPT_BASE + ", "
    "talking, mouth open speaking, dialogue, music heavy, "
    "harsh sound effects, multiple products competing, "
    "shaky cam, unmotivated camera movement"
)

NEGATIVE_PROMPT_MULTI_CHARACTER = (
    NEGATIVE_PROMPT_BASE + ", "
    "merged faces, identity blend between characters, "
    "duplicate characters, wrong outfit swap, character drift, "
    "face morphing between subjects"
)

NEGATIVE_PROMPT_PRODUCT = (
    NEGATIVE_PROMPT_BASE + ", "
    "warped product, deformed packaging, wrong brand label, "
    "Vietnamese text mangled, multiple products visible, "
    "ghost product, transparent product, floating product"
)

NEGATIVE_PROMPT_CINEMATIC = (
    NEGATIVE_PROMPT_BASE + ", "
    "TV commercial look, infomercial style, cheap home video, "
    "harsh ring light, vlog camera, smartphone front camera glare"
)
