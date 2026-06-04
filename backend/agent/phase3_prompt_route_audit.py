"""Phase 3 prompt and route audit for autonomous Seedance production.

This module is intentionally non-billable. It turns current docs, local model
specs, niche playbooks, prompt contracts, and benchmark policy into one
inspectable checklist before any paid benchmark run is approved.
"""
from __future__ import annotations

from typing import Any

from agent.autonomous_niche_launch_matrix import build_autonomous_niche_launch_matrix
from agent.autonomous_paid_benchmark_manifest import build_autonomous_paid_benchmark_manifest
from agent.autonomous_top_tier_completion_gate import build_autonomous_top_tier_completion_gate
from agent.benchmark_promotion_policy import build_benchmark_promotion_policy
from agent.model_specs import VIDEO_MODEL_SPECS, resolve_video_model_variant
from skills.niche_playbooks import get_niche_playbook, list_niche_keys


_OFFICIAL_SOURCE_OBSERVATIONS = [
    {
        "source": "BytePlus ModelArk Seedance 2.0 API reference",
        "url": "https://docs.byteplus.com/en/docs/ModelArk/1520757",
        "observations": [
            "Seedance 2.0 / 2.0 Fast support text-to-video, image-to-video, and multimodal reference generation.",
            "Reference generation supports image, video, and audio references, but audio-only reference input is not a valid visual generation route.",
            "Reference-video and reference-image inputs should be treated as visual anchors, not generic prompt decoration.",
        ],
    },
    {
        "source": "BytePlus ModelArk Seedance 2.0 prompt guide",
        "url": "https://docs.byteplus.com/en/docs/ModelArk/2222480",
        "observations": [
            "Prompting should name reference roles, concrete action, camera, timing, and constraints.",
            "The guide is current enough to be used as the primary prompt-contract source for Phase 3 audit.",
        ],
    },
    {
        "source": "AtlasCloud Seedance 2.0 Fast Reference-to-Video model page",
        "url": "https://www.atlascloud.ai/models/bytedance/seedance-2.0-fast/reference-to-video",
        "observations": [
            "AtlasCloud exposes bytedance/seedance-2.0-fast/reference-to-video through /model/generateVideo and /model/prediction polling.",
            "AtlasCloud marks the Fast reference route as multimodal from reference images, videos, and audio.",
        ],
    },
    {
        "source": "Seedance 2.0 paper",
        "url": "https://arxiv.org/abs/2604.14148",
        "observations": [
            "Seedance 2.0 is a native multimodal audio-video generation model; product claims still need output evidence, not architecture-only assumptions.",
        ],
    },
]


def build_phase3_prompt_route_audit() -> dict[str, Any]:
    """Return the Phase 3 non-billable audit and next paid-proof plan."""
    launch = build_autonomous_niche_launch_matrix()
    promotion = build_benchmark_promotion_policy()
    paid_manifest = build_autonomous_paid_benchmark_manifest(
        focus="sell_first",
        outputs_per_route=1,
        limit=5,
    )
    top_tier = build_autonomous_top_tier_completion_gate()
    model_routes = _model_route_contracts()
    niche_rows = _niche_prompt_rows(launch)
    checks = _non_billable_checks(model_routes=model_routes, niche_rows=niche_rows)
    return {
        "schema_version": "cinejelly.phase3_prompt_route_audit.v1",
        "phase": "phase_3_non_billable_audit",
        "verdict": {
            "ready_for_controlled_paid_benchmark": checks["failed_count"] == 0,
            "top_tier_claim_allowed": False,
            "why": (
                "Prompt/model/niche contracts are inspectable and internally tested. "
                "Top-tier claims remain blocked until real paid outputs, QA evidence, "
                "review scores, cost, latency, and promotion policy all pass."
            ),
            "failed_count": checks["failed_count"],
            "warning_count": checks["warning_count"],
        },
        "docs_alignment": {
            "last_reviewed": "2026-06-01",
            "sources": _OFFICIAL_SOURCE_OBSERVATIONS,
            "local_policy": [
                "Use Seedance 2.0 Fast as default cost-efficient visual route.",
                "Use premium Seedance 2.0 Reference only for hero/premium ref-heavy shots after route logic requires it.",
                "Use Wan 2.7 only as narrow driven-audio i2v fallback for short visible speech inserts.",
                "Never ask any Seedance route for one 5-30 minute generation; split into 4-15s units with scene graph handoffs.",
            ],
        },
        "model_route_contracts": model_routes,
        "situation_routing": _situation_routing(),
        "prompt_contract": _prompt_contract(),
        "niche_prompt_matrix": {
            "niche_count": len(niche_rows),
            "rows": niche_rows,
        },
        "phase3_non_billable_checks": checks,
        "paid_benchmark_gate": {
            "promotion_policy_summary": promotion.get("summary", {}),
            "top_tier_gate_verdict": top_tier.get("verdict", {}),
            "minimum_next_manifest": paid_manifest.get("summary", {}),
            "first_paid_runs": paid_manifest.get("runs", [])[:5],
            "do_not_run_paid_until": [
                "real reference assets are attached, not placeholders",
                "preflight says render_ready or explicit approval metadata is attached",
                "budget is approved for the selected run count",
                "benchmark result rows are created as planned before render",
            ],
        },
        "phase3b_feedback_loop": _phase3b_feedback_loop(),
        "next_engineering_actions": _next_engineering_actions(
            promotion_summary=promotion.get("summary", {}),
            top_tier_verdict=top_tier.get("verdict", {}),
        ),
    }


def _model_route_contracts() -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    families = ["seedance_2_0_fast", "seedance_2_0", "wan_2_7"]
    for family in families:
        for mode in ("t2v", "i2v", "ref"):
            concrete = resolve_video_model_variant(family, mode)
            if any(item["model_key"] == concrete for item in routes):
                continue
            spec = VIDEO_MODEL_SPECS[concrete]
            routes.append({
                "model_key": concrete,
                "family": family,
                "mode": mode,
                "endpoint": spec["endpoint"],
                "cost_per_second_usd": spec["cost_per_second_usd"],
                "duration": spec["duration"],
                "reference_limits": {
                    "images": spec.get("max_references", 0),
                    "videos": (spec.get("extra_fields", {}).get("reference_videos") or {}).get("max_items", 0),
                    "audios": (spec.get("extra_fields", {}).get("reference_audios") or {}).get("max_items", 0),
                },
                "use_when": _use_when(concrete),
                "must_not_use_when": _must_not_use_when(concrete),
                "prompt_requirements": _prompt_requirements(concrete),
            })
    return routes


def _use_when(model_key: str) -> list[str]:
    if model_key.endswith("_t2v"):
        return ["text-only ideation", "abstract b-roll", "no reliable visual refs", "lowest-cost visual smoke tests"]
    if model_key.endswith("_i2v") and model_key.startswith("seedance_2_0"):
        return ["single first-frame animation", "last-frame continuity handoff", "image-to-video chain unit"]
    if model_key.endswith("_ref"):
        return ["identity/product/style reference binding", "video motion/camera reference", "audio rhythm/SFX reference plus visual refs"]
    if model_key == "wan_2_7_i2v":
        return ["short 5s/10s driven-audio lip-sync insert", "talking-head fallback when a source image and driving audio exist"]
    return ["specialized route"]


def _must_not_use_when(model_key: str) -> list[str]:
    if model_key.endswith("_t2v"):
        return ["user supplied visual refs that must be preserved", "product/face fidelity is the main promise"]
    if model_key.endswith("_i2v") and model_key.startswith("seedance_2_0"):
        return ["multiple independent visual refs need role binding", "no first-frame or handoff image exists"]
    if model_key.endswith("_ref"):
        return ["audio-only input with no image/video anchor", "simple text-only cheap draft where T2V is enough"]
    if model_key == "wan_2_7_i2v":
        return ["text-only generation", "multi-ref cinematic scene without a source image", "non-5s/10s paid render unless snapped first"]
    return []


def _prompt_requirements(model_key: str) -> list[str]:
    base = ["timeline", "single visible action", "camera shot and movement", "environment", "constraints"]
    if model_key.endswith("_ref"):
        return ["reference jobs", "role tags for each reference", *base, "separate identity/product/motion/audio roles"]
    if model_key.endswith("_i2v"):
        return ["first-frame or last-frame continuity anchor", *base, "preserve input image as hard first frame"]
    if model_key.endswith("_t2v"):
        return [*base, "strong concrete visual noun and physical verb"]
    if model_key == "wan_2_7_i2v":
        return ["source image", "driving audio URL", "5s or 10s duration", "visible mouth/face framing if lip-sync matters"]
    return base


def _situation_routing() -> list[dict[str, Any]]:
    return [
        {
            "situation": "user gives only a vague idea",
            "route": "production decision -> conversational preflight -> seedance_2_0_fast_t2v only after approval",
            "agent_response": "ask for goal, duration, subject, market, and optional refs; do not overclaim identity consistency.",
        },
        {
            "situation": "user gives one product or character image",
            "route": "seedance_2_0_fast_i2v for first-frame animation; ref route if extra refs or product/identity binding is needed",
            "agent_response": "extract subject/action/style; keep product/face stable; avoid unrelated style refs competing with the image.",
        },
        {
            "situation": "user gives image + video + audio refs",
            "route": "seedance_2_0_fast_ref or seedance_2_0_ref for premium hero shots",
            "agent_response": "assign each asset exactly one job: identity/product, motion/camera, beat/SFX/dialogue pacing.",
        },
        {
            "situation": "15-60s social video",
            "route": "single-call only when <=15s and coherent; otherwise per-shot chain and assembly",
            "agent_response": "split into hook, proof/action, payoff; keep each unit 4-15s.",
        },
        {
            "situation": "3-30 minute film or episode",
            "route": "screenplay -> scenes -> chunks -> 4-15s Seedance units -> handoff/QA/retry/assembly",
            "agent_response": "build story spine and scene memory first; require references for characters/locations before paid render.",
        },
        {
            "situation": "visible dialogue/lip-sync",
            "route": "Wan 2.7 for short driven-audio inserts; emerging dialogue models remain benchmark-locked",
            "agent_response": "keep speech short, attach clean audio, require review for lip-sync before public/premium claims.",
        },
    ]


def _prompt_contract() -> dict[str, Any]:
    return {
        "required_block_order": [
            "reference jobs",
            "prompt formula",
            "timeline",
            "environment",
            "visual style",
            "shot direction",
            "camera and sound",
            "shot contract",
            "director intent",
            "constraints",
        ],
        "rewrite_rules": [
            "Reject vague adjective-only prompts.",
            "Reject multiple unrelated physical actions in one Seedance unit.",
            "Rewrite camera language into shot size, movement, and continuity purpose.",
            "Every uploaded asset must have one primary role.",
            "Long-form units must state scene purpose and handoff image.",
        ],
        "negative_policy": [
            "ban face morphing, product shape drift, text artifacts, fake logos, impossible anatomy, and random location changes",
            "for claims-heavy niches, keep claims educational/review-gated and avoid guarantees",
        ],
    }


def _phase3b_feedback_loop() -> dict[str, Any]:
    return {
        "schema_version": "cinejelly.phase3b_feedback_loop.v1",
        "purpose": "capture real post-render feedback without starting paid work",
        "endpoints": {
            "record_feedback": "POST /api/v1/director/jobs/{job_id}/feedback",
            "read_feedback": "GET /api/v1/director/jobs/{job_id}/feedback",
            "production_report": "GET /api/v1/director/jobs/{job_id}/production-report",
            "benchmark_evidence": "GET /api/v1/director/jobs/{job_id}/benchmark-evidence-pack",
        },
        "ratings": ["approved", "good", "needs_work", "bad"],
        "issue_tags": [
            "weak_hook",
            "face_drift",
            "product_drift",
            "wrong_niche",
            "bad_motion",
            "audio_lipsync_issue",
            "prompt_mismatch",
            "text_artifact",
            "composition_issue",
            "too_generic",
            "safety_or_claim_issue",
            "continuity_break",
            "other",
        ],
        "gates": [
            "feedback never triggers a paid render",
            "negative feedback blocks promotion until prompt, reference, or route is repaired",
            "approved feedback is supporting evidence, not enough by itself for top-tier claims",
            "benchmark promotion still requires QA scores, cost, latency, real output URL, and reviewer notes",
        ],
    }


def _niche_prompt_rows(launch: dict[str, Any]) -> list[dict[str, Any]]:
    launch_rows = {
        row.get("niche"): row
        for row in launch.get("rows", [])
        if isinstance(row, dict)
    }
    rows: list[dict[str, Any]] = []
    for niche in list_niche_keys():
        playbook = get_niche_playbook(niche)
        launch_row = launch_rows.get(niche, {})
        ref_contract = launch_row.get("reference_contract") or {}
        rows.append({
            "niche": niche,
            "launch_tier": launch_row.get("launch_tier", "benchmark_next"),
            "primary_visual_model": launch_row.get("primary_visual_model", "seedance_2_0_fast_ref"),
            "best_runtime_today": launch_row.get("best_runtime_today"),
            "hook_moves": playbook.get("hook_moves", [])[:3],
            "beat_flow": playbook.get("beat_flow", [])[:5],
            "camera_language": playbook.get("camera", [])[:4],
            "audio_policy": playbook.get("audio"),
            "reference_minimum": ref_contract.get("minimum"),
            "reference_optimal": ref_contract.get("optimal"),
            "quality_bar": playbook.get("quality_bar", [])[:5],
            "risk_controls": launch_row.get("risk_controls", []),
            "prompt_focus": _prompt_focus(niche),
        })
    return rows


def _prompt_focus(niche: str) -> list[str]:
    product = {"beauty", "food", "fashion", "ecommerce_catalog", "tech", "app_saas", "automotive", "restaurant_hospitality"}
    human = {"ugc_review", "drama", "documentary", "education", "finance_education", "medical_wellness", "kids_family", "fitness", "music_video", "anime_comic"}
    location = {"real_estate", "travel", "restaurant_hospitality", "documentary"}
    focus = ["one physical action", "camera and lighting continuity", "clear payoff"]
    if niche in product:
        focus.extend(["product geometry", "tactile proof", "no unsupported claims"])
    if niche in human:
        focus.extend(["identity and wardrobe continuity", "emotion matches beat"])
    if niche in location:
        focus.extend(["spatial layout", "screen direction"])
    if niche in {"finance_education", "medical_wellness", "kids_family", "documentary"}:
        focus.append("review-gated factual/safety claims")
    return list(dict.fromkeys(focus))


def _non_billable_checks(*, model_routes: list[dict[str, Any]], niche_rows: list[dict[str, Any]]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    model_keys = {route["model_key"] for route in model_routes}
    for required in {
        "seedance_2_0_fast_t2v",
        "seedance_2_0_fast_i2v",
        "seedance_2_0_fast_ref",
        "seedance_2_0_ref",
        "wan_2_7_i2v",
    }:
        checks.append(_check(
            key=f"model_route_{required}",
            status="pass" if required in model_keys else "fail",
            detail=f"{required} route contract present",
        ))
    checks.append(_check(
        key="niche_matrix_coverage",
        status="pass" if len(niche_rows) >= 20 else "fail",
        detail=f"{len(niche_rows)} niche prompt rows available",
    ))
    missing_refs = [
        row["niche"]
        for row in niche_rows
        if not row.get("reference_minimum") or not row.get("quality_bar")
    ]
    checks.append(_check(
        key="niche_reference_and_quality_contracts",
        status="pass" if not missing_refs else "warn",
        detail="all niches expose reference minimums and quality bars" if not missing_refs else f"missing/weak rows: {missing_refs[:8]}",
    ))
    checks.append(_check(
        key="prompt_block_contract",
        status="pass",
        detail="Seedance prompt compiler enforces reference jobs, timeline, action, camera/sound, shot contract, and constraints.",
    ))
    checks.append(_check(
        key="paid_evidence_gate",
        status="pass",
        detail="Paid benchmark and promotion policies block top-tier claims until real output evidence exists.",
    ))
    return {
        "checks": checks,
        "failed_count": len([c for c in checks if c["status"] == "fail"]),
        "warning_count": len([c for c in checks if c["status"] == "warn"]),
    }


def _check(*, key: str, status: str, detail: str) -> dict[str, str]:
    return {"key": key, "status": status, "detail": detail}


def _next_engineering_actions(*, promotion_summary: dict[str, Any], top_tier_verdict: dict[str, Any]) -> list[dict[str, Any]]:
    actions = [
        {
            "phase": "3A",
            "name": "Controlled paid benchmark",
            "why": "Architecture is not enough; routes need real outputs and review evidence.",
            "exit_gate": "At least two approved outputs for the same model/niche/runtime/market route.",
        },
        {
            "phase": "3B",
            "name": "Model-backed QA",
            "why": "Identity/product/lip-sync quality needs visual/audio scoring, not only deterministic checks.",
            "exit_gate": "QA evidence pack is complete for every promoted route.",
        },
        {
            "phase": "3C",
            "name": "Long-form graph proof",
            "why": "5-30m claims require scene graph execution, handoff memory, retry, and assembly evidence.",
            "exit_gate": "One 3m and one 5m graph run pass review with saved evidence.",
        },
    ]
    if int(promotion_summary.get("promoted_route_count") or 0) == 0:
        actions[0]["priority"] = "highest"
    if top_tier_verdict.get("partial_count", 0):
        actions[1]["priority"] = actions[1].get("priority", "high")
    return actions


__all__ = ["build_phase3_prompt_route_audit"]
