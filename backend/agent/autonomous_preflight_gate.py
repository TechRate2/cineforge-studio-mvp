"""Pre-render quality gate for CineJelly Autonomous Director.

This gate runs after planning and before paid render work. It catches structural
problems that should be visible from the DirectorPlan: missing hook/treatment,
weak reference coverage, unsafe niche claims, long-form graph gaps, shot limit
violations, and model-routing risks.
"""
from __future__ import annotations

from typing import Any, Optional

from agent.schemas import DirectorPlan
from agent.continuity_handoff_policy import build_continuity_handoff_policy
from agent.cross_shot_diagnostic import diagnose_cross_shot_coherence
from agent.niche_execution_rubric import score_plan_against_niche_rubric
from agent.long_form_execution_gate import build_long_form_execution_gate
from agent.producer_story_critic import critique_producer_story
from agent.reference_sufficiency_gate import build_reference_sufficiency_report
from agent.responsible_content_gate import build_responsible_content_gate
from agent.screenplay_scene_linter import lint_screenplay_scene_structure
from agent.seedance_shot_linter import lint_seedance_plan
from agent.script_asset_sop import build_script_asset_sop
from skills.niche_readiness import build_niche_readiness_matrix


def build_autonomous_preflight_report(
    *,
    plan: DirectorPlan,
    resolved_model: str,
    target_market: str,
    target_platform: str,
    reference_counts: dict[str, int],
    model_violations: Optional[list[str]] = None,
    pinned_assets: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    bible = plan.continuity_bible
    meta = bible.storytelling_meta or {}
    runtime = meta.get("runtime_structure") or {}
    treatment = meta.get("production_treatment") or {}
    graph = meta.get("production_graph") or {}
    niche = str((meta.get("niche_playbook") or {}).get("niche") or meta.get("niche") or "")
    if not niche:
        niche = str(getattr(plan, "intent", "") or bible.intent or "unknown")

    checks: list[dict[str, Any]] = []
    hard_failures: list[str] = []
    warnings: list[str] = []
    score = 100.0

    def add(name: str, status: str, detail: str, *, severity: str = "info", penalty: float = 0.0) -> None:
        nonlocal score
        checks.append({"name": name, "status": status, "severity": severity, "detail": detail})
        if status == "fail":
            hard_failures.append(name)
        elif status == "warn":
            warnings.append(name)
        score = max(0.0, score - penalty)

    _check_core_plan(add, plan)
    responsible_content_gate = _check_responsible_content_gate(
        add,
        plan=plan,
        target_market=target_market,
        reference_counts=reference_counts,
    )
    _check_runtime(add, plan, runtime, graph)
    long_form_execution_gate = _check_long_form_execution_gate(add, plan, runtime, graph)
    scene_lint = _check_screenplay_scene_lint(add, plan, runtime)
    _check_treatment(add, treatment)
    story_critic = _check_producer_story_critic(add, plan, target_market, target_platform)
    niche_execution_rubric = _check_niche_execution_rubric(add, plan, target_market, target_platform)
    handoff_policy = _check_continuity_handoff_policy(add, plan, runtime)
    cross_shot_diagnostic = _check_cross_shot_diagnostic(add, plan)
    reference_sufficiency = _check_reference_sufficiency(
        add,
        plan=plan,
        reference_counts=reference_counts,
        target_market=target_market,
    )
    script_asset_sop = _check_script_asset_sop(
        add,
        plan=plan,
        runtime=runtime,
        niche=niche,
        target_market=target_market,
        reference_counts=reference_counts,
    )
    _check_references(add, plan, reference_counts, pinned_assets or [])
    _check_model(add, plan, resolved_model, model_violations or [])
    shot_lint = _check_seedance_shot_lint(add, plan)
    _check_niche_market(add, niche, target_market, target_platform)

    status = "fail" if hard_failures else ("warn" if warnings else "pass")
    return {
        "schema_version": "cinejelly.autonomous_preflight.v1",
        "status": status,
        "score": round(score, 1),
        "render_allowed": not hard_failures,
        "manual_review_recommended": bool(warnings or _is_review_required(niche)),
        "niche": niche,
        "target_market": target_market,
        "target_platform": target_platform,
        "resolved_model": resolved_model,
        "hard_failures": hard_failures,
        "warnings": warnings,
        "checks": checks,
        "responsible_content_gate": responsible_content_gate,
        "producer_story_critic": story_critic,
        "niche_execution_rubric": niche_execution_rubric,
        "continuity_handoff_policy": handoff_policy,
        "long_form_execution_gate": long_form_execution_gate,
        "cross_shot_diagnostic": cross_shot_diagnostic,
        "reference_sufficiency": reference_sufficiency,
        "script_asset_sop": script_asset_sop,
        "screenplay_scene_lint": scene_lint,
        "seedance_shot_lint": shot_lint,
        "next_action": (
            "fix_plan_before_render" if hard_failures
            else "render_with_manual_review" if warnings or _is_review_required(niche)
            else "render"
        ),
    }


def _check_core_plan(add: Any, plan: DirectorPlan) -> None:
    bible = plan.continuity_bible
    if len((bible.logline or "").strip()) < 8:
        add("logline", "warn", "Production bible logline is too thin.", severity="warning", penalty=5)
    else:
        add("logline", "pass", "Production bible has a usable logline.")
    if not plan.shot_list:
        add("shot_list", "fail", "No shots were produced.", severity="error", penalty=45)
        return
    if any(s.duration_s <= 0 for s in plan.shot_list):
        add("shot_duration_positive", "fail", "At least one shot has non-positive duration.", severity="error", penalty=35)
    else:
        add("shot_duration_positive", "pass", "All shots have positive duration.")
    hook_like = plan.shot_list[0].purpose.lower() if plan.shot_list else ""
    if "hook" in hook_like or "open" in hook_like:
        add("first_shot_hook", "pass", "First shot is explicitly hook/opening oriented.")
    else:
        add("first_shot_hook", "warn", "First shot is not clearly marked as hook/opening.", severity="warning", penalty=8)


def _check_responsible_content_gate(
    add: Any,
    *,
    plan: DirectorPlan,
    target_market: str,
    reference_counts: dict[str, int],
) -> dict[str, Any]:
    bible = plan.continuity_bible
    meta = bible.storytelling_meta or {}
    idea = str(
        meta.get("user_idea")
        or bible.logline
        or bible.title
        or " ".join(getattr(shot, "dynamic_description", "") for shot in plan.shot_list[:3])
    )
    has_dialogue = any(bool(getattr(shot.audio, "dialogue_vn", None)) for shot in plan.shot_list)
    gate = build_responsible_content_gate(
        user_idea=idea,
        target_market=target_market,
        has_dialogue=has_dialogue,
        reference_counts=reference_counts,
    )
    if not gate.get("render_allowed", True):
        add(
            "responsible_content_gate",
            "fail",
            "Responsible content gate blocked render: "
            + ", ".join(gate.get("hard_blockers") or ["unknown"]),
            severity="error",
            penalty=40,
        )
    elif gate.get("manual_review_required"):
        add(
            "responsible_content_gate",
            "warn",
            "Responsible content review recommended: "
            + ", ".join(gate.get("review_flags") or ["review"]),
            severity="warning",
            penalty=10,
        )
    else:
        add("responsible_content_gate", "pass", "No public-figure, voice-clone, or known-IP blocker detected.")
    return gate


def _check_runtime(add: Any, plan: DirectorPlan, runtime: dict[str, Any], graph: dict[str, Any]) -> None:
    duration = int(plan.continuity_bible.duration_s or 0)
    runtime_class = str(runtime.get("runtime_class") or "")
    if duration > 180 and not runtime:
        add("runtime_structure", "fail", "Long-form plan is missing runtime_structure.", severity="error", penalty=35)
    elif runtime:
        add("runtime_structure", "pass", f"Runtime structure exists: {runtime_class or 'unknown'}.")
    if duration > 180:
        graph_summary = graph.get("summary") if isinstance(graph, dict) else None
        if not graph_summary:
            add("production_graph", "fail", "Long-form plan is missing production graph summary.", severity="error", penalty=35)
        else:
            add("production_graph", "pass", f"Production graph has {graph_summary.get('node_count')} nodes.")
    if duration > 60 and len(plan.shot_list) < max(6, duration // 30):
        add("shot_density", "warn", "Longer video has a sparse shot list; pacing may feel underproduced.", severity="warning", penalty=10)
    else:
        add("shot_density", "pass", "Shot density is plausible for requested runtime.")


def _check_long_form_execution_gate(
    add: Any,
    plan: DirectorPlan,
    runtime: dict[str, Any],
    graph: dict[str, Any],
) -> dict[str, Any]:
    meta = plan.continuity_bible.storytelling_meta or {}
    route_quality_scorecard = None
    if isinstance(meta, dict):
        route_quality_scorecard = (
            meta.get("route_quality_scorecard")
            or (meta.get("production_decision") or {}).get("route_quality_scorecard")
        )
    gate = build_long_form_execution_gate(
        duration_s=int(plan.continuity_bible.duration_s or 0),
        runtime_payload=runtime,
        production_graph=graph,
        scene_memory_pack=meta.get("scene_memory_pack") if isinstance(meta, dict) else None,
        shots=list(plan.shot_list),
        graph_executor_enabled=None,
        route_quality_scorecard=route_quality_scorecard,
    )
    if not gate.get("enabled"):
        add("long_form_execution_gate", "pass", "Short-form route does not require the long-form execution gate.")
    elif gate.get("status") == "fail":
        add(
            "long_form_execution_gate",
            "fail",
            (
                "Long-form execution is not ready: "
                + ", ".join(gate.get("blockers") or ["unknown"])
            ),
            severity="error",
            penalty=35,
        )
    elif gate.get("status") == "warn":
        add(
            "long_form_execution_gate",
            "warn",
            f"Long-form route needs operator attention: {gate.get('next_action')}.",
            severity="warning",
            penalty=12,
        )
    else:
        add("long_form_execution_gate", "pass", "Long-form graph, scene memory, handoff, and QA contract are ready.")
    return gate


def _check_treatment(add: Any, treatment: dict[str, Any]) -> None:
    required = ["story_engine", "camera_language", "editing_rhythm", "reference_policy", "seedance_execution", "qa_risks"]
    missing = [k for k in required if not treatment.get(k)]
    if missing:
        add("production_treatment", "fail", f"Production treatment missing: {', '.join(missing)}.", severity="error", penalty=30)
    else:
        add("production_treatment", "pass", "Production treatment locks story, camera, edit, reference, Seedance, and QA policy.")


def _check_producer_story_critic(
    add: Any,
    plan: DirectorPlan,
    target_market: str,
    target_platform: str,
) -> dict[str, Any]:
    critic = critique_producer_story(
        plan=plan,
        target_market=target_market,
        target_platform=target_platform,
    )
    score = float(critic.get("score") or 0.0)
    status = str(critic.get("status") or "warn")
    issues = ", ".join((critic.get("top_issues") or [])[:4]) or "none"
    if status == "fail":
        add(
            "producer_story_critic",
            "fail",
            f"Producer story critic score {score}: {issues}.",
            severity="error",
            penalty=30,
        )
    elif status == "warn":
        add(
            "producer_story_critic",
            "warn",
            f"Producer story critic score {score}: {issues}.",
            severity="warning",
            penalty=10,
        )
    else:
        add("producer_story_critic", "pass", f"Producer story critic passes with score {score}.")
    return critic


def _check_niche_execution_rubric(
    add: Any,
    plan: DirectorPlan,
    target_market: str,
    target_platform: str,
) -> dict[str, Any]:
    rubric = score_plan_against_niche_rubric(
        plan=plan,
        target_market=target_market,
        target_platform=target_platform,
    )
    score = float(rubric.get("score") or 0.0)
    status = str(rubric.get("status") or "warn")
    issues = ", ".join((rubric.get("top_issues") or [])[:4]) or "none"
    if status == "fail":
        add(
            "niche_execution_rubric",
            "fail",
            f"Niche execution score {score}: {issues}.",
            severity="error",
            penalty=28,
        )
    elif status == "warn":
        add(
            "niche_execution_rubric",
            "warn",
            f"Niche execution score {score}: {issues}.",
            severity="warning",
            penalty=10,
        )
    else:
        add("niche_execution_rubric", "pass", f"Niche execution rubric passes with score {score}.")
    return rubric


def _check_continuity_handoff_policy(
    add: Any,
    plan: DirectorPlan,
    runtime: dict[str, Any],
) -> dict[str, Any]:
    policy = build_continuity_handoff_policy(
        plan.shot_list,
        duration_s=int(plan.continuity_bible.duration_s or 0),
        runtime_class=str(runtime.get("runtime_class") or ""),
    )
    missing = int(policy.get("missing_required_handoffs") or 0)
    required = int(policy.get("required_handoffs") or 0)
    duration = int(plan.continuity_bible.duration_s or 0)
    if missing and duration > 180:
        add(
            "continuity_handoff_policy",
            "fail",
            f"{missing}/{required} required long-form handoff(s) are missing previous-shot anchors.",
            severity="error",
            penalty=28,
        )
    elif missing:
        add(
            "continuity_handoff_policy",
            "warn",
            f"{missing}/{required} required handoff(s) are missing previous-shot anchors.",
            severity="warning",
            penalty=12,
        )
    elif required:
        add(
            "continuity_handoff_policy",
            "pass",
            f"{policy.get('active_handoffs')}/{required} required continuity handoff(s) are active.",
        )
    else:
        add("continuity_handoff_policy", "pass", "No required previous-shot continuity handoffs.")
    return policy


def _check_cross_shot_diagnostic(add: Any, plan: DirectorPlan) -> dict[str, Any]:
    diagnostic = diagnose_cross_shot_coherence(plan=plan)
    score = float(diagnostic.get("score") or 0.0)
    status = str(diagnostic.get("status") or "warn")
    issues = ", ".join((diagnostic.get("top_issues") or [])[:4]) or "none"
    duration = int(diagnostic.get("duration_s") or 0)
    if status == "fail":
        add(
            "cross_shot_diagnostic",
            "fail" if duration > 180 else "warn",
            f"Cross-shot coherence score {score}: {issues}.",
            severity="error" if duration > 180 else "warning",
            penalty=30 if duration > 180 else 12,
        )
    elif status == "warn":
        add(
            "cross_shot_diagnostic",
            "warn",
            f"Cross-shot coherence score {score}: {issues}.",
            severity="warning",
            penalty=10,
        )
    else:
        add("cross_shot_diagnostic", "pass", f"Cross-shot coherence passes with score {score}.")
    return diagnostic


def _check_references(
    add: Any,
    plan: DirectorPlan,
    reference_counts: dict[str, int],
    pinned_assets: list[dict[str, Any]],
) -> None:
    images = int(reference_counts.get("images") or 0)
    videos = int(reference_counts.get("videos") or 0)
    audios = int(reference_counts.get("audios") or 0)
    has_identity_contract = bool(plan.continuity_bible.characters or plan.continuity_bible.products)
    if has_identity_contract and images == 0:
        add("visual_reference_coverage", "warn", "Characters/products exist but there are no image references.", severity="warning", penalty=14)
    else:
        add("visual_reference_coverage", "pass", f"Image references available: {images}.")
    if images > 9:
        add("seedance_image_cap", "fail", "Image reference count exceeds Seedance 2.0 cap of 9.", severity="error", penalty=25)
    if videos > 3 or audios > 3:
        add("seedance_quad_modal_cap", "fail", "Video/audio reference count exceeds Seedance 2.0 cap.", severity="error", penalty=25)
    if pinned_assets:
        add("asset_pins", "pass", f"{len(pinned_assets)} approved asset pin(s) will be injected.")
    elif has_identity_contract and plan.continuity_bible.duration_s > 180:
        add("asset_pins", "warn", "Long-form identity/product job has no approved asset pins.", severity="warning", penalty=10)


def _check_reference_sufficiency(
    add: Any,
    *,
    plan: DirectorPlan,
    reference_counts: dict[str, int],
    target_market: str,
) -> dict[str, Any]:
    meta = plan.continuity_bible.storytelling_meta or {}
    runtime = meta.get("runtime_structure") or {}
    niche = str(
        (meta.get("niche_playbook") or {}).get("niche")
        or meta.get("niche")
        or plan.continuity_bible.intent
        or "unknown"
    )
    allocation = meta.get("seedance_reference_allocation") or {}
    existing = allocation.get("reference_sufficiency") if isinstance(allocation, dict) else None
    report = existing if isinstance(existing, dict) else build_reference_sufficiency_report(
        niche=niche,
        runtime_payload={**runtime, "target_market": target_market},
        reference_counts=reference_counts,
        has_dialogue=any(bool(getattr(shot.audio, "dialogue_vn", None)) for shot in plan.shot_list),
        target_market=target_market,
    )
    status = str(report.get("status") or "warn")
    detail = (
        f"Reference sufficiency {status}; score={report.get('score')}; "
        f"next={report.get('next_best_action')}"
    )
    if report.get("render_blocking"):
        add("reference_sufficiency", "fail", detail, severity="error", penalty=30)
    elif status == "warn":
        add("reference_sufficiency", "warn", detail, severity="warning", penalty=10)
    else:
        add("reference_sufficiency", "pass", detail)
    return report


def _check_script_asset_sop(
    add: Any,
    *,
    plan: DirectorPlan,
    runtime: dict[str, Any],
    niche: str,
    target_market: str,
    reference_counts: dict[str, int],
) -> dict[str, Any]:
    bible = plan.continuity_bible
    meta = bible.storytelling_meta or {}
    idea = str(
        meta.get("user_idea")
        or bible.logline
        or bible.title
        or " ".join(getattr(shot.visual, "action", "") for shot in plan.shot_list[:3])
    )
    has_dialogue = any(bool(getattr(shot.audio, "dialogue_vn", None)) for shot in plan.shot_list)
    sop = build_script_asset_sop(
        user_idea=idea,
        niche=niche,
        runtime_payload=runtime or {
            "runtime_class": "short_film" if int(bible.duration_s or 0) > 180 else "short",
            "target_duration_s": int(bible.duration_s or 0),
        },
        target_market=target_market,
        reference_counts=reference_counts,
        has_dialogue=has_dialogue,
    )
    if not sop.get("enabled"):
        add("script_asset_sop", "pass", "Short/simple route does not require a script asset SOP.")
        return sop

    missing = list(sop.get("missing_before_top_tier") or [])
    severe = {"character_visual_anchor", "location_visual_anchor", "product_or_prop_visual_anchor"}
    duration = int(bible.duration_s or 0)
    if duration > 180 and any(item in severe for item in missing):
        add(
            "script_asset_sop",
            "warn",
            "Long-form asset SOP is missing anchors: " + ", ".join(missing[:5]) + ".",
            severity="warning",
            penalty=12,
        )
    elif missing:
        add(
            "script_asset_sop",
            "warn",
            "Asset SOP recommends stronger anchors before top-tier claim: " + ", ".join(missing[:5]) + ".",
            severity="warning",
            penalty=6,
        )
    else:
        add("script_asset_sop", "pass", "Script asset SOP has enough anchors for this route.")
    return sop


def _check_model(add: Any, plan: DirectorPlan, resolved_model: str, model_violations: list[str]) -> None:
    if model_violations:
        hard = [v for v in model_violations if "max " in v or "out of range" in v]
        status = "fail" if hard else "warn"
        add("model_contract", status, "; ".join(model_violations[:5]), severity="error" if hard else "warning", penalty=25 if hard else 10)
    else:
        add("model_contract", "pass", f"Plan fits resolved model route {resolved_model}.")
    if plan.continuity_bible.duration_s > 600 and "seedance" in resolved_model:
        add("long_form_route", "warn", "Episode-scale Seedance job should use graph/chunk executor and benchmark evidence before production claim.", severity="warning", penalty=12)


def _check_niche_market(add: Any, niche: str, target_market: str, target_platform: str) -> None:
    readiness = _readiness_for_niche(niche)
    if readiness == "review_required":
        add("niche_safety_review", "warn", f"Niche {niche} requires claims/safety review.", severity="warning", penalty=12)
    elif readiness == "high":
        add("niche_readiness", "pass", f"Niche {niche} is high-readiness.")
    else:
        add("niche_readiness", "warn", f"Niche {niche} is usable but needs stronger benchmark evidence.", severity="warning", penalty=6)
    if not target_market:
        add("market", "warn", "Target market missing; localization may be generic.", severity="warning", penalty=4)
    else:
        add("market", "pass", f"Market route is {target_market}; platform is {target_platform}.")


def _check_seedance_shot_lint(add: Any, plan: DirectorPlan) -> dict[str, Any]:
    lint = lint_seedance_plan(bible=plan.continuity_bible, shots=plan.shot_list)
    if lint["status"] == "fail":
        add(
            "seedance_shot_lint",
            "fail",
            (
                f"{lint['failed_shot_count']} shot(s) fail Seedance pre-render lint; "
                f"top issues: {', '.join(lint.get('top_issues') or []) or 'none'}."
            ),
            severity="error",
            penalty=35,
        )
    elif lint["status"] == "warn":
        add(
            "seedance_shot_lint",
            "warn",
            (
                f"{lint['warned_shot_count']} shot(s) need prompt tightening; "
                f"top issues: {', '.join(lint.get('top_issues') or []) or 'none'}."
            ),
            severity="warning",
            penalty=10,
        )
    else:
        add("seedance_shot_lint", "pass", "All shots pass Seedance pre-render lint.")
    return lint


def _check_screenplay_scene_lint(
    add: Any,
    plan: DirectorPlan,
    runtime: dict[str, Any],
) -> dict[str, Any]:
    lint = lint_screenplay_scene_structure(
        duration_s=int(plan.continuity_bible.duration_s or 0),
        runtime_structure=runtime,
    )
    if lint["status"] == "fail":
        add(
            "screenplay_scene_lint",
            "fail",
            (
                f"{lint['failed_scene_count']} scene(s) fail long-form screenplay lint; "
                f"top issues: {', '.join(lint.get('top_issues') or []) or 'none'}."
            ),
            severity="error",
            penalty=35,
        )
    elif lint["status"] == "warn":
        add(
            "screenplay_scene_lint",
            "warn",
            (
                f"{lint['warned_scene_count']} scene(s) need stronger screenplay continuity; "
                f"top issues: {', '.join(lint.get('top_issues') or []) or 'none'}."
            ),
            severity="warning",
            penalty=10,
        )
    else:
        add("screenplay_scene_lint", "pass", "Screenplay/scene structure passes long-form lint.")
    return lint


def _readiness_for_niche(niche: str) -> str:
    try:
        matrix = build_niche_readiness_matrix()
        for row in matrix.get("niches") or []:
            if row.get("niche") == niche:
                return str(row.get("readiness") or "medium")
    except Exception:
        return "medium"
    return "medium"


def _is_review_required(niche: str) -> bool:
    return _readiness_for_niche(niche) == "review_required"


__all__ = ["build_autonomous_preflight_report"]
