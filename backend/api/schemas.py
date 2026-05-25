"""Pydantic schemas cho request/response."""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============================================
# AUDIO PLAN — V5.15.7 H2 strict schema (was: Optional[dict])
# ============================================

class AudioPlan(BaseModel):
    """Strict schema for the audio_plan body field on /generate + /plan-and-render.

    Previously `Optional[dict]` accepting any shape — Pydantic now rejects
    typos (e.g. "dialogue_v0" with zero, mode as number) at 400 instead of
    letting them slip through to the worker which would treat them as
    "no audio mode" and silently render a silent shot.

    Semantics:
      - mode=None or omitted          → no dialogue track; worker leaves
                                        audio plan alone (legacy behavior).
      - mode="silent_native"          → vendor's native ambient/music only.
      - mode="dialogue_vo"            → worker auto-pre-renders TTS from
                                        shot.audio.dialogue_vn IF
                                        voice_audio_url AND driven_audio_urls
                                        are both empty.
      - mode="asmr_macro"             → SFX-driven (e.g. food close-ups).

    `driven_audio_urls`: per-shot TTS map (V5.2 — Wan 2.7 lip-sync path).
    Worker sets this after auto-TTS; clients usually leave it None.
    """
    model_config = ConfigDict(extra="forbid")  # reject typo keys with 422

    mode: Optional[Literal["silent_native", "dialogue_vo", "asmr_macro"]] = None
    voice_audio_url: Optional[str] = Field(
        None,
        max_length=2000,
        description="Single voiceover URL applied to whole video (legacy single-track path).",
    )
    sfx_audio_url: Optional[str] = Field(None, max_length=2000)
    caption_text_vn: Optional[str] = Field(None, max_length=1000)
    bgm_path: Optional[str] = Field(
        None, max_length=500,
        description="Local path on the server to a BGM track to mix at low volume.",
    )
    driven_audio_urls: Optional[dict[str, str]] = Field(
        None,
        description="Per-shot TTS URLs {shot_id: https_url}. Set by worker after auto-TTS; "
                    "clients usually omit. Each value must be a URL string ≤ 2000 chars.",
    )


# ============================================
# REQUEST SCHEMAS
# ============================================

class ProductInput(BaseModel):
    """User input về sản phẩm."""
    url: Optional[str] = Field(None, description="Link Shopee/Lazada/Tiki")
    text_description: Optional[str] = Field(None, description="Mô tả text nếu không có link")
    image_urls: Optional[list[str]] = Field(default_factory=list, description="Ảnh sản phẩm")


class VideoSettings(BaseModel):
    """Settings cho video gen.

    V6 — 3 user-facing models (Seedance 2.0 core + Wan 2.7 fallback).
    """
    audio_mode: Literal["silent_native", "dialogue_vo", "asmr_macro"] = "silent_native"
    # V6: "auto" = model_picker auto-selects between seedance_2_0[_fast] and wan_2_7
    model: Literal[
        "auto",
        "seedance_2_0",
        "seedance_2_0_fast",
        "wan_2_7",
    ] = "auto"
    duration_s: int = Field(15, ge=3, le=60, description="3-60s, cap thực tế per-model enforce sau")
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    # Per-model resolution enum (mỗi AtlasCloud model có set riêng: 480p/540p/720p/720P/1080p/1080P/SR variants).
    # Loose string thay vì Literal — model_specs.py validate per-model trong build_payload.
    resolution: str = "720p"
    # NEW V3.1 — num_shots cho Seedance 2.0/Fast (Topview pattern user override).
    # None = Director tự quyết theo duration + style. 1-5 = user ép số shot.
    # Chỉ áp dụng cho model multi-shot native (seedance_2_0, seedance_2_0_fast).
    num_shots: Optional[int] = Field(
        None, ge=1, le=5,
        description="Override số shot cho multi-shot model (Seedance 2.0/Fast). None = Director tự quyết.",
    )
    setting_location: Optional[str] = Field(None, description="Override default location")
    voice_persona: Optional[str] = Field(None, description="Voice preset alias hoặc voice_id")
    seed: Optional[int] = Field(None, description="Reproducibility seed (optional)")


class ApprovedScript(BaseModel):
    """Script đã được user approve trong ProposalModal (Phase 2)."""
    variant_id: str
    hook_text_vn: str
    body_text_vn: str = ""  # concat segments
    cta_text_vn: str
    framework: Optional[str] = None
    total_duration_s: Optional[int] = None


class ApprovedScene(BaseModel):
    """1 scene đã edit + approved trong SceneEditorModal (Phase 2 NEW v3 — TopView V2 pattern).

    Mỗi scene = 1 shot trong video. User có thể edit prompt/duration/refs trước khi render.
    Backend Phase 3 sẽ render TỪNG scene song song rồi FFmpeg concat thành MP4 final.
    """
    scene_id: str
    prompt: str  # full prompt text + [Image N] mentions inline
    duration_s: int = Field(..., ge=2, le=20)
    image_refs: list[int] = Field(default_factory=list, description="1-based indices vào reference_images[]")
    extends_from: Optional[str] = Field(None, description="scene_id của scene trước (chain continuity)")
    purpose: Optional[str] = Field(None, description="hook / problem / solution / proof / cta")
    caption: Optional[str] = Field(None, description="Caption on-screen overlay")
    dialogue: Optional[str] = Field(None, description="Dialogue VN cho voiceover (nếu có)")


class CreateJobRequest(BaseModel):
    """Request tạo job UGC video — V2 LOGIC: AI tự pick template.

    Phase 2-3 wiring (NEW):
        Khi user approve ProposalModal, frontend pass:
            - proposal_id: track lại proposal đã gen
            - approved_script: full hook+body+CTA đã chọn
            - avatar_id: avatar đã pick (từ Casting Director)
        → Generator sẽ override AI auto-pick và DÙNG script approved.
    """
    product_input: ProductInput
    reference_images: list[str] = Field(
        default_factory=list,
        max_length=12,
        description="1-12 ảnh tham chiếu (base64 data URL hoặc external URL). Count tùy model."
    )
    settings: VideoSettings

    # ===== Phase 2 → Phase 3 wire (Director Agent approval) =====
    proposal_id: Optional[str] = Field(None, description="UUID từ /propose endpoint (tracking)")
    approved_script: Optional[ApprovedScript] = Field(
        None,
        description="Script user đã pick từ ProposalModal — override AI auto-pick"
    )
    approved_scenes: Optional[list[ApprovedScene]] = Field(
        None,
        description=(
            "NEW v3 (TopView V2 Multi-Scene pattern): list scenes editable user đã chốt "
            "từ SceneEditorModal. Khi có → backend render TỪNG scene song song theo prompt+"
            "duration user edit + FFmpeg concat. Override approved_script (vì scenes đã "
            "embed prompt thay vì script hook/body/cta riêng)."
        ),
    )
    reference_mapping: Optional[dict] = Field(
        None,
        description="ReferenceMapping JSON từ ReferenceAnalyzer (Phase 2) — pass cho generator"
    )
    approved_keyframes: Optional[list[dict]] = Field(
        None,
        description=(
            "Keyframes user đã duyệt Phase 2.5 — list dict {shot_id, image_url, "
            "purpose, duration_s, dialogue_vn, ...}. Khi có, render pipeline dùng "
            "image-to-video (i2v) thay text-only — identity consistency 100%."
        ),
    )
    # ===== V3 Model-Aware wire (Phase 2 cinematic outputs → Phase 3 strategy) =====
    # Khi có 2 field này → render_pipeline dùng strategy.build_prompt() pure function
    # thay vì LLM Generator. Format prompt đúng model spec (time-coded / inline-named / ...).
    approved_shots: Optional[list[dict]] = Field(
        None,
        description=(
            "Shots MCSLA từ cinematic_brief.shots (Phase 2 Director). Mỗi shot: "
            "{shot_id, duration_s, purpose, C_camera, S_subject, L_lighting, A_action, "
            "dialogue_vn, caption_on_screen}. Cần cho V3 strategy.build_prompt()."
        ),
    )
    approved_character_sheet: Optional[dict] = Field(
        None,
        description=(
            "character_sheet từ cinematic_brief (Phase 2 Director). Fields: "
            "{id, name_vn, age_apparent, gender, face, outfit_top, outfit_bottom, ...}. "
            "Strategy dùng để inject character descr inline vào prompt."
        ),
    )

    # ===== Legacy / advanced override =====
    template_id: Optional[str] = Field(None, description="Override AI auto-pick (optional)")
    avatar_id: Optional[str] = Field(None, description="Backward compat (anh không dùng preset avatar)")
    avatar_image_url: Optional[str] = Field(None, description="Backward compat")


# ============================================
# RESPONSE SCHEMAS
# ============================================

class JobStatus(BaseModel):
    """Status của job (polling endpoint)."""
    job_id: UUID
    status: Literal[
        "pending",
        "scraping",
        "analyzing",
        "generating",
        "rendering",
        "voicing",
        "sfx",
        "assembling",
        "uploading",
        "done",
        "failed",
    ]
    progress: int = Field(0, ge=0, le=100)
    current_step: Optional[str] = None
    estimated_remaining_s: Optional[int] = None
    output_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_s: Optional[int] = None
    cost_actual_usd: Optional[float] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class JobCreatedResponse(BaseModel):
    """Response khi tạo job mới."""
    job_id: UUID
    status: str = "pending"
    estimated_duration_s: int = Field(..., description="Estimate render time seconds")
    estimated_cost_usd: float
    polling_url: str


class Template(BaseModel):
    """Template skeleton."""
    id: str
    name_vn: str
    name_en: str
    category: str
    tier: Literal["S", "A", "B"]
    default_duration_s: int
    default_audio_mode: str
    aspect_ratio: str
    thumbnail_url: Optional[str] = None
    sample_video_url: Optional[str] = None
    use_cases_vn: list[str] = []


class Avatar(BaseModel):
    """Avatar preset hoặc custom."""
    id: str
    name: str
    ethnicity: str
    age: int
    gender: str
    style: str
    vibe: str
    image_url: str
    is_preset: bool = True
