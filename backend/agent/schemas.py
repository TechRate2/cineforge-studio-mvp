"""V3 Director Agent — Pydantic schemas.

Trung tâm contract của Director V3:
    - ContinuityBible  : JSON toàn cục character / product / style / audio / setting / constraints
    - Shot             : 1 shot trong shot_list (8-15 shots tổng)
    - StoryboardFrame  : 1 frame để gen ảnh (Seedream/Flux) hoặc user upload
    - EvaluationReport : self-score consistency / viral / cinematic
    - DirectorPlan     : tổng hợp tất cả → response của POST /api/v1/director/plan

Triết lý: KHÔNG hardcode niche / template / tier. Mọi field free-form string —
LLM Director Agent sinh động hoàn toàn dựa vào input user + Continuity Bible.
"""
from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field


# ============================================================
# CONTINUITY BIBLE — global state video
# ============================================================

class Character(BaseModel):
    """Nhân vật xuyên suốt video (face / outfit / voice nhất quán)."""
    id: str = Field(..., description="char_main / char_friend / char_kol ...")
    name: str
    role: str = Field(..., description="protagonist / supporting / cameo / narrator")
    age_apparent: Optional[str] = None
    gender: Optional[str] = None
    face_signature: str = Field(
        "",
        description="1-2 câu mô tả face anchor (race / hair / skin tone / vibe). "
                    "Director Agent dùng để inject vào MỌI prompt scene → identity bền vững.",
    )
    outfit: str = Field("", description="Outfit base — KHÔNG đổi giữa các shot trừ khi có lý do")
    voice_persona: Optional[str] = None
    personality: list[str] = Field(default_factory=list)


class Product(BaseModel):
    """Sản phẩm chính (nếu có) — packaging / color / hero feature."""
    id: str = Field(..., description="prod_main / prod_alt ...")
    name: str
    hero_features: list[str] = Field(default_factory=list)
    packaging_description: str = ""
    color_palette: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)


class VisualStyle(BaseModel):
    """DNA visual nhất quán toàn video — Director V3 áp vào MỌI scene."""
    cinematography: str = Field("", description="vd: cinematic 35mm, handheld UGC, faceless top-down ...")
    color_grading: str = Field("", description="vd: warm filmic / cold teal&orange / pastel airy ...")
    lighting_design: str = Field("", description="vd: golden hour soft / clinical studio / moody key+fill ...")
    camera_language: str = Field("", description="vd: dolly-in reveal, rack focus, whip pan, static lock-off ...")
    film_grain: str = Field("", description="vd: clean digital / 16mm grain / VHS lo-fi ...")
    aspect_ratio: str = "9:16"


class AudioDesign(BaseModel):
    """Audio DNA — mood / tempo / genre / SFX language."""
    mood: str = ""
    tempo: str = Field("", description="slow / mid / fast / build / drop ...")
    music_genre: str = ""
    sfx_emphasis: list[str] = Field(default_factory=list)
    dialogue_style: str = Field("", description="conversational / monologue / VO narration / silent ...")


class Setting(BaseModel):
    location: str = ""
    time_of_day: str = ""
    atmosphere: str = ""


class Constraints(BaseModel):
    """Brand safety + must-have / must-avoid — Director áp vào negative_prompt."""
    must_have: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    brand_safety: list[str] = Field(default_factory=list)


class ReferenceAsset(BaseModel):
    """Universal Reference — ảnh user upload, Director Agent tag role + map vào shot."""
    index: int = Field(..., ge=0, description="0-based vào reference_images[]")
    url: str
    role: Literal[
        "character_anchor",   # ảnh nhân vật chính → giữ face nhất quán
        "product_hero",       # ảnh sản phẩm primary
        "product_detail",     # ảnh sản phẩm detail (macro/angle khác)
        "style_reference",    # ảnh mood/style mẫu
        "environment",        # ảnh setting/location
        "brand_asset",        # logo / packaging close-up
        "secondary_character",
        "unknown",
    ] = "unknown"
    apply_to_shots: list[str] = Field(
        default_factory=list,
        description="List shot_id mà ref này được dùng (Universal Ref binding)",
    )
    notes: str = ""


class ContinuityBible(BaseModel):
    """JSON toàn cục — Director Agent sinh ra 1 lần ở Layer 1.

    Scene Generation Agent (Layer 2) đọc bible này để build prompt mỗi shot
    → identity / style / audio nhất quán toàn video (đặc biệt cho video dài).
    """
    title: str
    logline: str = Field(..., description="1 câu tóm tắt nội dung video (≤140 chars)")
    intent: str = Field(..., description="viral_short / product_demo / brand_story / education / ...")
    duration_s: int
    aspect_ratio: str = "9:16"

    characters: list[Character] = Field(default_factory=list)
    products: list[Product] = Field(default_factory=list)
    visual_style: VisualStyle
    audio_design: AudioDesign
    setting: Setting
    constraints: Constraints

    reference_assets: list[ReferenceAsset] = Field(default_factory=list)

    # Free-form notes Director Agent muốn truyền cho Scene Gen / Eval
    director_notes: str = ""


# ============================================================
# SHOT LIST
# ============================================================

class ShotVisual(BaseModel):
    subject: str
    action: str
    camera_shot: str = Field(..., description="ECU / CU / MS / WS / drone / POV ...")
    camera_movement: str = "static"
    composition: str = ""
    lighting_override: Optional[str] = Field(
        None, description="None = inherit từ bible.visual_style.lighting_design"
    )
    background: str = ""


class ShotAudio(BaseModel):
    dialogue_vn: Optional[str] = None
    caption_on_screen: Optional[str] = None
    sfx: list[str] = Field(default_factory=list)
    music_cue: Optional[str] = None


class ShotContinuity(BaseModel):
    """Glue giữa shot này với bible + shot trước/sau."""
    character_ids: list[str] = Field(default_factory=list)
    product_ids: list[str] = Field(default_factory=list)
    reference_indices: list[int] = Field(
        default_factory=list,
        description="Indices vào reference_assets[] — Reference Chaining mạnh",
    )
    previous_shot_id: Optional[str] = Field(
        None,
        description="Nếu set → render pipeline dùng last_frame của shot này làm i2v input "
                    "(reference chaining — identity 100% giữa shots)",
    )
    style_anchor: str = Field(
        "",
        description="1-line tóm visual style cần giữ (vd: 'warm 35mm grain, soft window light')",
    )


class ShotModelRouting(BaseModel):
    preferred_model: str = Field(
        "auto",
        description="auto / vidu_q3 / vidu_q3_mix / wan_2_7 / seedance_1_5_pro / seedance_2_0 / seedance_2_0_fast",
    )
    reasoning: str = ""


class Shot(BaseModel):
    shot_id: str = Field(..., description="S1 / S2 / S3 ...")
    index: int = Field(..., ge=0)
    start_s: float
    end_s: float
    duration_s: int = Field(..., ge=2, le=20)

    purpose: str = Field(..., description="hook / problem / solution / proof / cta / transition / ...")
    emotion_beat: str = ""

    visual: ShotVisual
    audio: ShotAudio
    continuity: ShotContinuity
    model_routing: ShotModelRouting = Field(default_factory=ShotModelRouting)


# ============================================================
# STORYBOARD GRID
# ============================================================

class StoryboardFrame(BaseModel):
    """1 ảnh storyboard — mô tả prompt để gen bằng Seedream/Flux hoặc user upload."""
    shot_id: str
    prompt: str = Field(
        ...,
        description="Prompt full để feed vào image gen — đã embed character anchor + style",
    )
    image_size: str = "1080*1920"
    user_uploaded_url: Optional[str] = None
    generated_url: Optional[str] = None


# ============================================================
# EVALUATION
# ============================================================

class EvaluationReport(BaseModel):
    """Self-score của Director Plan — Layer 1 reflection trước khi đưa user duyệt."""
    consistency_score: float = Field(..., ge=0, le=10)
    viral_potential_score: float = Field(..., ge=0, le=10)
    cinematic_score: float = Field(..., ge=0, le=10)
    pacing_score: float = Field(..., ge=0, le=10)
    brand_safety_score: float = Field(..., ge=0, le=10)
    overall_score: float = Field(..., ge=0, le=10)

    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)

    red_flags: list[str] = Field(default_factory=list)


# ============================================================
# COST ESTIMATE
# ============================================================

class CostEstimate(BaseModel):
    plan_cost_usd: float = 0.0
    storyboard_gen_cost_usd: float = 0.0
    render_cost_usd: float = 0.0
    audio_cost_usd: float = 0.0
    total_cost_usd: float = 0.0


# ============================================================
# DIRECTOR PLAN — main response
# ============================================================

class DirectorPlan(BaseModel):
    plan_id: str
    created_at: str

    continuity_bible: ContinuityBible
    shot_list: list[Shot]
    storyboard_grid: list[StoryboardFrame] = Field(default_factory=list)
    evaluation: EvaluationReport

    cost_estimate: CostEstimate

    # Debug / observability
    llm_calls_total: int = 0
    elapsed_s: float = 0.0
