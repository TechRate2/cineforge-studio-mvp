"""Director Agent V3 — Layer 1.

Pipeline:
    1. Build input bundle (brief + context + refs + tech_config + trends)
    2. Vision-pass on reference_images → role detection (single LLM call)
    3. Director LLM call: take bundle → JSON DirectorPlan (Continuity Bible + Shot List + Storyboard Grid)
    4. Continuity validation + auto-chain + storyboard fill
    5. Evaluation Layer self-score
    6. Return DirectorPlan ready cho user duyệt

KHÔNG có template hardcoded. KHÔNG có persona chain linear.
Toàn bộ creative output từ 1 hệ thống prompt + JSON schema mạnh.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Callable, Awaitable

from loguru import logger
from pydantic import ValidationError

from agent.schemas import (
    DirectorPlan, ContinuityBible, Shot, StoryboardFrame,
    EvaluationReport, CostEstimate, ReferenceAsset,
)
from agent import continuity_manager
from agent.evaluation_layer import evaluate_plan
from system_prompts import load as load_system_prompt
from vendors.llm_router import llm


ProgressCallback = Optional[Callable[[dict], Awaitable[None]]]


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_fences(text: str) -> str:
    """LLM hay quên rule "no fences" — strip ```json ... ``` if present."""
    return _JSON_FENCE_RE.sub("", text).strip()


def _safe_parse_json(text: str) -> dict:
    """Best-effort parse — strip fences, find first { ... last }."""
    text = _strip_fences(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Find first { and last } and retry
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError as e:
                logger.error(f"[DirectorAgent] JSON parse fail after brace-trim: {e}")
                raise
        raise


class DirectorAgent:
    """V3 dynamic Director — outputs DirectorPlan."""

    async def plan(
        self,
        product_input: dict,
        reference_images: list[str],
        reference_videos: list[str],
        user_brief: str,
        context_injection: dict,
        tech_config: dict,
        niche_hint: Optional[str] = None,
        reference_role_hints: Optional[list[Optional[str]]] = None,
        progress_callback: ProgressCallback = None,
    ) -> DirectorPlan:
        """Main entry — return validated DirectorPlan.

        Args:
            reference_role_hints: Optional per-image role pre-tags (same length
                as `reference_images`). When supplied, the vision-pass is
                skipped and these tags are used directly as the role hint
                fed into the Director LLM. Saves ~1 LLM call.
        """

        # ===== Stage 0 (V3 C2 fix): Sanitize untrusted user inputs =====
        # User-provided `context_injection` fields (pain_points / real_reviews /
        # usps / forbidden_to_say / mood_hint) go straight into the LLM prompt.
        # Without sanitization they can carry prompt injection ("ignore previous
        # instructions") or PII (VN phone / email / CCCD) that the model
        # shouldn't see or echo back. Wire it here BEFORE the Director call.
        # Also sanitize `user_brief` and `niche_hint` which flow into prompt.
        from core.sanitize import (
            sanitize_context_injection, sanitize_prompt_injection, strip_pii,
        )
        try:
            ctx_clean, ctx_report = sanitize_context_injection(context_injection or {})
            if ctx_report.get("flagged_injections"):
                logger.warning(
                    f"[DirectorAgent] context_injection neutralized: "
                    f"{ctx_report['flagged_injections'][:3]}"
                )
            if ctx_report.get("pii_counts"):
                logger.info(f"[DirectorAgent] context PII redacted: {ctx_report['pii_counts']}")
            context_injection = ctx_clean
            brief_clean, brief_flagged = sanitize_prompt_injection(user_brief or "")
            brief_clean, _ = strip_pii(brief_clean)
            if brief_flagged:
                logger.warning(f"[DirectorAgent] user_brief neutralized: {brief_flagged[:3]}")
            user_brief = brief_clean
            if niche_hint:
                niche_clean, _ = sanitize_prompt_injection(niche_hint)
                niche_hint = niche_clean
        except Exception as e:
            # Sanitization must never block render — log and proceed with originals
            logger.warning(f"[DirectorAgent] sanitization fail (continuing): {e}")

        async def _emit(stage: str, status: str, **extra) -> None:
            if progress_callback is None:
                return
            event = {"stage": stage, "status": status, **extra}
            try:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(event)
                else:
                    progress_callback(event)  # type: ignore[misc]
            except Exception as e:
                logger.warning(f"[DirectorAgent] progress_cb fail: {e}")

        t_start = time.time()
        plan_id = f"dp_{uuid.uuid4().hex[:12]}"
        logger.info(
            f"[DirectorAgent] plan {plan_id} start — duration={tech_config.get('duration_s')}s, "
            f"refs={len(reference_images)}, niche_hint={niche_hint}"
        )

        # Sprint2 M15 — warn explicitly when no reference images uploaded.
        # Without refs the render falls back to text-to-video (t2v), which is
        # ~2× slower + ~1.3× more expensive than ref-to-video for the same
        # output quality. Users often upload nothing by accident.
        if not reference_images:
            logger.warning(
                f"[DirectorAgent] plan {plan_id} has NO reference_images — "
                f"render will fall back to text-to-video (slower + costlier). "
                f"Upload product / character refs at /studio for ~1.3× cheaper "
                f"+ better identity consistency."
            )

        await _emit("init", "running", plan_id=plan_id)
        if not reference_images:
            # Surface to UI so user sees the warning in DirectorPlanModal status
            await _emit(
                "warning", "info",
                code="no_reference_images",
                message="No reference images — render will use text-to-video (slower + ~1.3× costlier).",
            )

        # ===== Stage A: ref role classification =====
        # Prefer user-supplied role hints (from the 3-zone uploader in Studio V4)
        # — skips an LLM vision call. Fall back to vision pass when hints absent.
        ref_hints: list[dict] = []
        if reference_images:
            if reference_role_hints and any(h for h in reference_role_hints):
                ref_hints = [
                    {"index": i, "role": (reference_role_hints[i] or "unknown")
                                          if i < len(reference_role_hints) else "unknown",
                     "notes": "user-tagged"}
                    for i in range(len(reference_images))
                ]
                await _emit("vision", "done", classified=len(ref_hints), source="user_tagged")
                logger.info(f"[DirectorAgent] using {len(ref_hints)} user-tagged role hints — skip vision scan")
            else:
                await _emit("vision", "running", message="Scanning reference images")
                try:
                    ref_hints = await asyncio.to_thread(
                        self._vision_scan_refs, reference_images,
                    )
                except Exception as e:
                    logger.warning(f"[DirectorAgent] vision scan fail (continuing): {e}")
                    ref_hints = []
                await _emit("vision", "done", classified=len(ref_hints), source="vision_llm")

        # ===== Stage B: Build prompt context for Director LLM =====
        await _emit("director", "running", message="Director composing plan")

        director_input = self._build_director_input(
            product_input=product_input,
            reference_images=reference_images,
            reference_videos=reference_videos,
            user_brief=user_brief,
            context_injection=context_injection,
            tech_config=tech_config,
            niche_hint=niche_hint,
            ref_hints=ref_hints,
        )

        director_system = load_system_prompt("director")
        director_user = json.dumps(director_input, ensure_ascii=False, indent=2)

        # ===== Stage C: Director LLM call =====
        try:
            raw = await asyncio.to_thread(
                llm.complete,
                system_prompt=director_system,
                user_message=director_user,
                task="generator",  # heavy reasoning → DeepSeek-V4-Pro / Claude
                max_tokens=8000,
                temperature=0.65,
            )
        except Exception as e:
            logger.exception(f"[DirectorAgent] LLM call fail: {e}")
            raise RuntimeError(f"Director LLM call failed: {e}") from e

        try:
            raw_dict = _safe_parse_json(raw)
        except Exception as e:
            logger.error(f"[DirectorAgent] JSON parse fail. Raw head: {raw[:400]}")
            raise RuntimeError(f"Director output is not valid JSON: {e}") from e

        # ===== Stage D: Parse → DirectorPlan + repair =====
        bible_dict = raw_dict.get("continuity_bible") or {}
        shots_list = raw_dict.get("shot_list") or []
        storyboard_list = raw_dict.get("storyboard_grid") or []

        bible_dict = self._repair_bible_dict(bible_dict, reference_images, ref_hints, tech_config, user_brief)

        try:
            bible = ContinuityBible(**bible_dict)
        except ValidationError as e:
            logger.error(f"[DirectorAgent] Bible validation fail: {e}")
            raise RuntimeError(f"Bible schema invalid: {e}") from e

        parsed_shots: list[Shot] = []
        skipped_shots: list[dict] = []
        for raw_idx, s_dict in enumerate(shots_list):
            try:
                coerced = self._coerce_shot_dict(s_dict, fallback_index=raw_idx)
                parsed_shots.append(Shot(**coerced))
            except ValidationError as ve:
                # Sprint2 M6 — log full Pydantic errors() instead of opaque str(ve)
                # so user can debug exactly which field LLM screwed up.
                try:
                    field_errors = [
                        f"{'.'.join(str(p) for p in err.get('loc', []))}: {err.get('msg', '?')}"
                        for err in ve.errors()[:5]
                    ]
                except Exception:
                    field_errors = [str(ve)[:160]]
                logger.warning(
                    f"[DirectorAgent] Shot {raw_idx} validation fail — SKIPPED. "
                    f"shot_id={s_dict.get('shot_id', '?') if isinstance(s_dict, dict) else '?'}, "
                    f"field_errors={field_errors}"
                )
                skipped_shots.append({
                    "raw_idx": raw_idx,
                    "shot_id": (s_dict.get("shot_id") if isinstance(s_dict, dict) else None),
                    "field_errors": field_errors,
                })

        if not parsed_shots:
            raise RuntimeError(
                f"Director Agent returned no valid shots — all {len(shots_list)} "
                f"shots failed validation. First errors: "
                f"{[s.get('field_errors') for s in skipped_shots[:2]]}"
            )

        # Re-index contiguously (defensive) + ensure unique shot_ids
        parsed_shots = self._reindex_shots(parsed_shots)

        parsed_storyboard: list[StoryboardFrame] = []
        for f_dict in storyboard_list:
            try:
                parsed_storyboard.append(StoryboardFrame(**f_dict))
            except ValidationError:
                pass  # ensure_storyboard_complete sẽ fill placeholder

        # Auto-fixes
        parsed_shots = continuity_manager.normalize_timeline(parsed_shots)
        parsed_shots = continuity_manager.auto_chain_shots(parsed_shots)

        plan = DirectorPlan(
            plan_id=plan_id,
            created_at=datetime.now(timezone.utc).isoformat() + "Z",
            continuity_bible=bible,
            shot_list=parsed_shots,
            storyboard_grid=parsed_storyboard,
            evaluation=EvaluationReport(
                consistency_score=0, viral_potential_score=0, cinematic_score=0,
                pacing_score=0, brand_safety_score=0, overall_score=0,
            ),
            cost_estimate=CostEstimate(),
            llm_calls_total=1 + (1 if ref_hints else 0),
        )
        plan = continuity_manager.ensure_storyboard_complete(plan)

        # Validate + sanitize (warnings logged once, soft issues silently fixed)
        warnings = continuity_manager.validate_plan(
            plan, target_duration_s=tech_config.get("duration_s", 15),
        )
        if warnings:
            logger.warning(f"[DirectorAgent] plan {plan_id} validation warnings: {warnings}")
        plan = continuity_manager.sanitize_plan(plan)

        await _emit("director", "done",
                    shots=len(parsed_shots),
                    duration_total=sum(s.duration_s for s in parsed_shots),
                    warnings=len(warnings))

        # ===== Stage E: Evaluation =====
        await _emit("evaluation", "running", message="Self-critique")
        try:
            eval_report = await asyncio.to_thread(
                evaluate_plan,
                plan_dict=plan.model_dump(),
                user_brief=user_brief,
                tech_config=tech_config,
            )
            plan.evaluation = eval_report
            plan.llm_calls_total += 1
        except Exception as e:
            logger.warning(f"[DirectorAgent] eval fail (continuing with zero scores): {e}")
        await _emit("evaluation", "done", overall=plan.evaluation.overall_score)

        # ===== Stage F: Cost estimate =====
        plan.cost_estimate = self._estimate_cost(plan, tech_config)
        plan.elapsed_s = round(time.time() - t_start, 1)

        logger.info(
            f"[DirectorAgent] plan {plan_id} done in {plan.elapsed_s}s — "
            f"{len(plan.shot_list)} shots, overall={plan.evaluation.overall_score}"
        )
        return plan

    # ============================================================
    # Repair helpers — coerce LLM output to schema-compatible shapes
    # ============================================================
    def _repair_bible_dict(
        self,
        bible_dict: dict,
        reference_images: list[str],
        ref_hints: list[dict],
        tech_config: dict,
        user_brief: str,
    ) -> dict:
        """Fill defaults + sync ref_assets URLs so Pydantic accepts the dict."""
        # Top-level
        bible_dict.setdefault("title", (user_brief[:80] or "Untitled").strip())
        bible_dict.setdefault("logline", (user_brief[:140] or "Untitled video").strip())
        bible_dict.setdefault("intent", "viral_short")
        bible_dict.setdefault("duration_s", tech_config.get("duration_s", 15))
        bible_dict.setdefault("aspect_ratio", tech_config.get("aspect_ratio", "9:16"))
        bible_dict.setdefault("director_notes", "")
        bible_dict.setdefault("characters", [])
        bible_dict.setdefault("products", [])

        # Nested objects — set defaults only if missing OR not a dict
        vs = bible_dict.get("visual_style")
        if not isinstance(vs, dict):
            vs = {}
        vs.setdefault("cinematography", "")
        vs.setdefault("color_grading", "")
        vs.setdefault("lighting_design", "")
        vs.setdefault("camera_language", "")
        vs.setdefault("film_grain", "")
        vs.setdefault("aspect_ratio", tech_config.get("aspect_ratio", "9:16"))
        bible_dict["visual_style"] = vs

        ad = bible_dict.get("audio_design")
        if not isinstance(ad, dict):
            ad = {}
        ad.setdefault("mood", "")
        ad.setdefault("tempo", "")
        ad.setdefault("music_genre", "")
        ad.setdefault("sfx_emphasis", [])
        ad.setdefault("dialogue_style", "silent")
        bible_dict["audio_design"] = ad

        st = bible_dict.get("setting")
        if not isinstance(st, dict):
            st = {}
        st.setdefault("location", "")
        st.setdefault("time_of_day", "")
        st.setdefault("atmosphere", "")
        bible_dict["setting"] = st

        cn = bible_dict.get("constraints")
        if not isinstance(cn, dict):
            cn = {}
        cn.setdefault("must_have", [])
        cn.setdefault("must_avoid", [])
        cn.setdefault("brand_safety", [])
        bible_dict["constraints"] = cn

        # reference_assets — backfill / sync URLs / drop invalid
        existing = bible_dict.get("reference_assets") or []
        if not existing and reference_images:
            bible_dict["reference_assets"] = [
                {
                    "index": i,
                    "url": url,
                    "role": (
                        ref_hints[i].get("role", "unknown")
                        if i < len(ref_hints) and isinstance(ref_hints[i], dict)
                        else "unknown"
                    ),
                    "apply_to_shots": [],
                    "notes": "",
                }
                for i, url in enumerate(reference_images)
            ]
        else:
            cleaned = []
            for r in existing:
                if not isinstance(r, dict):
                    continue
                idx = r.get("index")
                if not isinstance(idx, int) or idx < 0 or idx >= len(reference_images):
                    # Drop refs that don't map back to any uploaded image
                    continue
                # Force URL to echo the user-uploaded URL (LLM cannot invent URLs)
                r["url"] = reference_images[idx]
                r.setdefault("role", "unknown")
                r.setdefault("apply_to_shots", [])
                r.setdefault("notes", "")
                cleaned.append(r)
            bible_dict["reference_assets"] = cleaned

        return bible_dict

    def _coerce_shot_dict(self, s_dict: dict, fallback_index: int) -> dict:
        """Clamp duration / fix index / fill nested dict defaults so Pydantic accepts."""
        if not isinstance(s_dict, dict):
            raise ValidationError.from_exception_data("Shot", []) if False else ValueError("shot not a dict")

        # shot_id / index
        s_dict.setdefault("shot_id", f"S{fallback_index + 1}")
        idx = s_dict.get("index")
        if not isinstance(idx, int) or idx < 0:
            s_dict["index"] = fallback_index

        # Duration — schema requires ge=2, le=20. Clamp LLM mistakes
        try:
            dur = int(s_dict.get("duration_s", 3))
        except (TypeError, ValueError):
            dur = 3
        s_dict["duration_s"] = max(2, min(20, dur))

        # start_s / end_s defaults — continuity_manager.normalize_timeline overrides anyway
        s_dict.setdefault("start_s", float(fallback_index * 3))
        s_dict.setdefault("end_s", float(fallback_index * 3 + s_dict["duration_s"]))

        # Required nested objects
        visual = s_dict.get("visual") if isinstance(s_dict.get("visual"), dict) else {}
        visual.setdefault("subject", "")
        visual.setdefault("action", "")
        visual.setdefault("camera_shot", "MS")
        visual.setdefault("camera_movement", "static")
        visual.setdefault("composition", "")
        visual.setdefault("background", "")
        s_dict["visual"] = visual

        audio = s_dict.get("audio") if isinstance(s_dict.get("audio"), dict) else {}
        audio.setdefault("sfx", [])
        s_dict["audio"] = audio

        cont = s_dict.get("continuity") if isinstance(s_dict.get("continuity"), dict) else {}
        cont.setdefault("character_ids", [])
        cont.setdefault("product_ids", [])
        cont.setdefault("reference_indices", [])
        cont.setdefault("previous_shot_id", None)
        cont.setdefault("style_anchor", "")
        s_dict["continuity"] = cont

        mr = s_dict.get("model_routing") if isinstance(s_dict.get("model_routing"), dict) else {}
        mr.setdefault("preferred_model", "auto")
        mr.setdefault("reasoning", "")
        s_dict["model_routing"] = mr

        s_dict.setdefault("purpose", "shot")
        s_dict.setdefault("emotion_beat", "")
        return s_dict

    def _reindex_shots(self, shots: list[Shot]) -> list[Shot]:
        """Force contiguous `index` 0..N-1 and dedupe shot_ids if LLM duplicated."""
        seen_ids: set[str] = set()
        for new_idx, s in enumerate(shots):
            s.index = new_idx
            if s.shot_id in seen_ids:
                base = s.shot_id
                bump = 2
                while f"{base}_{bump}" in seen_ids:
                    bump += 1
                logger.warning(f"[DirectorAgent] duplicate shot_id '{base}' → renamed '{base}_{bump}'")
                s.shot_id = f"{base}_{bump}"
            seen_ids.add(s.shot_id)
        return shots

    # ============================================================
    # Vision pass — classify references (best-effort, fast)
    # ============================================================
    def _vision_scan_refs(self, reference_images: list[str]) -> list[dict]:
        """Best-effort role classification for each ref image.

        Single vision call returns JSON array. Errors → empty list, Director Agent
        still runs (will mark refs as 'unknown' and reason from URLs alone).
        """
        if not reference_images:
            return []

        system = (
            "You classify uploaded reference images for a video shoot. For each image, "
            "decide one role: character_anchor | secondary_character | product_hero | "
            "product_detail | style_reference | environment | brand_asset | unknown. "
            "Reply ONLY with a JSON array of objects: [{\"index\":0,\"role\":\"...\",\"notes\":\"...\"}]. "
            "No prose."
        )
        user = (
            f"Classify these {len(reference_images)} images (indices 0..{len(reference_images)-1}). "
            "Return JSON array."
        )

        try:
            raw = llm.complete_with_image(
                system_prompt=system,
                user_message=user,
                image_urls=reference_images[:12],
                task="vision",
                max_tokens=800,
            )
        except Exception as e:
            logger.warning(f"[DirectorAgent] vision call fail: {e}")
            return []

        try:
            data = _safe_parse_json(raw)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and isinstance(data.get("classifications"), list):
                return data["classifications"]
        except Exception as e:
            logger.warning(f"[DirectorAgent] vision parse fail: {e}")
        return []

    # ============================================================
    # Build director input bundle
    # ============================================================
    def _build_director_input(
        self,
        product_input: dict,
        reference_images: list[str],
        reference_videos: list[str],
        user_brief: str,
        context_injection: dict,
        tech_config: dict,
        niche_hint: Optional[str],
        ref_hints: list[dict],
    ) -> dict:
        # V3.1 — inject model capability summary so the Director plans within
        # the chosen model's hard constraints (max refs, discrete durations,
        # audio mode, image-tag support, etc.).
        from agent.model_capabilities import summary_for_director_prompt
        tc = dict(tech_config)
        tc["model_capability_notes"] = summary_for_director_prompt(
            tc.get("model", "auto")
        )
        return {
            "product_input": product_input,
            "reference_images": reference_images,
            "reference_hints": ref_hints,  # Vision-pass output, optional
            "reference_videos": reference_videos,
            "user_brief": user_brief,
            "context_injection": context_injection,
            "tech_config": tc,
            "niche_hint": niche_hint or "auto",
        }

    # ============================================================
    # Cost estimate (heuristic — refined later)
    # ============================================================
    def _estimate_cost(self, plan: DirectorPlan, tech_config: dict) -> CostEstimate:
        # LLM cost (Director + Eval + optional Vision)
        llm_cost = 0.02 * plan.llm_calls_total

        # Storyboard gen — assume Seedream v4.5 ~$0.04 / image, only if user opts in
        sb_cost = 0.0  # filled when /storyboard endpoint called

        # Render cost — rough per-model $/s
        per_s = {
            "vidu_q3": 0.042, "vidu_q3_mix": 0.046,
            "wan_2_7": 0.060,
            "seedance_1_5_pro": 0.047, "seedance_2_0": 0.096, "seedance_2_0_fast": 0.076,
            "auto": 0.060,
        }.get(tech_config.get("model", "auto"), 0.060)
        render_cost = round(per_s * plan.continuity_bible.duration_s, 3)

        # Audio cost
        audio_mode = tech_config.get("audio_mode", "silent_native")
        audio_cost = 0.01 if audio_mode == "dialogue_vo" else (0.10 if audio_mode == "asmr_macro" else 0.0)

        total = round(llm_cost + sb_cost + render_cost + audio_cost, 3)
        return CostEstimate(
            plan_cost_usd=round(llm_cost, 3),
            storyboard_gen_cost_usd=sb_cost,
            render_cost_usd=render_cost,
            audio_cost_usd=audio_cost,
            total_cost_usd=total,
        )


# Singleton
director = DirectorAgent()
