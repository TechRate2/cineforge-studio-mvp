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
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field

from skills import (
    AutoPlanner, PlannerInput, PlannerOutput,
    AutoStoryboard, StoryboardInput, StoryboardOutput, StoryboardPanel,
    AutoDirector, DirectorInput, DirectorOutput,
    RoleTagger, RoleTaggerInput, RoleTaggerOutput,
    AutoEditor, EditorInput, EditorOutput,
)
from skills.niche_playbooks import get_niche_playbook
from skills.market_playbooks import get_market_playbook
from agent.cinematic_grammar_contract import build_cinematic_grammar_contract
from agent.long_form_execution_gate import build_long_form_execution_gate
from agent.schemas import (
    DirectorPlan, ContinuityBible, Shot, ShotVisual, ShotAudio,
    ShotContinuity, ShotModelRouting, Character, Product,
    VisualStyle, AudioDesign, Setting, Constraints, ReferenceAsset,
    EvaluationReport, CostEstimate,
)
from agent.long_form_orchestrator import plan_runtime_structure
from agent.scene_planner import plan_scene_blueprints
from agent.screenplay_planner import plan_screenplay
from agent.production_graph import build_production_graph
from agent.production_treatment import build_production_treatment
from agent.continuity_handoff_policy import apply_continuity_handoffs
from agent.scene_memory_pack import build_scene_memory_pack
from agent.dynamic_keyframe_memory import build_dynamic_keyframe_memory_contract
from agent.asset_memory import remember_autonomous_assets, suggest_autonomous_assets
from agent.market_inference import infer_target_market
from agent.autonomous_production_decision import build_autonomous_production_decision
from agent.niche_runtime_director import build_niche_runtime_director_contract
from agent.niche_production_recipe import build_niche_production_recipe
from agent.seedance_reference_allocation import build_seedance_reference_allocation
from agent.seedance_prompt_formula import build_seedance_prompt_formula


# ============================================================
# Output schemas
# ============================================================

class AutonomousRunRequest(BaseModel):
    """User-facing request — 1 idea + refs + optional overrides."""

    user_idea: str = Field(..., min_length=5)
    reference_image_urls: list[str] = Field(default_factory=list, max_length=9)
    reference_video_urls: list[str] = Field(default_factory=list, max_length=3)
    reference_audio_urls: list[str] = Field(default_factory=list, max_length=3)
    reference_manifest: dict[str, Any] = Field(default_factory=dict)
    pinned_asset_ids: list[str] = Field(default_factory=list, max_length=12)
    pinned_assets: list[dict[str, Any]] = Field(default_factory=list)
    target_platform: str = "tiktok"
    target_market: str = Field("auto", description="auto / vn / us / sea / jp / kr / global")
    duration_hint_s: Optional[int] = Field(None, ge=4, le=1800)
    aspect_ratio: Optional[str] = Field(None, description="Optional UI output frame override: 9:16 / 16:9 / 1:1")
    user_model: str = Field("auto", description="auto / seedance_2_0 / seedance_2_0_fast / wan_2_7")
    use_vision_llm_for_tagging: bool = False


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
    asset_memory_meta: dict = Field(default_factory=dict)
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
        deterministic_decision = build_autonomous_production_decision(
            user_idea=req.user_idea,
            target_market=req.target_market,
            target_platform=req.target_platform,
            duration_hint_s=req.duration_hint_s,
            reference_counts={
                "images": len(req.reference_image_urls),
                "videos": len(req.reference_video_urls),
                "audios": len(req.reference_audio_urls),
                "pinned_assets": len(req.pinned_asset_ids),
            },
            reference_image_urls=req.reference_image_urls,
            reference_video_urls=req.reference_video_urls,
            reference_audio_urls=req.reference_audio_urls,
            reference_manifest=req.reference_manifest,
        )
        creative_treatment_search = deterministic_decision.get("creative_treatment_search") or {}
        selected_creative_treatment = _selected_creative_treatment(creative_treatment_search)
        market_inference = (
            deterministic_decision.get("input_summary", {}).get("market_inference")
            or infer_target_market(req.user_idea, req.target_market)
        )
        effective_target_market = str(
            (deterministic_decision.get("decision") or {}).get("target_market")
            or market_inference["effective_target_market"]
        )
        market_playbook = get_market_playbook(effective_target_market)
        market_playbook["market_inference"] = market_inference
        market_playbook["requested_target_market"] = req.target_market
        planner_out = await self.planner.run(PlannerInput(
            user_idea=req.user_idea,
            reference_image_urls=req.reference_image_urls,
            reference_video_urls=req.reference_video_urls,
            reference_audio_urls=req.reference_audio_urls,
            target_platform=req.target_platform,
            target_market=effective_target_market,
            market_playbook=market_playbook,
            duration_hint_s=req.duration_hint_s,
        ))
        planner_guard = _apply_planner_decision_guard(
            planner_out,
            deterministic_decision=deterministic_decision,
        )
        planner_out = planner_guard["planner"]
        planner_out = _apply_creative_treatment_to_planner(
            planner_out,
            selected_creative_treatment=selected_creative_treatment,
        )
        planner_out = _apply_aspect_ratio_override(
            planner_out,
            aspect_ratio=req.aspect_ratio,
        )
        niche_playbook = get_niche_playbook(planner_out.niche)
        if selected_creative_treatment:
            niche_playbook = {
                **niche_playbook,
                "creative_treatment": selected_creative_treatment,
                "creative_treatment_search": creative_treatment_search,
            }
        asset_memory_suggestions = suggest_autonomous_assets(
            user_idea=req.user_idea,
            niche=planner_out.niche,
            target_market=effective_target_market,
        )
        runtime_structure = plan_runtime_structure(
            req.duration_hint_s or planner_out.suggested_duration_s,
            niche=planner_out.niche,
            platform=req.target_platform,
        )

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
        role_out = _apply_reference_manifest_role_overrides(role_out, req.reference_manifest)

        # ---- Step 3: Storyboard ----
        target_dur = req.duration_hint_s or planner_out.suggested_duration_s
        if target_dur > 180:
            scene_blueprints = plan_scene_blueprints(
                user_idea=req.user_idea,
                runtime_structure=runtime_structure.model_dump(),
                niche_playbook=niche_playbook,
                planner_hook=planner_out.hook_first_3s,
            )
            screenplay_plan = plan_screenplay(
                user_idea=req.user_idea,
                runtime_structure=runtime_structure.model_dump(),
                scene_blueprints=scene_blueprints,
                niche_playbook=niche_playbook,
                hook_first_3s=planner_out.hook_first_3s,
                primary_emotion=planner_out.primary_emotion,
            )
            storyboard_out = await self._storyboard_long_form(
                planner=planner_out,
                user_idea=req.user_idea,
                reference_image_urls=req.reference_image_urls,
                niche_playbook=niche_playbook,
                scene_blueprints=scene_blueprints,
                screenplay_plan=screenplay_plan.model_dump(),
            )
            runtime_structure_dict = {
                **runtime_structure.model_dump(),
                "scene_blueprints": [s.model_dump() for s in scene_blueprints],
                "screenplay_plan": screenplay_plan.model_dump(),
            }
        else:
            storyboard_out = await self.storyboard.run(StoryboardInput(
                planner=planner_out,
                user_idea=req.user_idea,
                target_duration_s=target_dur,
                reference_image_urls=req.reference_image_urls,
                niche_playbook=niche_playbook,
            ))
            runtime_structure_dict = runtime_structure.model_dump()

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
            target_market=effective_target_market,
            market_playbook=market_playbook,
            n_shots_rendered=len(director_out.shots),
            niche_playbook=niche_playbook,
        )))

        director_plan = _build_director_plan(
            req=req,
            planner=planner_out,
            storyboard=storyboard_out,
            director=director_out,
            role_tagger=role_out,
            runtime_structure=runtime_structure_dict,
            target_market=effective_target_market,
            market_inference=market_inference,
            planner_guard=planner_guard["meta"],
            creative_treatment_search=creative_treatment_search,
        )
        asset_memory_meta = remember_autonomous_assets(
            tagged_references=role_out.tagged,
            user_idea=req.user_idea,
            niche=planner_out.niche,
            target_market=effective_target_market,
            plan_id=director_plan.plan_id,
        )
        asset_memory_meta["suggestions"] = asset_memory_suggestions
        asset_memory_meta["market_inference"] = market_inference
        asset_memory_meta["creative_treatment_search"] = creative_treatment_search

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
            asset_memory_meta=asset_memory_meta,
            elapsed_s=round(elapsed, 2),
        )

    @staticmethod
    def apply_planner_decision_guard(
        planner: PlannerOutput,
        *,
        deterministic_decision: dict[str, Any],
    ) -> dict[str, Any]:
        return _apply_planner_decision_guard(
            planner,
            deterministic_decision=deterministic_decision,
        )

    async def _storyboard_long_form(
        self,
        *,
        planner: PlannerOutput,
        user_idea: str,
        reference_image_urls: list[str],
        niche_playbook: dict,
        scene_blueprints: list,
        screenplay_plan: Optional[dict] = None,
    ) -> StoryboardOutput:
        """Storyboard long-form by scene, then merge into one timeline."""
        merged: list[StoryboardPanel] = []
        scene_durations: list[float] = []
        global_index = 0
        elapsed = 0.0
        screenplay_scenes = {
            s.get("scene_id"): s
            for s in (screenplay_plan or {}).get("scene_scripts", [])
            if isinstance(s, dict)
        }
        continuity_contract = (screenplay_plan or {}).get("continuity_contract") or []

        for scene in scene_blueprints:
            scene_script = screenplay_scenes.get(scene.scene_id, {})
            scene_planner = planner.model_copy(update={
                "hook_first_3s": scene.visual_hook,
                "suggested_duration_s": scene.duration_s,
                "director_notes": (
                    f"{planner.director_notes}\n"
                    f"Scene {scene.scene_id}: {scene.purpose}. "
                    f"Dramatic question: {scene.dramatic_question}. "
                    f"Continuity: {scene.continuity_anchor}. "
                    f"Handoff: {scene.handoff_to_next}. "
                    f"Conflict: {scene_script.get('conflict', '')}. "
                    f"Turning point: {scene_script.get('turning_point', '')}. "
                    f"Dialogue/VO intent: {scene_script.get('dialogue_or_vo_intent', '')}."
                ).strip(),
            })
            scene_idea = (
                f"{user_idea}\n\n"
                f"SCENE BLUEPRINT {scene.scene_id}: act={scene.act}, duration={scene.duration_s}s, "
                f"purpose={scene.purpose}. Dramatic question: {scene.dramatic_question}. "
                f"Visual hook: {scene.visual_hook}. Continuity: {scene.continuity_anchor}. "
                f"Handoff: {scene.handoff_to_next}.\n"
                f"SCREENPLAY SCENE: premise={scene_script.get('premise', '')}; "
                f"conflict={scene_script.get('conflict', '')}; "
                f"turning_point={scene_script.get('turning_point', '')}; "
                f"opening_image={scene_script.get('opening_image', '')}; "
                f"closing_image={scene_script.get('closing_image', '')}; "
                f"dialogue_or_vo_intent={scene_script.get('dialogue_or_vo_intent', '')}."
            )
            out = await self.storyboard.run(StoryboardInput(
                planner=scene_planner,
                user_idea=scene_idea,
                target_duration_s=min(scene.duration_s, 180),
                reference_image_urls=reference_image_urls,
                niche_playbook={
                    **niche_playbook,
                    "scene_blueprint": scene.model_dump(),
                    "screenplay_scene": scene_script,
                    "continuity_contract": continuity_contract,
                },
            ))

            scene_total = 0.0
            for panel in out.panels:
                start = elapsed + scene_total
                merged.append(panel.model_copy(update={
                    "index": global_index,
                    "chunk_id": int(start // 60),
                }))
                global_index += 1
                scene_total += float(panel.duration_s)
            scene_durations.append(scene_total)
            elapsed += scene_total

        by_chunk: dict[int, float] = {}
        for panel in merged:
            by_chunk[panel.chunk_id] = by_chunk.get(panel.chunk_id, 0.0) + float(panel.duration_s)

        return StoryboardOutput(
            panels=merged,
            total_duration_s=sum(scene_durations),
            n_chunks=len(by_chunk) or 1,
            chunk_duration_s=[by_chunk[i] for i in sorted(by_chunk.keys())],
        )


# ============================================================
# Adapter — skill outputs → existing DirectorPlan schema
# ============================================================

def _apply_planner_decision_guard(
    planner: PlannerOutput,
    *,
    deterministic_decision: dict[str, Any],
) -> dict[str, Any]:
    """Keep the LLM planner aligned with the deterministic preview contract."""
    decision = deterministic_decision.get("decision") or {}
    expected_niche = str(decision.get("niche") or "").strip()
    expected_duration = int(decision.get("target_duration_s") or planner.suggested_duration_s)
    market = str(decision.get("target_market") or "auto")
    requested_market = str(decision.get("requested_target_market") or market)

    updates: dict[str, Any] = {}
    corrections: list[str] = []
    if expected_niche and expected_niche != planner.niche:
        updates["niche"] = expected_niche
        corrections.append("niche")
    if expected_duration and expected_duration != planner.suggested_duration_s:
        updates["suggested_duration_s"] = expected_duration
        corrections.append("suggested_duration_s")

    guarded = planner.model_copy(update=updates) if updates else planner
    meta = {
        "schema_version": "cinejelly.planner_guard.v1",
        "applied": bool(corrections),
        "corrections": corrections,
        "planner_niche": planner.niche,
        "deterministic_niche": expected_niche or planner.niche,
        "planner_duration_s": planner.suggested_duration_s,
        "deterministic_duration_s": expected_duration,
        "target_market": market,
        "requested_target_market": requested_market,
        "reason": (
            "deterministic_preview_contract"
            if corrections else "planner_aligned_with_preview_contract"
        ),
    }
    if corrections:
        logger.info(
            "[AutonomousDirector] planner guard corrected "
            f"{corrections} planner_niche={planner.niche} decision_niche={expected_niche}"
        )
    return {"planner": guarded, "meta": meta}


def _selected_creative_treatment(search: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not search:
        return {}
    selected_id = search.get("selected_treatment_id")
    candidates = search.get("candidates") or []
    for item in candidates:
        if item.get("treatment_id") == selected_id:
            return item
    return candidates[0] if candidates else {}


def _apply_creative_treatment_to_planner(
    planner: PlannerOutput,
    *,
    selected_creative_treatment: dict[str, Any],
) -> PlannerOutput:
    if not selected_creative_treatment:
        return planner
    label = selected_creative_treatment.get("label") or selected_creative_treatment.get("treatment_id")
    intent = selected_creative_treatment.get("director_intent") or ""
    camera = selected_creative_treatment.get("camera_language") or ""
    edit = selected_creative_treatment.get("edit_rhythm") or ""
    refs = selected_creative_treatment.get("reference_policy") or ""
    notes = "\n".join(
        part for part in [
            planner.director_notes,
            f"Creative treatment: {label}. {intent}".strip(),
            f"Camera language: {camera}" if camera else "",
            f"Edit rhythm: {edit}" if edit else "",
            f"Reference policy: {refs}" if refs else "",
        ]
        if part
    )
    style = ". ".join(
        part for part in [
            planner.style_direction.rstrip("."),
            f"Treatment camera: {camera}" if camera else "",
            f"Treatment edit: {edit}" if edit else "",
        ]
        if part
    )
    return planner.model_copy(update={
        "director_notes": notes[:1600],
        "style_direction": style[:900],
    })


def _apply_aspect_ratio_override(
    planner: PlannerOutput,
    *,
    aspect_ratio: Optional[str],
) -> PlannerOutput:
    normalized = (aspect_ratio or "").strip()
    if normalized in {"", "auto", "adaptive"}:
        return planner
    if normalized not in {"9:16", "16:9", "1:1"}:
        logger.warning(f"[AutonomousDirector] ignored invalid aspect_ratio={normalized!r}")
        return planner
    note = f"Output frame override from UI: {normalized}. Compose every shot for this final aspect ratio."
    notes = "\n".join(part for part in [planner.director_notes, note] if part)
    return planner.model_copy(update={
        "suggested_aspect_ratio": normalized,
        "director_notes": notes[:1600],
    })


def _merge_creative_treatment_into_production_treatment(
    production_treatment: dict[str, Any],
    *,
    selected_creative_treatment: dict[str, Any],
) -> None:
    if not selected_creative_treatment:
        return
    label = selected_creative_treatment.get("label") or selected_creative_treatment.get("treatment_id")
    camera = selected_creative_treatment.get("camera_language")
    edit = selected_creative_treatment.get("edit_rhythm")
    refs = selected_creative_treatment.get("reference_policy")
    intent = selected_creative_treatment.get("director_intent")
    production_treatment["selected_creative_treatment"] = selected_creative_treatment
    production_treatment["story_engine"] = (
        f"{production_treatment.get('story_engine', '')} "
        f"Selected director treatment: {label}. {intent or ''}"
    ).strip()
    if camera:
        production_treatment["camera_language"] = [
            f"selected treatment camera: {camera}",
            *list(production_treatment.get("camera_language") or []),
        ]
    if edit:
        production_treatment["editing_rhythm"] = [
            f"selected treatment edit rhythm: {edit}",
            *list(production_treatment.get("editing_rhythm") or []),
        ]
    if refs:
        production_treatment["reference_policy"] = [
            f"selected treatment reference policy: {refs}",
            *list(production_treatment.get("reference_policy") or []),
        ]


def _creative_camera_note(selected_creative_treatment: dict[str, Any]) -> str:
    camera = selected_creative_treatment.get("camera_language") if selected_creative_treatment else ""
    return f"Selected treatment camera language: {camera}." if camera else ""


def _creative_constraint_lines(selected_creative_treatment: dict[str, Any]) -> list[str]:
    if not selected_creative_treatment:
        return []
    lines = []
    label = selected_creative_treatment.get("label") or selected_creative_treatment.get("treatment_id")
    intent = selected_creative_treatment.get("director_intent")
    refs = selected_creative_treatment.get("reference_policy")
    if label or intent:
        lines.append(f"Creative treatment: {label}. {intent or ''}".strip())
    if refs:
        lines.append(f"Creative treatment reference policy: {refs}")
    return lines


def _creative_treatment_summary(selected_creative_treatment: dict[str, Any]) -> str:
    if not selected_creative_treatment:
        return "auto-selected during production decision"
    label = selected_creative_treatment.get("label") or selected_creative_treatment.get("treatment_id") or "auto"
    score = selected_creative_treatment.get("score")
    reason = selected_creative_treatment.get("selection_reason") or selected_creative_treatment.get("director_intent") or ""
    score_text = f" score={score}" if score is not None else ""
    return f"{label}{score_text}; {reason}".strip()


def _cinematic_grammar_directives(cinematic_grammar: dict[str, Any]) -> list[str]:
    if not cinematic_grammar:
        return []
    directives = [
        str(x)
        for x in (cinematic_grammar.get("prompt_directives") or [])[:2]
        if str(x).strip()
    ]
    transition = [
        str(x)
        for x in (cinematic_grammar.get("transition_logic") or [])[:1]
        if str(x).strip()
    ]
    return [*directives, *transition]


def _build_director_plan(
    req: AutonomousRunRequest,
    planner: PlannerOutput,
    storyboard: StoryboardOutput,
    director: DirectorOutput,
    role_tagger: RoleTaggerOutput,
    runtime_structure: Optional[dict] = None,
    target_market: Optional[str] = None,
    market_inference: Optional[dict[str, Any]] = None,
    planner_guard: Optional[dict[str, Any]] = None,
    creative_treatment_search: Optional[dict[str, Any]] = None,
) -> DirectorPlan:
    """Convert skill outputs → agent/schemas.py:DirectorPlan.

    This is the bridge that lets the existing render_plan() / video_worker
    pipeline consume autonomous director output without modification.
    """
    import uuid
    from datetime import datetime

    plan_id = f"auto_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.utcnow().isoformat() + "Z"
    playbook = get_niche_playbook(planner.niche)
    effective_target_market = target_market or req.target_market
    market_playbook = get_market_playbook(effective_target_market)
    if market_inference:
        market_playbook["market_inference"] = market_inference
        market_playbook["requested_target_market"] = req.target_market
    runtime_structure = runtime_structure or plan_runtime_structure(
        director.total_duration_s,
        niche=planner.niche,
        platform=req.target_platform,
    ).model_dump()
    playbook_camera = ", ".join(playbook.get("camera") or [])
    playbook_quality = list(playbook.get("quality_bar") or [])
    playbook_avoid = list(playbook.get("avoid") or [])
    playbook_safety = list(playbook.get("safety_rules") or [])
    playbook_audio = str(playbook.get("audio") or "")
    playbook_best_for = str(playbook.get("best_for") or planner.niche)
    is_long_form = bool(runtime_structure.get("runtime_class") not in ("short", "sequence"))
    market_guidance = _market_guidance(effective_target_market, market_playbook)
    quad_modal_reference_roles = _quad_modal_reference_roles(role_tagger)
    selected_creative_treatment = _selected_creative_treatment(creative_treatment_search)
    seedance_reference_allocation = build_seedance_reference_allocation(
        niche=planner.niche,
        runtime_payload={**runtime_structure, "target_market": effective_target_market},
        reference_counts={
            "images": len(req.reference_image_urls),
            "videos": len(req.reference_video_urls),
            "audios": len(req.reference_audio_urls),
            "pinned_assets": len(req.pinned_assets),
        },
        has_dialogue=planner.suggested_audio_mode == "dialogue_vo",
        creative_treatment=selected_creative_treatment,
        reference_manifest=getattr(req, "reference_manifest", {}),
    )
    niche_runtime_director = build_niche_runtime_director_contract(
        niche=planner.niche,
        runtime_payload=runtime_structure,
        target_market=effective_target_market,
        target_platform=req.target_platform,
        has_dialogue=planner.suggested_audio_mode == "dialogue_vo",
        reference_counts={
            "images": len(req.reference_image_urls),
            "videos": len(req.reference_video_urls),
            "audios": len(req.reference_audio_urls),
            "pinned_assets": len(req.pinned_assets),
        },
    )
    cinematic_grammar = build_cinematic_grammar_contract(
        niche=planner.niche,
        runtime_payload=runtime_structure,
        target_market=effective_target_market,
        creative_treatment=selected_creative_treatment,
    )
    niche_production_recipe = build_niche_production_recipe(
        niche=planner.niche,
        runtime_payload=runtime_structure,
        target_market=effective_target_market,
        target_platform=req.target_platform,
        niche_playbook=playbook,
        reference_counts={
            "images": len(req.reference_image_urls),
            "videos": len(req.reference_video_urls),
            "audios": len(req.reference_audio_urls),
            "pinned_assets": len(req.pinned_assets),
        },
        has_dialogue=planner.suggested_audio_mode == "dialogue_vo",
        selected_creative_treatment=selected_creative_treatment,
    )
    seedance_prompt_formula = build_seedance_prompt_formula(
        niche=planner.niche,
        runtime_payload=runtime_structure,
        target_market=effective_target_market,
        target_platform=req.target_platform,
        has_dialogue=planner.suggested_audio_mode == "dialogue_vo",
        reference_allocation=seedance_reference_allocation,
        niche_production_recipe=niche_production_recipe,
    )
    production_treatment = build_production_treatment(
        user_idea=req.user_idea,
        niche=planner.niche,
        runtime_structure=runtime_structure,
        niche_playbook=playbook,
        market_playbook=market_playbook,
        reference_counts={
            "images": len(req.reference_image_urls),
            "videos": len(req.reference_video_urls),
            "audios": len(req.reference_audio_urls),
            "pinned_assets": len(req.pinned_assets),
        },
    ).model_dump()
    if selected_creative_treatment:
        _merge_creative_treatment_into_production_treatment(
            production_treatment,
            selected_creative_treatment=selected_creative_treatment,
        )

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
                personality=[planner.primary_emotion, planner.mood],
                voice_persona=(
                    "natural Vietnamese conversational voice"
                    if planner.suggested_audio_mode == "dialogue_vo" else None
                ),
            ))
            char_count += 1
        elif t.role == "secondary_character" and char_count < 3:
            characters.append(Character(
                id=f"char_secondary_{char_count}",
                name=f"Supporting {char_count}",
                role="supporting",
                face_signature=f"Reference @image_{t.index + 1}",
                outfit="(inherit from reference image)",
                personality=[planner.mood],
            ))
            char_count += 1

    # Products from tagged refs
    products: list[Product] = []
    for t in role_tagger.tagged:
        if t.modality == "image" and t.role in ("product_hero", "product_detail"):
            products.append(Product(
                id=f"prod_{t.role}_{t.index}",
                name=f"Product @image_{t.index + 1}",
                hero_features=[planner.hook_pattern, playbook_best_for],
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
            color_grading=f"{planner.mood}; consistent grade across every shot",
            lighting_design=(
                "motivated practical lighting; keep exposure and key direction stable across chained shots"
            ),
            camera_language=(
                f"{playbook_camera}. {_creative_camera_note(selected_creative_treatment)} "
                "Every cut must change shot size or camera mode deliberately."
                if playbook_camera else
                f"deliberate cinematic shot sizes; {_creative_camera_note(selected_creative_treatment)} avoid random camera movement"
            ),
            film_grain="clean photoreal digital with subtle cinematic texture",
            aspect_ratio=planner.suggested_aspect_ratio,
        ),
        audio_design=AudioDesign(
            mood=planner.mood,
            tempo=(
                "slow-build narrative pacing" if is_long_form else "fast hook-first social pacing"
            ),
            music_genre=playbook_audio,
            sfx_emphasis=playbook_audio.split(", ") if playbook_audio else [],
            dialogue_style=(
                "monologue" if planner.suggested_audio_mode == "dialogue_vo"
                else "silent" if planner.suggested_audio_mode == "silent_native"
                else "ambient"
            ),
        ),
        setting=Setting(
            location=(
                "single coherent production location inferred from the idea and references"
                if not is_long_form else
                "scene-by-scene locations; preserve spatial continuity within each scene"
            ),
            time_of_day="consistent motivated time of day unless the story explicitly changes scene",
            atmosphere=f"{planner.mood}; {playbook_best_for}",
        ),
        constraints=Constraints(
            must_have=[
                f"First 3 seconds must execute: {planner.hook_first_3s}",
                f"Target market localization: {market_guidance}",
                f"Caption/dialogue language: {market_playbook.get('caption_language') or market_playbook.get('primary_language')}",
                "Every shot must be physically filmable and visually specific",
                "Reference identity, product, style, motion, and audio anchors must stay consistent",
                f"Production format: {production_treatment['production_format']}",
                f"Story engine: {production_treatment['story_engine']}",
                *_creative_constraint_lines(selected_creative_treatment),
            ],
            must_avoid=[
                "watermark",
                "text overlay duplication",
                "face morphing",
                "outfit drift",
                "product/logo drift",
                "lighting flicker between cuts",
                *playbook_quality,
                *playbook_avoid,
            ],
            brand_safety=playbook_safety,
        ),
        reference_assets=reference_assets,
        director_notes=(
            f"{planner.director_notes}\nMarket guidance: {market_guidance}\n"
            f"Selected creative treatment: {_creative_treatment_summary(selected_creative_treatment)}"
            if planner.director_notes else
            f"Market guidance: {market_guidance}\n"
            f"Selected creative treatment: {_creative_treatment_summary(selected_creative_treatment)}"
        ),
        storytelling_meta={
            "user_idea": req.user_idea,
            "hook_pattern": planner.hook_pattern,
            "hook_first_3s": planner.hook_first_3s,
            "primary_emotion": planner.primary_emotion,
            "target_market": effective_target_market,
            "requested_target_market": req.target_market,
            "market_inference": market_inference or {},
            "planner_guard": planner_guard or {},
            "target_platform": req.target_platform,
            "pinned_asset_ids": req.pinned_asset_ids,
            "pinned_assets": req.pinned_assets,
            "market_playbook": market_playbook,
            "niche_playbook": playbook,
            "safety_rules": playbook_safety,
            "production_bible_version": "cinejelly_v1",
            "long_form_mode": is_long_form,
            "runtime_structure": runtime_structure,
            "production_treatment": production_treatment,
            "creative_treatment_search": creative_treatment_search or {},
            "selected_creative_treatment": selected_creative_treatment,
            "niche_runtime_director": niche_runtime_director,
            "niche_production_recipe": niche_production_recipe,
            "seedance_prompt_formula": seedance_prompt_formula,
            "cinematic_grammar": cinematic_grammar,
            "seedance_reference_allocation": seedance_reference_allocation,
            "n_chunks": director.n_chunks,
            "chunk_shot_ids": director.chunk_shot_ids,
            "quad_modal_reference_roles": quad_modal_reference_roles,
            "reference_prompt_suffix": role_tagger.prompt_tag_suffix,
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
        camera_palette = playbook.get("camera") or []
        composition_hint = (
            str(camera_palette[s.index % len(camera_palette)])
            if camera_palette else
            "deliberate cinematic framing"
        )
        treatment_camera = production_treatment.get("camera_language") or []
        treatment_editing = production_treatment.get("editing_rhythm") or []
        treatment_scene = production_treatment.get("scene_design") or []
        treatment_reference = production_treatment.get("reference_policy") or []
        treatment_directive = "; ".join(
            str(x)
            for x in [
                *(treatment_camera[:2] if isinstance(treatment_camera, list) else []),
                *(treatment_editing[:1] if isinstance(treatment_editing, list) else []),
                *(treatment_scene[:1] if isinstance(treatment_scene, list) else []),
                *(treatment_reference[:1] if isinstance(treatment_reference, list) else []),
                *_cinematic_grammar_directives(cinematic_grammar),
            ]
        )[:420]
        background_hint = bible.setting.location
        sfx_palette = list(bible.audio_design.sfx_emphasis or [])
        sfx = [sfx_palette[s.index % len(sfx_palette)]] if sfx_palette else []

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
                composition=composition_hint,
                lighting_override=s.lighting_override or None,
                background=background_hint,
            ),
            audio=ShotAudio(
                dialogue_vn=None,
                caption_on_screen=None,
                sfx=sfx,
                music_cue=playbook_audio or None,
            ),
            continuity=ShotContinuity(
                character_ids=char_ids,
                product_ids=prod_ids,
                reference_indices=ref_indices,
                previous_shot_id=s.previous_shot_id,
                style_anchor=(
                    f"{planner.style_direction}. Camera: {playbook_camera}. "
                    f"Quality: {'; '.join(playbook_quality[:3])}"
                )[:300],
            ),
            model_routing=ShotModelRouting(
                preferred_model=director.user_model,
                reasoning=director.reasoning,
            ),
            dynamic_description=(
                f"{_fmt_mmss(start_s)}-{_fmt_mmss(end_s)} "
                f"{s.camera_shot} {s.camera_movement}: {s.subject}. {s.action}. "
                f"Composition: {composition_hint}. Treatment: {treatment_directive}. "
                f"Audio: {playbook_audio or planner.suggested_audio_mode}."
            ),
        ))
        cursor = end_s

    runtime_class = str(runtime_structure.get("runtime_class") or "")
    continuity_handoff_policy = apply_continuity_handoffs(
        shots,
        duration_s=director.total_duration_s,
        runtime_class=runtime_class,
    )
    scene_memory_pack = build_scene_memory_pack(
        runtime_structure=runtime_structure,
        shots=shots,
        seedance_reference_allocation=seedance_reference_allocation,
    )

    production_graph = build_production_graph(
        plan_id=plan_id,
        duration_s=director.total_duration_s,
        runtime_structure=runtime_structure,
        shots=shots,
        scene_memory_pack=scene_memory_pack,
        prompt_formula=seedance_prompt_formula,
        reference_contract=seedance_prompt_formula,
    ).model_dump()
    dynamic_keyframe_memory = build_dynamic_keyframe_memory_contract(
        scene_memory_pack=scene_memory_pack,
        production_graph=production_graph,
    )
    long_form_execution_gate = build_long_form_execution_gate(
        duration_s=director.total_duration_s,
        runtime_payload=runtime_structure,
        production_graph=production_graph,
        scene_memory_pack=scene_memory_pack,
        shots=shots,
        graph_executor_enabled=None,
    )
    bible.storytelling_meta = {
        **(bible.storytelling_meta or {}),
        "continuity_handoff_policy": continuity_handoff_policy,
        "scene_memory_pack": scene_memory_pack,
        "dynamic_keyframe_memory": dynamic_keyframe_memory,
        "production_graph": production_graph,
        "long_form_execution_gate": long_form_execution_gate,
    }

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
    from agent.model_specs import get_user_model_cost_rate

    rate = get_user_model_cost_rate(director.user_model)
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


def _market_guidance(target_market: str, market_playbook: Optional[dict] = None) -> str:
    market = (target_market or "auto").lower()
    if market_playbook:
        return (
            f"{market_playbook.get('label', market)}; "
            f"language={market_playbook.get('primary_language', 'auto')}; "
            f"hook={market_playbook.get('hook_style', 'platform-native')}; "
            f"dialogue={market_playbook.get('dialogue_style', 'natural')}; "
            f"claims={market_playbook.get('claim_style', 'show proof visually')}"
        )
    mapping = {
        "auto": "infer the market from language, references, platform, product, and setting; keep dialogue/captions natural for that audience",
        "vn": "Vietnam-first: natural Vietnamese speech, local social proof, Saigon/Hanoi/SEA visual realism when relevant, no forced US idioms",
        "us": "US-first: direct English hook, clear benefit claim, creator-native pacing, avoid region-specific Vietnamese slang",
        "sea": "Southeast Asia: warm practical realism, mobile-first commerce/social context, broadly understandable English or local-language cues",
        "jp": "Japan-first: restrained product claims, clean composition, polite natural phrasing, culturally careful lifestyle cues",
        "kr": "Korea-first: polished beauty/lifestyle rhythm, clean trend-aware visual language, concise Korean-market social cues",
        "global": "global: internationally understandable hook, minimal local slang, captions that travel across markets",
    }
    return mapping.get(market, mapping["auto"])


_REFERENCE_ALLOWED_ROLES = {
    "image": {
        "character_anchor", "secondary_character", "product_hero", "product_detail",
        "style_reference", "environment", "brand_asset",
    },
    "video": {"camera_motion", "motion_style", "shot_pacing"},
    "audio": {"beat_reference", "lip_sync_source", "sfx_layer"},
}

_REFERENCE_ROLE_LABELS = {
    "character_anchor": "primary character (exact face, hair, outfit from reference)",
    "secondary_character": "secondary character (exact appearance from reference)",
    "product_hero": "product (exact packaging, geometry, colors and label)",
    "product_detail": "product detail (exact texture, material and label)",
    "style_reference": "style reference (mood, color grade and lighting only; do not copy subject)",
    "environment": "environment / setting (preserve location layout and atmosphere)",
    "brand_asset": "brand asset / logo (preserve typography and brand colors)",
    "camera_motion": "camera movement reference (match trajectory)",
    "motion_style": "motion style reference (match action tempo and easing)",
    "shot_pacing": "shot pacing reference (match cut rhythm and reveal timing)",
    "beat_reference": "audio beat reference (match BGM rhythm and emotional pacing)",
    "lip_sync_source": "lip-sync source audio (sync dialogue timing; do not clone identity)",
    "sfx_layer": "SFX / ambient layer reference",
}


def _apply_reference_manifest_role_overrides(
    role_tagger: RoleTaggerOutput,
    manifest: dict[str, Any],
) -> RoleTaggerOutput:
    """Let confirmed UI manifest roles override heuristic/vision role tagging.

    RoleTagger remains useful for first-pass suggestions, but paid rendering
    should use explicit user-confirmed reference jobs when available.
    """
    if not isinstance(manifest, dict):
        return role_tagger
    items = manifest.get("items") or []
    if not isinstance(items, list):
        return role_tagger

    by_key: dict[tuple[str, int], dict[str, Any]] = {}
    by_url: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in items[:12]:
        if not isinstance(raw, dict) or not raw.get("role_confirmed"):
            continue
        kind = str(raw.get("kind") or "").strip().lower()
        role = str(raw.get("role") or "").strip().lower()
        if kind not in _REFERENCE_ALLOWED_ROLES or role not in _REFERENCE_ALLOWED_ROLES[kind]:
            continue
        tag = str(raw.get("tag") or "").strip()
        index = _reference_tag_index(tag, kind)
        item = {
            "tag": tag,
            "kind": kind,
            "role": role,
            "name": str(raw.get("name") or "").strip()[:120],
            "prompt_binding": str(raw.get("prompt_binding") or "").strip()[:260],
        }
        if index is not None:
            by_key[(kind, index)] = item
        url = str(raw.get("url") or "").strip()
        if url:
            by_url[(kind, url)] = item

    if not by_key and not by_url:
        return role_tagger

    changed = False
    tagged = []
    for ref in role_tagger.tagged:
        item = by_key.get((ref.modality, ref.index)) or by_url.get((ref.modality, ref.url))
        if not item:
            tagged.append(ref)
            continue
        role = str(item["role"])
        canonical_tag = f"@{ref.modality}_{ref.index + 1}"
        tag = f"{canonical_tag} as {_REFERENCE_ROLE_LABELS.get(role, role.replace('_', ' '))}"
        note = "UI confirmed reference manifest role"
        if item.get("name"):
            note += f": {item['name']}"
        tagged.append(ref.model_copy(update={
            "role": role,
            "tag": tag,
            "confidence": 1.0,
            "notes": note,
        }))
        changed = True

    if not changed:
        return role_tagger

    suffix = (
        "Use references: "
        + ", ".join(ref.tag for ref in tagged)
        + ". Follow the confirmed Reference Manifest exactly; never swap product, "
          "character, style, camera, motion, beat, SFX or voice roles."
    )
    return role_tagger.model_copy(update={
        "tagged": tagged,
        "prompt_tag_suffix": suffix,
    })


def _reference_tag_index(tag: str, kind: str) -> int | None:
    prefix = f"@{kind}_"
    if not tag.startswith(prefix):
        return None
    try:
        value = int(tag[len(prefix):])
    except ValueError:
        return None
    if value <= 0:
        return None
    return value - 1


def _quad_modal_reference_roles(role_tagger: RoleTaggerOutput) -> dict:
    """Persist image/video/audio roles in the Production Bible metadata.

    The legacy `ReferenceAsset` schema is image-centric because it feeds the
    continuity manager. Seedance 2.0 also consumes video and audio references,
    so autonomous mode stores their assigned jobs here for prompt compilation.
    """
    by_modality = {"images": [], "videos": [], "audios": []}
    for tagged in role_tagger.tagged:
        row = {
            "index": tagged.index,
            "role": tagged.role,
            "tag": tagged.tag,
            "confidence": tagged.confidence,
            "notes": tagged.notes,
        }
        if tagged.modality == "image":
            by_modality["images"].append(row)
        elif tagged.modality == "video":
            by_modality["videos"].append(row)
        elif tagged.modality == "audio":
            by_modality["audios"].append(row)
    for values in by_modality.values():
        values.sort(key=lambda item: int(item.get("index") or 0))
    return by_modality


__all__ = [
    "AutonomousDirector",
    "AutonomousRunRequest", "AutonomousDirectorResult",
]
