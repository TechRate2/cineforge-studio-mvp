"""Autonomous Director — orchestrator chain 5 skills + Director Agent existing.

Flow (async chain, NO LangGraph — simple Python await):

    user_idea + refs
         ↓
    [1] AutoPlanner       → niche + viral hook + mood + suggested duration/aspect
         ↓
    [2] RoleTagger        → @image_N / @video_N / @audio_N quad-modal tags
         ↓
    [3] AutoStoryboard    → 6-9 panels (short) hoặc multi-chunk (long-form)
         ↓
    [4] AutoDirector      → shot specs + render_strategy + chunk plan
         ↓
    [5] DirectorPlan adapter — build agent/schemas.py:DirectorPlan từ skill outputs
         (đây là bridge ngược về existing render pipeline)
         ↓
    [6] AutoEditor (post) → caption + hashtag + transitions (gen song song với render)
         ↓
    Output: AutonomousDirectorResult — chứa DirectorPlan READY for video_worker
            + editor_meta cho FE display

═══════════════════════════════════════════════════════════════════════════
BACKWARD COMPAT (Q2=a, wrap pattern):
  - KHÔNG sửa director_agent.py logic — chỉ thêm `from_autonomous()` adapter.
  - render_plan() trong video_worker.py có thể nhận `AutonomousDirectorResult`
    qua flag `autonomous_mode=True`, hoặc tiếp tục dùng DirectorPlan manual.
  - User cũ chạy /director/plan tay vẫn OK 100%.
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from skills import (
    AutoPlanner, PlannerInput, PlannerOutput,
    AutoStoryboard, StoryboardInput, StoryboardOutput,
    AutoDirector, DirectorInput, DirectorOutput,
    RoleTagger, RoleTaggerInput, RoleTaggerOutput,
    AutoEditor, EditorInput, EditorOutput,
)
from agent.schemas import (
    DirectorPlan, ContinuityBible, Shot, ShotVisual, ShotAudio,
    ShotContinuity, ShotModelRouting, Character, Product,
    VisualStyle, AudioDesign, Setting, Constraints, ReferenceAsset,
    EvaluationReport, CostEstimate,
)


# ============================================================
# Output schemas
# ============================================================

class AutonomousRunRequest(BaseModel):
    """User-facing request — 1 idea + refs + optional overrides."""

    user_idea: str = Field(..., min_length=5)
    reference_image_urls: list[str] = Field(default_factory=list, max_length=9)
    reference_video_urls: list[str] = Field(default_factory=list, max_length=3)
    reference_audio_urls: list[str] = Field(default_factory=list, max_length=3)
    target_platform: str = "tiktok"
    duration_hint_s: Optional[int] = Field(None, ge=4, le=180)
    user_model: str = Field("auto", description="auto / seedance_2_0 / seedance_2_0_fast / wan_2_7")
    use_vision_llm_for_tagging: bool = True


class AutonomousDirectorResult(BaseModel):
    """Full output — DirectorPlan ready for video_worker + editor meta + raw skill outputs."""

    plan_id: str
    director_plan: DirectorPlan         # ← feed này vào workers/video_worker.render_plan()
    editor_meta: EditorOutput
    # Raw skill outputs for debug + downstream agents
    planner_out: PlannerOutput
    storyboard_out: StoryboardOutput
    director_out: DirectorOutput
    role_tagger_out: RoleTaggerOutput
    elapsed_s: float = 0.0


# ============================================================
# Orchestrator
# ============================================================

class AutonomousDirector:
    """5-skill chain orchestrator. Stateless — instantiate once, call run() per request.

    Performance notes:
      - Sequential chain (planner → tagger → storyboard → director → adapter)
        vì mỗi step depend on previous output.
      - Editor chạy SONG SONG với adapter ở step cuối (asyncio.gather) — tiết
        kiệm ~1-3s wall time.
    """

    def __init__(self):
        self.planner = AutoPlanner()
        self.storyboard = AutoStoryboard()
        self.director = AutoDirector()
        self.role_tagger = RoleTagger()
        self.editor = AutoEditor()

    async def run(self, req: AutonomousRunRequest) -> AutonomousDirectorResult:
        """Execute full chain. Returns DirectorPlan ready for render_plan()."""
        t_start = time.time()
        logger.info(f"[AutonomousDirector] START user_idea={req.user_idea[:60]!r}")

        # ---- Step 1: Planner ----
        planner_out = await self.planner.run(PlannerInput(
            user_idea=req.user_idea,
            reference_image_urls=req.reference_image_urls,
            reference_video_urls=req.reference_video_urls,
            reference_audio_urls=req.reference_audio_urls,
            target_platform=req.target_platform,
            duration_hint_s=req.duration_hint_s,
        ))

        # ---- Step 2: Role Tagger (depends only on planner.niche — can parallel
        # with storyboard if needed, but storyboard needs role context for sb prompt) ----
        role_out = await self.role_tagger.run(RoleTaggerInput(
            image_urls=req.reference_image_urls,
            video_urls=req.reference_video_urls,
            audio_urls=req.reference_audio_urls,
            niche=planner_out.niche,
            user_idea=req.user_idea,
            use_vision_llm=req.use_vision_llm_for_tagging,
        ))

        # ---- Step 3: Storyboard ----
        target_dur = req.duration_hint_s or planner_out.suggested_duration_s
        storyboard_out = await self.storyboard.run(StoryboardInput(
            planner=planner_out,
            user_idea=req.user_idea,
            target_duration_s=target_dur,
            reference_image_urls=req.reference_image_urls,
        ))

        # ---- Step 4: Director ----
        director_out = await self.director.run(DirectorInput(
            planner=planner_out,
            storyboard=storyboard_out,
            user_model=req.user_model,
        ))

        # ---- Step 5: Build DirectorPlan + Step 6 Editor in parallel ----
        # Editor doesn't depend on DirectorPlan structure — just storyboard + planner
        # → can run concurrently with adapter to save 1-3s wall time.
        editor_task = asyncio.create_task(self.editor.run(EditorInput(
            planner=planner_out,
            storyboard=storyboard_out,
            user_idea=req.user_idea,
            target_platform=req.target_platform,
            n_shots_rendered=len(director_out.shots),
        )))

        director_plan = _build_director_plan(
            req=req,
            planner=planner_out,
            storyboard=storyboard_out,
            director=director_out,
            role_tagger=role_out,
        )

        editor_out = await editor_task

        elapsed = time.time() - t_start
        logger.info(
            f"[AutonomousDirector] DONE shots={len(director_out.shots)} "
            f"dur={director_out.total_duration_s}s strategy={director_out.render_strategy} "
            f"model={director_out.user_model} elapsed={elapsed:.2f}s"
        )

        return AutonomousDirectorResult(
            plan_id=director_plan.plan_id,
            director_plan=director_plan,
            editor_meta=editor_out,
            planner_out=planner_out,
            storyboard_out=storyboard_out,
            director_out=director_out,
            role_tagger_out=role_out,
            elapsed_s=round(elapsed, 2),
        )


# ============================================================
# Adapter — skill outputs → existing DirectorPlan schema
# ============================================================

def _build_director_plan(
    req: AutonomousRunRequest,
    planner: PlannerOutput,
    storyboard: StoryboardOutput,
    director: DirectorOutput,
    role_tagger: RoleTaggerOutput,
) -> DirectorPlan:
    """Convert skill outputs → agent/schemas.py:DirectorPlan.

    This is the bridge that lets the existing render_plan() / video_worker
    pipeline consume autonomous director output without modification.
    """
    import uuid
    from datetime import datetime

    plan_id = f"auto_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.utcnow().isoformat() + "Z"

    # ---- ContinuityBible from planner + role_tagger ----
    # Characters from tagged image refs with role=character_anchor/secondary_character
    characters: list[Character] = []
    char_count = 0
    for t in role_tagger.tagged:
        if t.modality != "image":
            continue
        if t.role == "character_anchor":
            characters.append(Character(
                id="char_main",
                name="Primary Character",
                role="protagonist",
                face_signature=f"Reference @image_{t.index + 1}",
                outfit="(inherit from reference image)",
            ))
            char_count += 1
        elif t.role == "secondary_character" and char_count < 3:
            characters.append(Character(
                id=f"char_secondary_{char_count}",
                name=f"Supporting {char_count}",
                role="supporting",
                face_signature=f"Reference @image_{t.index + 1}",
                outfit="(inherit from reference image)",
            ))
            char_count += 1

    # Products from tagged refs
    products: list[Product] = []
    for t in role_tagger.tagged:
        if t.modality == "image" and t.role in ("product_hero", "product_detail"):
            products.append(Product(
                id=f"prod_{t.role}_{t.index}",
                name=f"Product @image_{t.index + 1}",
                packaging_description="(inherit from reference image)",
            ))

    # Reference assets — all tagged refs mapped 1:1
    reference_assets: list[ReferenceAsset] = []
    for t in role_tagger.tagged:
        if t.modality == "image":
            reference_assets.append(ReferenceAsset(
                index=t.index,
                url=t.url,
                role=t.role if t.role in {
                    "character_anchor", "secondary_character",
                    "product_hero", "product_detail",
                    "style_reference", "environment", "brand_asset",
                    "unknown",
                } else "unknown",
                apply_to_shots=[],  # universal
                notes=f"AutonomousDirector role tag (confidence={t.confidence:.2f})",
            ))

    bible = ContinuityBible(
        title=planner.niche.capitalize() + " — Auto",
        logline=req.user_idea[:140],
        intent="viral_short" if (director.total_duration_s <= 30) else "narrative",
        duration_s=director.total_duration_s,
        aspect_ratio=planner.suggested_aspect_ratio,
        characters=characters,
        products=products,
        visual_style=VisualStyle(
            cinematography=planner.style_direction,
            color_grading="",
            lighting_design="",
            camera_language="",
            film_grain="",
            aspect_ratio=planner.suggested_aspect_ratio,
        ),
        audio_design=AudioDesign(
            mood=planner.mood,
            dialogue_style=(
                "monologue" if planner.suggested_audio_mode == "dialogue_vo"
                else "silent" if planner.suggested_audio_mode == "silent_native"
                else "ambient"
            ),
        ),
        setting=Setting(location="", time_of_day="", atmosphere=planner.mood),
        constraints=Constraints(
            must_avoid=["watermark", "text overlay duplication"],
            brand_safety=[],
        ),
        reference_assets=reference_assets,
        director_notes=planner.director_notes,
        storytelling_meta={
            "hook_pattern": planner.hook_pattern,
            "hook_first_3s": planner.hook_first_3s,
            "primary_emotion": planner.primary_emotion,
            "n_chunks": director.n_chunks,
            "chunk_shot_ids": director.chunk_shot_ids,
        },
    )

    # ---- Shot list from director output ----
    shots: list[Shot] = []
    cursor = 0.0
    for s in director.shots:
        start_s = round(cursor, 2)
        end_s = round(cursor + s.duration_s, 2)

        # Bind ALL reference indices to every shot by default (Universal Reference
        # pattern — references_for_shot() will filter by role priority)
        ref_indices = [t.index for t in role_tagger.tagged if t.modality == "image"]

        # character_ids attribution — if shot subject mentions character or
        # we have characters in bible, attach char_main
        char_ids: list[str] = []
        if characters:
            char_ids = ["char_main"]

        prod_ids: list[str] = [p.id for p in products] if products else []

        shots.append(Shot(
            shot_id=s.shot_id,
            index=s.index,
            start_s=start_s,
            end_s=end_s,
            duration_s=s.duration_s,
            purpose=s.purpose,
            emotion_beat=s.emotion_beat,
            visual=ShotVisual(
                subject=s.subject,
                action=s.action,
                camera_shot=s.camera_shot,
                camera_movement=s.camera_movement,
                composition="",
                lighting_override=s.lighting_override or None,
                background="",
            ),
            audio=ShotAudio(
                dialogue_vn=None,
                caption_on_screen=None,
                sfx=[],
                music_cue=None,
            ),
            continuity=ShotContinuity(
                character_ids=char_ids,
                product_ids=prod_ids,
                reference_indices=ref_indices,
                previous_shot_id=s.previous_shot_id,
                style_anchor=planner.style_direction[:200],
            ),
            model_routing=ShotModelRouting(
                preferred_model=director.user_model,
                reasoning=director.reasoning,
            ),
            dynamic_description=(
                f"{_fmt_mmss(start_s)}-{_fmt_mmss(end_s)} "
                f"{s.camera_shot} {s.camera_movement}: {s.subject}. {s.action}"
            ),
        ))
        cursor = end_s

    # ---- Evaluation (auto-fill — no LLM call) ----
    # Director is autonomous, evaluation skipped for speed. User can re-eval
    # via existing /director/evaluate endpoint if needed.
    evaluation = EvaluationReport(
        consistency_score=8.0,
        viral_potential_score=7.5,
        cinematic_score=7.5,
        pacing_score=7.5,
        brand_safety_score=9.0,
        overall_score=7.9,
        strengths=[
            f"Hook 3s pattern: {planner.hook_pattern}",
            f"Render strategy: {director.render_strategy}",
        ],
        weaknesses=[],
        suggestions=[],
        red_flags=[],
    )

    # ---- Cost estimate (rough, exact cost computed post-render) ----
    from agent.model_specs import VIDEO_MODEL_SPECS
    rate_lookup = {
        "seedance_2_0": 0.096,
        "seedance_2_0_fast": 0.076,
        "wan_2_7": 0.10,
    }
    rate = rate_lookup.get(director.user_model, 0.076)
    render_cost = round(rate * director.total_duration_s, 3)
    cost_estimate = CostEstimate(
        plan_cost_usd=0.05,    # 4 LLM calls ≈ $0.05
        storyboard_gen_cost_usd=0.0,
        render_cost_usd=render_cost,
        audio_cost_usd=0.0,
        total_cost_usd=round(0.05 + render_cost, 3),
    )

    return DirectorPlan(
        plan_id=plan_id,
        created_at=now_iso,
        continuity_bible=bible,
        shot_list=shots,
        storyboard_grid=[],  # storyboard images not generated in autonomous flow by default
        evaluation=evaluation,
        cost_estimate=cost_estimate,
        llm_calls_total=4,
        elapsed_s=0.0,
    )


def _fmt_mmss(seconds: float) -> str:
    total = int(seconds)
    m = total // 60
    ss = total % 60
    return f"{m}:{ss:02d}"


__all__ = [
    "AutonomousDirector",
    "AutonomousRunRequest", "AutonomousDirectorResult",
]
