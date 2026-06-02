"""Conversational preflight contract for the autonomous Studio UI.

This is a vendor-free layer in front of paid rendering. It turns the existing
production decision into a user-facing chat state: ask only blocking questions,
draft the story/shot plan, and require explicit approval before render.
"""
from __future__ import annotations

import hashlib
import os
import re
from typing import Any

from agent.autonomous_production_decision import build_autonomous_production_decision

BLOCKING_STATUSES = {"blocked", "fail", "missing"}


def build_conversational_preflight(
    *,
    user_idea: str,
    target_market: str = "auto",
    target_platform: str = "tiktok",
    duration_hint_s: int | None = None,
    aspect_ratio: str | None = None,
    reference_counts: dict[str, int] | None = None,
    reference_image_urls: list[str] | None = None,
    reference_video_urls: list[str] | None = None,
    reference_audio_urls: list[str] | None = None,
    reference_manifest: dict[str, Any] | None = None,
    speaker_count: int = 1,
    approved: bool = False,
    edited_brief: str | None = None,
    revision_notes: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return the chat-ready preflight plan for an autonomous render."""
    conversation = _normalize_conversation_messages(conversation_messages or [])
    idea = _merge_idea_with_conversation((edited_brief or user_idea or "").strip(), conversation)
    revisions = (revision_notes or "").strip()
    decision_wrap = build_autonomous_production_decision(
        user_idea=idea,
        target_market=target_market,
        target_platform=target_platform,
        duration_hint_s=duration_hint_s,
        reference_counts=reference_counts or {},
        reference_image_urls=reference_image_urls or [],
        reference_video_urls=reference_video_urls or [],
        reference_audio_urls=reference_audio_urls or [],
        reference_manifest=reference_manifest or {},
        speaker_count=speaker_count,
    )
    decision = decision_wrap.get("decision") or {}
    creative_brief_contract = decision_wrap.get("creative_brief_contract") or {}
    creative_producer_v2 = decision_wrap.get("creative_producer_v2") or {}
    prompt_execution_contract_v3 = decision_wrap.get("prompt_execution_contract_v3") or {}
    viral_creative_brain = decision_wrap.get("viral_creative_brain") or {}
    output_qa_retry_brain = decision_wrap.get("output_qa_retry_brain") or {}
    selected_producer_angle = creative_producer_v2.get("selected_angle") or {}
    producer_shot_graph = creative_producer_v2.get("shot_graph") or {}
    prompt_contract_readiness = prompt_execution_contract_v3.get("readiness") or {}
    prompt_contract_model_plan = prompt_execution_contract_v3.get("model_plan") or {}
    viral_readiness = viral_creative_brain.get("readiness") or {}
    selected_viral_pattern = viral_creative_brain.get("selected_viral_pattern") or {}
    qa_retry_readiness = output_qa_retry_brain.get("readiness") or {}
    blockers = _blocking_questions(
        decision_wrap,
        idea=idea,
        duration_hint_s=duration_hint_s,
    )
    render_blocked = bool(blockers)
    status = (
        "needs_user_input"
        if render_blocked
        else "approved_for_render"
        if approved
        else "ready_for_approval"
    )
    creative_plan = _creative_plan(decision_wrap, idea, revisions)
    script = _script_outline(decision_wrap, creative_plan)
    storyboard = _storyboard(decision_wrap, creative_plan)
    distribution = _distribution_preview(decision_wrap, creative_plan=creative_plan, script=script)
    approval_checklist = _approval_checklist(
        decision_wrap,
        script=script,
        storyboard=storyboard,
        distribution=distribution,
        blockers=blockers,
    )
    assistant_message = _assistant_message(
        status=status,
        questions=blockers,
        creative_plan=creative_plan,
        decision=decision,
        revision_notes=revisions,
    )
    approved_brief = _build_approved_brief(
        idea=idea,
        revision_notes=revisions,
        creative_plan=creative_plan,
        script=script,
        storyboard=storyboard,
        distribution=distribution,
        reference_manifest=(decision_wrap.get("reference_context") or {}).get("reference_manifest") or reference_manifest or {},
        approval_checklist=approval_checklist,
        aspect_ratio=aspect_ratio,
        include_plan=bool(approved and not render_blocked),
    )
    approved_plan = _approved_plan_meta(
        approved_brief=approved_brief,
        render_ready=bool(approved and not render_blocked),
    )
    return {
        "schema_version": "cinejelly.conversational_preflight.v1",
        "status": status,
        "render_ready": bool(approved and not render_blocked),
        "approval_required": not render_blocked and not approved,
        "planning_trace": _planning_trace(decision_wrap),
        "assistant_message": assistant_message,
        "blocking_questions": blockers,
        "suggested_replies": _suggested_replies(blockers),
        "approved_brief": approved_brief,
        "approved_plan": approved_plan,
        "summary": {
            "niche": decision.get("niche"),
            "market": decision.get("target_market"),
            "target_platform": decision.get("target_platform") or target_platform,
            "aspect_ratio": aspect_ratio or "auto",
            "runtime_class": decision.get("runtime_class"),
            "target_duration_s": decision.get("target_duration_s"),
            "graph_required": decision.get("graph_required"),
            "primary_visual_model": (decision.get("primary_model_route") or {}).get("primary_visual_model"),
            "llm_brain_route": decision.get("llm_brain_route"),
            "brief_readiness": (creative_brief_contract.get("readiness") or {}).get("status"),
            "brief_completeness_score": (creative_brief_contract.get("readiness") or {}).get("completeness_score"),
            "producer_angle": selected_producer_angle.get("label"),
            "producer_angle_id": selected_producer_angle.get("angle_id"),
            "script_beat_count": len(creative_producer_v2.get("script_beats") or []),
            "shot_graph_node_count": producer_shot_graph.get("node_count"),
            "prompt_contract_status": prompt_contract_readiness.get("status"),
            "compiled_shot_count": prompt_contract_readiness.get("compiled_shot_count"),
            "prompt_contract_warning_count": prompt_contract_readiness.get("warning_count"),
            "prompt_primary_visual_model": prompt_contract_model_plan.get("primary_visual_model"),
            "viral_brain_status": viral_readiness.get("status"),
            "viral_creative_score": viral_readiness.get("creative_score"),
            "viral_pattern": selected_viral_pattern.get("label"),
            "viral_pattern_id": selected_viral_pattern.get("pattern_id"),
            "viral_hook_count": viral_readiness.get("hook_variant_count"),
            "output_qa_status": qa_retry_readiness.get("status"),
            "qa_confidence_score": qa_retry_readiness.get("qa_confidence_score"),
            "qa_node_count": qa_retry_readiness.get("qa_node_count"),
            "retry_recipe_count": qa_retry_readiness.get("retry_recipe_count"),
            "qa_warning_count": qa_retry_readiness.get("warning_count"),
        },
        "creative_brief_contract": creative_brief_contract,
        "creative_producer_v2": creative_producer_v2,
        "prompt_execution_contract_v3": prompt_execution_contract_v3,
        "viral_creative_brain": viral_creative_brain,
        "output_qa_retry_brain": output_qa_retry_brain,
        "creative_plan": creative_plan,
        "script_outline": script,
        "storyboard": storyboard,
        "input_suggestions": _input_suggestions(decision_wrap),
        "distribution_preview": distribution,
        "approval_checklist": approval_checklist,
        "conversation_context": _conversation_context(conversation),
        "production_decision": decision_wrap,
    }


def _planning_trace(decision_wrap: dict[str, Any]) -> dict[str, Any]:
    """Expose why preflight is fast and what has not been called yet."""
    llm_policy = decision_wrap.get("llm_brain_policy") or {}
    route_summary = llm_policy.get("route_summary") or {}
    return {
        "schema_version": "cinejelly.preflight_planning_trace.v1",
        "engine_mode": "deterministic_policy_preflight",
        "vendor_calls_performed": False,
        "llm_calls_performed": False,
        "paid_video_vendor_calls_allowed": False,
        "why_response_is_fast": (
            "Send builds a local rule/playbook preflight from repo policies. "
            "It does not call AtlasCloud LLM or paid video generation."
        ),
        "source_modules": [
            "creative_brief_contract",
            "creative_producer_v2",
            "seedance_reference_allocation",
            "prompt_execution_contract_v3",
            "viral_creative_brain",
            "output_qa_retry_brain",
        ],
        "planned_llm_route": {
            "primary_text_model": route_summary.get("primary_text_model"),
            "vision_model": route_summary.get("vision_model"),
            "pro_selected": bool(route_summary.get("pro_selected")),
            "premium_selected": bool(route_summary.get("premium_selected")),
            "cost_mode": route_summary.get("cost_mode"),
        },
        "next_live_vendor_stage": (
            "Only after explicit approval + render does the autonomous chain run live LLM planning "
            "and then paid video render."
        ),
    }


def _normalize_conversation_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in messages[-12:]:
        role = str(item.get("role") or "").strip().lower()
        text = str(item.get("text") or item.get("content") or "").strip()
        intent = str(item.get("intent") or item.get("kind") or "idea").strip().lower()
        if intent not in {"idea", "revision"}:
            intent = "idea"
        if text.lower().startswith("revision request:"):
            intent = "revision"
        if role not in {"user", "assistant"} or not text:
            continue
        out.append({"role": role, "text": text[:700], "intent": intent})
    return out


def _merge_idea_with_conversation(idea: str, conversation: list[dict[str, str]]) -> str:
    user_turns = [
        item["text"]
        for item in conversation
        if item["role"] == "user" and item.get("intent") != "revision"
    ]
    merged = idea
    normalized = merged.lower()
    for text in user_turns[-6:]:
        if text.lower() in normalized:
            continue
        candidate = f"{merged}\n{text}".strip() if merged else text
        if len(candidate) > 3000:
            break
        merged = candidate
        normalized = merged.lower()
    return merged[:3000].strip()


def _conversation_context(conversation: list[dict[str, str]]) -> dict[str, Any]:
    user_turns = [item["text"] for item in conversation if item["role"] == "user"]
    assistant_turns = [item["text"] for item in conversation if item["role"] == "assistant"]
    return {
        "message_count": len(conversation),
        "user_turn_count": len(user_turns),
        "assistant_turn_count": len(assistant_turns),
        "latest_user_turn": user_turns[-1] if user_turns else "",
        "context_window": conversation[-6:],
    }


def _build_approved_brief(
    *,
    idea: str,
    revision_notes: str,
    creative_plan: dict[str, Any],
    script: list[dict[str, Any]],
    storyboard: list[dict[str, str]],
    distribution: dict[str, Any],
    reference_manifest: dict[str, Any],
    approval_checklist: list[dict[str, str]],
    aspect_ratio: str | None,
    include_plan: bool,
) -> str:
    idea_limit = 480 if include_plan else 900
    sections = [f"User idea:\n{idea[:idea_limit]}".strip()]
    if aspect_ratio:
        sections.append(f"Output frame:\n{aspect_ratio}".strip())
    if revision_notes:
        sections.append(f"Revision focus:\n{revision_notes[:360]}".strip())
    if include_plan:
        plan_lines = [
            "Approved render plan:",
            f"Title: {_clip(str(creative_plan.get('title') or ''), 100)}",
            f"Logline: {_clip(str(creative_plan.get('logline') or creative_plan.get('viewer_promise') or ''), 220)}",
            f"Angle: {_clip(str(creative_plan.get('creative_angle') or ''), 140)}",
        ]
        scene_lines = [
            (
                f"- {_clip(str(item.get('beat') or f'Scene {idx + 1}'), 28)}"
                f"{_duration_suffix(item.get('duration_s'))}: "
                f"{_clip(str(item.get('purpose') or item.get('script') or 'story beat'), 42)}"
            )
            for idx, item in enumerate(script[:5])
            if item.get("duration_s") or item.get("purpose") or item.get("turn")
        ]
        beat_lines = [
            f"- {_clip(str(item.get('beat') or f'Beat {idx + 1}'), 28)}: {_clip(str(item.get('script') or item.get('purpose') or ''), 58)}"
            for idx, item in enumerate(script[:4])
        ]
        frame_lines = [
            f"- {_clip(str(item.get('frame') or f'Frame {idx + 1}'), 26)}: {_clip(str(item.get('visual') or ''), 54)}"
            for idx, item in enumerate(storyboard[:4])
        ]
        publishing_lines = [
            f"Hook: {_clip(str(distribution.get('hook_first_3s') or ''), 130)}",
            f"Caption: {_clip(str(distribution.get('caption_draft') or ''), 130)}",
            f"Title: {_clip(str(distribution.get('title_hint') or ''), 90)}",
            f"Cover: {_clip(str(distribution.get('cover_frame_cue') or ''), 100)}",
        ]
        hashtags = [
            str(tag).strip()
            for tag in (distribution.get("hashtags") or [])[:6]
            if str(tag).strip()
        ]
        if hashtags:
            publishing_lines.append(f"Hashtags: {' '.join(hashtags)}")
        sections.append("\n".join([line for line in plan_lines if line.strip()]))
        useful_publishing_lines = [
            line
            for line in publishing_lines
            if line.split(":", 1)[-1].strip()
        ]
        if useful_publishing_lines:
            sections.append("Publishing preview:\n" + "\n".join(useful_publishing_lines))
        manifest_lines = _reference_manifest_lines(reference_manifest)
        if manifest_lines:
            sections.append("Reference manifest:\n" + "\n".join(manifest_lines))
        check_lines = [
            f"- {_clip(str(item.get('label') or 'Check'), 28)}: {str(item.get('status') or 'review')}; {_clip(str(item.get('detail') or ''), 58)}"
            for item in approval_checklist[:6]
        ]
        if check_lines:
            sections.append("Render checks:\n" + "\n".join(check_lines))
        if scene_lines:
            sections.append("Scene map:\n" + "\n".join(scene_lines))
        if beat_lines:
            sections.append("Script beats:\n" + "\n".join(beat_lines))
        if frame_lines:
            sections.append("Storyboard frames:\n" + "\n".join(frame_lines))

    return _clip_multiline("\n\n".join(section for section in sections if section), 1950)


def _approved_plan_meta(*, approved_brief: str, render_ready: bool) -> dict[str, Any]:
    source_hash = hashlib.sha256(approved_brief.encode("utf-8")).hexdigest()
    return {
        "id": f"plan_{source_hash[:16]}",
        "source_hash": source_hash,
        "source_length": len(approved_brief),
        "included_in_render_source": bool(render_ready),
    }


def _clip(value: str, limit: int) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def _clip_multiline(value: str, limit: int) -> str:
    value = "\n".join(line.rstrip() for line in value.splitlines()).strip()
    value = re.sub(r"\n{3,}", "\n\n", value)
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def _reference_manifest_lines(manifest: dict[str, Any]) -> list[str]:
    items = manifest.get("items") if isinstance(manifest, dict) else []
    if not isinstance(items, list):
        return []
    lines: list[str] = []
    for item in items[:12]:
        if not isinstance(item, dict):
            continue
        tag = str(item.get("tag") or "").strip()
        role = str(item.get("role") or "unknown").strip()
        binding = str(item.get("prompt_binding") or "").strip()
        confirmed = "confirmed" if item.get("role_confirmed") else "needs_review"
        name = str(item.get("name") or "").strip()
        if not tag:
            continue
        detail = binding or f"{tag} = {role}"
        if name:
            detail = f"{detail} ({_clip(name, 48)})"
        lines.append(f"- {detail}; status={confirmed}")
    if lines:
        lines.append("Rule: do not swap product, character, style, camera, motion, beat, SFX or voice roles across references.")
    return lines


def _duration_suffix(value: Any) -> str:
    try:
        duration = int(value)
    except (TypeError, ValueError):
        return ""
    return f" ({duration}s)"


def _blocking_questions(
    decision_wrap: dict[str, Any],
    *,
    idea: str,
    duration_hint_s: int | None,
) -> list[dict[str, Any]]:
    decision = decision_wrap.get("decision") or {}
    questions: list[dict[str, Any]] = []
    questions.extend(_missing_brief_questions(idea=idea, duration_hint_s=duration_hint_s))
    if decision.get("niche_resolution_review_required"):
        resolution = (decision_wrap.get("input_summary") or {}).get("niche_resolution") or {}
        for idx, question in enumerate(resolution.get("clarifying_questions") or []):
            q = str(question)
            questions.append(_question(
                question_id=f"niche_{idx + 1}",
                question=q,
                why="The agent needs one clear production intent before paid rendering.",
                replies=_niche_reply_options(q),
            ))
    gate = decision_wrap.get("responsible_content_gate") or {}
    if gate.get("render_allowed") is False:
        guidance = (gate.get("rewrite_guidance") or ["Rewrite the brief without unverified likeness, voice, or IP use."])[0]
        questions.append(_question(
            question_id="responsible_rewrite",
            question=str(guidance),
            why="Paid rendering is blocked until the brief is safe to generate.",
            replies=[
                "Rewrite with fictional characters, owned references, and no real-person likeness.",
                "Keep the same story goal, but use an original character and original brand assets.",
            ],
        ))
    questions.extend(_execution_blocking_questions(decision_wrap, duration_hint_s=duration_hint_s))
    questions.extend(_reference_blocking_questions(decision_wrap, duration_hint_s=duration_hint_s))
    return questions[:3]


def _execution_blocking_questions(
    decision_wrap: dict[str, Any],
    *,
    duration_hint_s: int | None,
) -> list[dict[str, Any]]:
    gate = decision_wrap.get("long_form_execution_gate") or {}
    if _gate_status(gate.get("status")) != "blocked":
        return []
    if _long_form_graph_can_be_built_at_render(gate):
        return []
    detail = "The long-form route needs continuity planning, scene memory, and resumable shot QA before paid render."
    target = int(duration_hint_s or (decision_wrap.get("decision") or {}).get("target_duration_s") or 0)
    return [_question(
        question_id="long_form_execution_blocked",
        question="This long video needs the long-form production route before it can render safely. Switch to a short trailer now or prepare the missing long-form inputs?",
        why=detail,
        replies=[
            "Switch this to a 30s vertical trailer first.",
            f"Keep the {target or 300}s blueprint and add the missing long-form references before render.",
            "Keep this as a story blueprint; do not render until the long-form route is ready.",
        ],
    )]


def _reference_blocking_questions(
    decision_wrap: dict[str, Any],
    *,
    duration_hint_s: int | None,
) -> list[dict[str, Any]]:
    input_plan = decision_wrap.get("autonomous_input_upgrade_plan") or {}
    missing = input_plan.get("missing_minimum") or {}
    missing_total = sum(
        int(value or 0)
        for key, value in missing.items()
        if key in {"images", "videos", "audios", "pinned_assets"}
    )
    target_duration = int(duration_hint_s or (decision_wrap.get("decision") or {}).get("target_duration_s") or 0)
    if missing_total <= 0 or (target_duration < 180 and input_plan.get("renderable_now", True)):
        return []
    actions = [
        str(item.get("action") or "").strip()
        for item in input_plan.get("priority_actions") or []
        if str(item.get("priority") or "").lower() == "required" and str(item.get("action") or "").strip()
    ]
    action_text = "; ".join(actions[:2]) or "Add the missing visual or motion references."
    return [_question(
        question_id="reference_minimum_missing",
        question="This plan is missing the minimum references needed for a consistent render. Add references or reduce the scope before approval?",
        why=action_text,
        replies=[
            "I will add the missing character, product, location, or motion references first.",
            "Reduce this to a 30s trailer that can render with fewer references.",
            "Use existing asset memory pins for the missing anchors.",
        ],
    )]


def _missing_brief_questions(*, idea: str, duration_hint_s: int | None) -> list[dict[str, Any]]:
    normalized = " ".join(idea.lower().split())
    words = [
        word.strip(".,:;!?()[]{}\"'")
        for word in normalized.split()
        if len(word.strip(".,:;!?()[]{}\"'")) > 2
    ]
    if len(words) < 4:
        return [_question(
            question_id="brief_core_missing",
            question="What is the specific product, topic, character, or story outcome this video must sell?",
            why="A paid render needs one concrete subject and one viewer payoff.",
            replies=[
                "Product: [name]. Audience: [who]. Payoff: [visible result].",
                "Story: [character]. Conflict: [problem]. Ending: [transformation].",
                "Topic: [subject]. Viewer should understand [outcome] in the first 30 seconds.",
            ],
        )]

    target_duration = duration_hint_s or 0
    if target_duration >= 180:
        story_signals = (
            "story",
            "drama",
            "film",
            "character",
            "conflict",
            "episode",
            "script",
            "plot",
            "phim",
            "kich",
            "nhan vat",
            "cot truyen",
        )
        has_story_signal = any(signal in normalized for signal in story_signals)
        if len(words) < 16 and not has_story_signal:
            return [_question(
                question_id="long_form_story_missing",
                question="For this long video, what main character, conflict, or transformation should drive the story?",
                why="Long-form renders need a narrative spine before the agent splits scenes and continuity anchors.",
                replies=[
                    "Main character is [who], conflict is [problem], transformation is [final change].",
                    "Treat this as [niche]. Act 1: [setup]. Act 2: [escalation]. Ending: [payoff].",
                    "Keep these anchors consistent: character [name], location [place], proof/payoff [result].",
                ],
            )]

    return []


def _question(*, question_id: str, question: str, why: str, replies: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": question_id,
        "question": question,
        "why": why,
        "suggested_replies": replies or [],
    }


def _suggested_replies(questions: list[dict[str, Any]]) -> list[str]:
    replies: list[str] = []
    for question in questions:
        for reply in question.get("suggested_replies") or []:
            text = str(reply).strip()
            if text and text not in replies:
                replies.append(text)
            if len(replies) >= 4:
                return replies
    return replies


def _niche_reply_options(question: str) -> list[str]:
    normalized = " ".join(question.strip().rstrip("?").split())
    match = re.search(r"primarily as (.+)$", normalized, flags=re.IGNORECASE)
    if not match:
        return []
    raw = match.group(1)
    choices = [
        choice.strip(" .")
        for choice in re.split(r",|\bor\b", raw)
        if choice.strip(" .")
    ]
    return [f"Treat this primarily as {choice}." for choice in choices[:3]]


def _creative_plan(decision_wrap: dict[str, Any], idea: str, revision_notes: str = "") -> dict[str, Any]:
    decision = decision_wrap.get("decision") or {}
    producer = decision_wrap.get("creative_producer_v2") or {}
    selected_angle = producer.get("selected_angle") or {}
    continuity_seed = producer.get("continuity_bible_seed") or {}
    treatment = _selected_treatment(decision_wrap.get("creative_treatment_search") or {})
    preview = decision_wrap.get("long_form_scene_preview") or {}
    recipe = decision_wrap.get("niche_production_recipe") or {}
    director = recipe.get("director_recipe") or {}
    runtime = str(decision.get("runtime_class") or "short").replace("_", " ")
    niche = str(decision.get("niche") or "story").replace("_", " ")
    logline = preview.get("logline") or treatment.get("director_intent") or idea
    promise = (
        selected_angle.get("story_engine")
        or
        preview.get("editor_promise")
        or director.get("story_engine")
        or "Hook fast, prove the idea visually, and close with a memorable payoff."
    )
    plan = {
        "title": continuity_seed.get("title_seed") or _title_from(niche=niche, runtime=runtime, idea=idea),
        "logline": logline,
        "creative_angle": selected_angle.get("label") or treatment.get("label") or f"{niche} autonomous treatment",
        "viewer_promise": promise,
        "tone": director.get("tone") or "cinematic, direct, emotionally clear",
        "runtime": runtime,
        "producer_id": producer.get("producer_id"),
        "producer_angle_id": selected_angle.get("angle_id"),
    }
    if revision_notes:
        plan["revision_directive"] = revision_notes[:500]
        plan["viewer_promise"] = f"{promise} Revision focus: {revision_notes[:240]}"
    return plan


def _script_outline(decision_wrap: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, Any]]:
    producer = decision_wrap.get("creative_producer_v2") or {}
    producer_beats = producer.get("script_beats") or []
    if producer_beats:
        return _ensure_min_beats([
            {
                "beat": beat.get("beat") or beat.get("beat_id") or f"Beat {idx + 1}",
                "duration_s": beat.get("duration_s"),
                "purpose": beat.get("purpose") or "story beat",
                "script": beat.get("script") or plan["viewer_promise"],
                "turn": beat.get("turn") or beat.get("retention_device") or "Advance the viewer to the next beat.",
            }
            for idx, beat in enumerate(producer_beats[:8])
        ], plan)
    preview = decision_wrap.get("long_form_scene_preview") or {}
    scenes = preview.get("scene_blueprints") or []
    if scenes:
        return _ensure_min_beats([
            {
                "beat": scene.get("scene_id") or f"Scene {idx + 1}",
                "duration_s": scene.get("duration_s"),
                "purpose": scene.get("purpose") or "story beat",
                "script": scene.get("dramatic_question") or scene.get("visual_hook") or plan["viewer_promise"],
                "turn": scene.get("turning_point") or scene.get("handoff_to_next") or "Advance the viewer to the next beat.",
            }
            for idx, scene in enumerate(scenes[:8])
        ], plan)
    segment_inspector = decision_wrap.get("seedance_segment_inspector") or {}
    segments = segment_inspector.get("segments") or []
    if segments:
        return _ensure_min_beats([
            {
                "beat": segment.get("segment_id") or f"Beat {idx + 1}",
                "duration_s": segment.get("duration_s"),
                "purpose": segment.get("shot_type") or "visual proof",
                "script": segment.get("prompt_blocks", {}).get("action") or plan["viewer_promise"],
                "turn": segment.get("hook_or_turn") or "Keep the visual promise moving.",
            }
            for idx, segment in enumerate(segments[:6])
        ], plan)
    return _ensure_min_beats([
        {"beat": "Hook", "duration_s": 3, "purpose": "attention", "script": plan["logline"], "turn": "Open with the most concrete visual."},
        {"beat": "Proof", "duration_s": 12, "purpose": "value", "script": plan["viewer_promise"], "turn": "Show the mechanism, not just the claim."},
        {"beat": "Payoff", "duration_s": 6, "purpose": "memory", "script": "End with a clear result and publishable caption angle.", "turn": "Close on the strongest frame."},
    ], plan)


def _ensure_min_beats(beats: list[dict[str, Any]], plan: dict[str, Any]) -> list[dict[str, Any]]:
    fallback = [
        {"beat": "Hook", "duration_s": 3, "purpose": "attention", "script": plan["logline"], "turn": "Open with the most concrete visual."},
        {"beat": "Proof", "duration_s": 12, "purpose": "value", "script": plan["viewer_promise"], "turn": "Show the mechanism, not just the claim."},
        {"beat": "Payoff", "duration_s": 6, "purpose": "memory", "script": "End with a clear result and publishable caption angle.", "turn": "Close on the strongest frame."},
    ]
    out = list(beats)
    existing = {str(item.get("beat") or "").lower() for item in out}
    for item in fallback:
        if len(out) >= 3:
            break
        if str(item["beat"]).lower() not in existing:
            out.append(item)
    return out


def _storyboard(decision_wrap: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, str]]:
    producer = decision_wrap.get("creative_producer_v2") or {}
    nodes = ((producer.get("shot_graph") or {}).get("nodes") or [])[:8]
    if nodes:
        return [
            {
                "id": str(node.get("shot_id") or f"shot_{idx + 1}"),
                "frame": str(node.get("beat_id") or node.get("purpose") or f"Shot {idx + 1}"),
                "visual": str(node.get("visual_intent") or node.get("script") or plan["viewer_promise"]),
                "camera": str(node.get("camera_intent") or _camera_for(idx, len(nodes))),
                "audio": "VO/dialogue follows market language; music and SFX support the beat.",
            }
            for idx, node in enumerate(nodes)
        ]
    script = _script_outline(decision_wrap, plan)
    out: list[dict[str, str]] = []
    for idx, beat in enumerate(script[:8]):
        out.append({
            "id": f"board_{idx + 1}",
            "frame": str(beat.get("beat") or f"Beat {idx + 1}"),
            "visual": str(beat.get("script") or plan["viewer_promise"]),
            "camera": _camera_for(idx, len(script)),
            "audio": "VO/dialogue follows market language; music and SFX support the beat.",
        })
    return out


def _input_suggestions(decision_wrap: dict[str, Any]) -> list[dict[str, str]]:
    plan = decision_wrap.get("autonomous_input_upgrade_plan") or {}
    actions = plan.get("priority_actions") or []
    return [
        {
            "priority": str(item.get("priority") or "recommended"),
            "action": str(item.get("action") or item.get("kind") or "Improve input"),
            "why": str(item.get("why") or "Improves quality before render."),
        }
        for item in actions[:4]
    ]


def _approval_checklist(
    decision_wrap: dict[str, Any],
    *,
    script: list[dict[str, Any]],
    storyboard: list[dict[str, str]],
    distribution: dict[str, Any],
    blockers: list[dict[str, Any]],
) -> list[dict[str, str]]:
    decision = decision_wrap.get("decision") or {}
    input_plan = decision_wrap.get("autonomous_input_upgrade_plan") or {}
    long_form_gate = decision_wrap.get("long_form_execution_gate") or {}
    suggestions = _input_suggestions(decision_wrap)
    has_publishing = bool(
        distribution.get("hook_first_3s")
        and distribution.get("caption_draft")
        and distribution.get("hashtags")
    )
    checklist = [
        {
            "key": "creative_intent",
            "label": "Creative intent",
            "status": "blocked" if blockers else "ready",
            "detail": blockers[0]["question"] if blockers else "Niche, market, runtime and viewer payoff are resolved.",
        },
        {
            "key": "script_blueprint",
            "label": "Script blueprint",
            "status": "ready" if len(script) >= 3 else "blocked",
            "detail": f"{len(script)} beat plan prepared before render.",
        },
        {
            "key": "storyboard",
            "label": "Storyboard",
            "status": "ready" if len(storyboard) >= 3 else "blocked",
            "detail": f"{len(storyboard)} visual frame cues prepared for generation.",
        },
        {
            "key": "publishing",
            "label": "Publishing package",
            "status": "ready" if has_publishing else "recommended",
            "detail": "Hook, caption, cover cue and hashtags are drafted.",
        },
        {
            "key": "execution_route",
            "label": "Execution route",
            "status": _execution_route_status(decision, long_form_gate),
            "detail": _execution_check_detail(decision, long_form_gate),
        },
        {
            "key": "references",
            "label": "References",
            "status": "ready" if input_plan.get("renderable_now", True) else "blocked",
            "detail": _reference_check_detail(input_plan, suggestions),
        },
    ]
    return checklist


def _gate_status(value: Any) -> str:
    status = str(value or "ready").lower()
    if status == "pass":
        return "ready"
    if status in {"warn", "review"}:
        return "recommended"
    if status in BLOCKING_STATUSES:
        return "blocked"
    return status


def _execution_route_status(decision: dict[str, Any], long_form_gate: dict[str, Any]) -> str:
    if decision.get("graph_required") and _long_form_graph_can_be_built_at_render(long_form_gate):
        return "ready"
    return _gate_status(long_form_gate.get("status") or ("ready" if not decision.get("graph_required") else "recommended"))


def _long_form_graph_can_be_built_at_render(long_form_gate: dict[str, Any]) -> bool:
    blockers = set(str(item) for item in (long_form_gate.get("blockers") or []))
    generated_during_render = {"production_graph", "scene_memory_pack"}
    return bool(
        blockers
        and blockers.issubset(generated_during_render)
        and _graph_long_form_enabled()
    )


def _graph_long_form_enabled() -> bool:
    return os.getenv("CINEJELLY_ENABLE_GRAPH_LONG_FORM", "").strip().lower() in {"1", "true", "yes", "on"}


def _reference_check_detail(input_plan: dict[str, Any], suggestions: list[dict[str, str]]) -> str:
    counts = input_plan.get("current_reference_counts") or {}
    base = (
        f"{int(counts.get('images') or 0)} image, "
        f"{int(counts.get('videos') or 0)} video, "
        f"{int(counts.get('audios') or 0)} audio references attached."
    )
    if suggestions:
        return f"{base} Suggested: {suggestions[0]['action']}"
    return base


def _execution_check_detail(decision: dict[str, Any], long_form_gate: dict[str, Any]) -> str:
    if decision.get("graph_required"):
        if _long_form_graph_can_be_built_at_render(long_form_gate):
            return "Long-form production route is ready; continuity memory and resumable shot tasks will be built during autonomous render."
        contract = long_form_gate.get("execution_contract") or {}
        scene_count = contract.get("scene_count") or 0
        shot_count = contract.get("shot_count") or contract.get("graph_shot_count") or 0
        return f"Long-form production route needs continuity memory across {scene_count} scene(s) and {shot_count} shot unit(s)."
    duration = decision.get("target_duration_s") or "auto"
    return f"Short-form autonomous route prepared for {duration}s target."


def _distribution_preview(
    decision_wrap: dict[str, Any],
    *,
    creative_plan: dict[str, Any],
    script: list[dict[str, Any]],
) -> dict[str, Any]:
    package = decision_wrap.get("distribution_package") or {}
    viral = decision_wrap.get("viral_creative_brain") or {}
    viral_package = viral.get("platform_package") or {}
    viral_hooks = viral.get("hook_variants") or []
    playbook = decision_wrap.get("market_playbook") or {}
    decision = decision_wrap.get("decision") or {}
    niche = str(decision.get("niche") or "video").replace("_", " ")
    market = str(decision.get("target_market") or playbook.get("target_market") or "global")
    title = (viral_package.get("title_variants") or [None])[0] or package.get("title_hint") or creative_plan.get("title")
    hook = (
        str((viral_hooks[0] or {}).get("first_3s_line") or "")
        if viral_hooks
        else _clip(str((script[0] or {}).get("script") or creative_plan.get("logline") or ""), 160)
        if script
        else ""
    )
    caption = viral_package.get("caption_draft") or package.get("caption_primary") or _caption_draft(
        title=str(title or ""),
        promise=str(creative_plan.get("viewer_promise") or creative_plan.get("logline") or ""),
        market=market,
    )
    return {
        "caption_language": playbook.get("caption_language") or playbook.get("primary_language"),
        "hook_style": playbook.get("hook_style"),
        "hook_first_3s": hook,
        "caption_draft": caption,
        "title_hint": title,
        "cover_frame_cue": viral_package.get("cover_frame_cue") or package.get("cover_frame_cue") or "Use the clearest proof/payoff frame.",
        "hashtags": viral_package.get("hashtags") or package.get("hashtag_primary") or _fallback_hashtags(niche=niche, market=market),
        "cta": viral_package.get("cta"),
        "viral_pattern": (viral.get("selected_viral_pattern") or {}).get("label"),
    }


def _caption_draft(*, title: str, promise: str, market: str) -> str:
    base = _clip(promise or title or "A clear story with a strong visual payoff.", 150)
    if market == "vn":
        return f"{base} Xem den cuoi de thay ket qua."
    return f"{base} Watch to the end for the payoff."


def _fallback_hashtags(*, niche: str, market: str) -> list[str]:
    tags = ["#aivideo", "#storytelling", f"#{_hashtag_slug(niche)}"]
    if market == "vn":
        tags.insert(0, "#xuhuong")
    elif market not in {"auto", "global"}:
        tags.insert(0, f"#{_hashtag_slug(market)}")
    return [tag for tag in tags if tag and tag != "#"][:6]


def _hashtag_slug(value: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "" for ch in value)
    return out or "video"


def _selected_treatment(search: dict[str, Any]) -> dict[str, Any]:
    selected_id = search.get("selected_treatment_id")
    for item in search.get("candidates") or []:
        if item.get("treatment_id") == selected_id:
            return item
    candidates = search.get("candidates") or []
    return candidates[0] if candidates else {}


def _title_from(*, niche: str, runtime: str, idea: str) -> str:
    words = [word.strip(".,:;!?") for word in idea.split() if len(word.strip(".,:;!?")) > 2]
    if words:
        return " ".join(words[:7])[:80]
    return f"{niche.title()} {runtime.title()} Video"


def _camera_for(index: int, total: int) -> str:
    if index == 0:
        return "tight hook frame, immediate motion, no slow intro"
    if index == total - 1:
        return "clean payoff frame with a memorable final composition"
    return "controlled cinematic movement with continuity to the next beat"


def _assistant_message(
    *,
    status: str,
    questions: list[dict[str, Any]],
    creative_plan: dict[str, Any],
    decision: dict[str, Any],
    revision_notes: str = "",
) -> str:
    if status == "needs_user_input":
        return questions[0]["question"] if questions else "I need one detail before building the render plan."
    if status == "approved_for_render":
        return "Approved. I can render this plan now."
    runtime = str(decision.get("runtime_class") or creative_plan.get("runtime") or "video").replace("_", " ")
    if revision_notes:
        return (
            f"I revised the {runtime} plan around your notes. "
            "Review the updated script and storyboard, then approve to render."
        )
    return (
        f"I drafted a {runtime} plan: {creative_plan.get('creative_angle')}. "
        "Review the script and storyboard, edit the brief if needed, then approve to render."
    )


__all__ = ["build_conversational_preflight"]
