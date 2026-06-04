"""Render quality metadata for post-render QA and future auto-retry.

This module is intentionally deterministic. It does not claim to inspect pixels
or audio; it records the quality contract that a rendered clip must satisfy and
flags gaps that can be verified without an extra model call. A real visual/audio
evaluator can consume the same report shape later.
"""
from __future__ import annotations

from typing import Any, Optional

from agent.schemas import ContinuityBible, Shot
from agent.strong_quality_gate import evaluate_strong_quality_gate


def _trim_list(values: list[str], limit: int = 8) -> list[str]:
    return [str(v) for v in values if str(v).strip()][:limit]


def _check(name: str, status: str, detail: str, severity: str = "info") -> dict[str, str]:
    return {
        "name": name,
        "status": status,
        "severity": severity,
        "detail": detail,
    }


def build_render_quality_report(
    *,
    bible: ContinuityBible,
    shot: Optional[Shot],
    render_mode: str,
    model_key: str,
    video_url: Optional[str],
    prediction_id: Optional[str],
    duration_s: int,
    reference_image_count: int,
    reference_video_count: int = 0,
    reference_audio_count: int = 0,
    chained_from: Optional[str] = None,
    output_scope: str = "shot",
    media_probe: Optional[dict[str, Any]] = None,
    frame_samples: Optional[dict[str, Any]] = None,
    semantic_quality: Optional[dict[str, Any]] = None,
    text_artifacts: Optional[dict[str, Any]] = None,
    visual_reference_probe: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Return a conservative QA report for one rendered shot or one full clip."""
    checks: list[dict[str, str]] = []
    hard_fail = False
    warnings = 0

    if video_url:
        checks.append(_check("video_url", "pass", "Vendor returned a playable video URL."))
    else:
        hard_fail = True
        checks.append(_check("video_url", "fail", "Vendor did not return video_url.", "error"))

    if prediction_id:
        checks.append(_check("prediction_tracking", "pass", f"Prediction tracked as {prediction_id}."))
    else:
        warnings += 1
        checks.append(_check("prediction_tracking", "warn", "Missing prediction_id metadata.", "warning"))

    if duration_s > 0:
        checks.append(_check("duration_contract", "pass", f"Target render duration is {duration_s}s."))
    else:
        hard_fail = True
        checks.append(_check("duration_contract", "fail", "Invalid non-positive duration.", "error"))

    if shot and shot.continuity.previous_shot_id:
        if chained_from:
            checks.append(_check("reference_chain", "pass", f"Shot chains from {chained_from}."))
        else:
            warnings += 1
            checks.append(
                _check(
                    "reference_chain",
                    "warn",
                    f"Shot requested previous_shot_id={shot.continuity.previous_shot_id}, but no chain anchor was used.",
                    "warning",
                )
            )
    else:
        checks.append(_check("reference_chain", "pass", "No previous-shot chain required."))

    if media_probe:
        probe_status = str(media_probe.get("status") or "unavailable")
        if probe_status == "fail":
            hard_fail = True
            checks.append(
                _check(
                    "media_probe",
                    "fail",
                    f"ffprobe failed: {', '.join(media_probe.get('errors') or ['unknown'])}",
                    "error",
                )
            )
        elif probe_status == "warn":
            warnings += 1
            checks.append(
                _check(
                    "media_probe",
                    "warn",
                    f"ffprobe warnings: {', '.join(media_probe.get('warnings') or ['unknown'])}",
                    "warning",
                )
            )
        elif probe_status == "pass":
            checks.append(
                _check(
                    "media_probe",
                    "pass",
                    (
                        f"{media_probe.get('duration_s')}s, "
                        f"{media_probe.get('width')}x{media_probe.get('height')}, "
                        f"video={media_probe.get('video_codec')}, "
                        f"audio_streams={media_probe.get('audio_stream_count')}"
                    ),
                )
            )
        else:
            warnings += 1
            checks.append(_check("media_probe", "warn", "ffprobe unavailable.", "warning"))

    if frame_samples:
        sample_status = str(frame_samples.get("status") or "unavailable")
        frame_count = len(frame_samples.get("frames") or [])
        if sample_status == "pass":
            checks.append(_check("frame_sampling", "pass", f"Sampled {frame_count} QA frames."))
        elif sample_status == "warn":
            warnings += 1
            checks.append(
                _check(
                    "frame_sampling",
                    "warn",
                    f"Sampled {frame_count} QA frames; warnings: {', '.join(frame_samples.get('warnings') or [])[:180]}",
                    "warning",
                )
            )
        elif sample_status == "fail":
            warnings += 1
            checks.append(
                _check(
                    "frame_sampling",
                    "warn",
                    f"Frame sampling failed: {', '.join(frame_samples.get('errors') or ['unknown'])}",
                    "warning",
                )
            )
        else:
            warnings += 1
            checks.append(_check("frame_sampling", "warn", "ffmpeg unavailable.", "warning"))

    if semantic_quality:
        semantic_status = str(semantic_quality.get("status") or "unavailable")
        if semantic_status == "fail":
            warnings += 1
            checks.append(
                _check(
                    "semantic_visual_qa",
                    "warn",
                    f"Vision QA recommends retry: {semantic_quality.get('retry_reason') or 'semantic failure'}",
                    "warning",
                )
            )
        elif semantic_status == "warn":
            warnings += 1
            checks.append(
                _check(
                    "semantic_visual_qa",
                    "warn",
                    f"Vision QA warnings: {', '.join(semantic_quality.get('failures') or [])[:180]}",
                    "warning",
                )
            )
        elif semantic_status == "pass":
            checks.append(
                _check(
                    "semantic_visual_qa",
                    "pass",
                    f"Vision QA score={semantic_quality.get('score')}.",
                )
            )
        else:
            checks.append(
                _check(
                    "semantic_visual_qa",
                    "pending",
                    f"Vision QA unavailable: {semantic_quality.get('reason') or 'not run'}.",
                )
            )

    if text_artifacts:
        text_status = str(text_artifacts.get("status") or "unavailable")
        if text_status == "warn":
            warnings += 1
            checks.append(
                _check(
                    "text_artifact_ocr",
                    "warn",
                    f"OCR warnings: {', '.join(text_artifacts.get('warnings') or ['unknown'])}",
                    "warning",
                )
            )
        elif text_status == "pass":
            checks.append(_check("text_artifact_ocr", "pass", "OCR text-artifact probe passed."))
        else:
            warnings += 1
            checks.append(_check("text_artifact_ocr", "warn", "OCR unavailable.", "warning"))

    if visual_reference_probe:
        visual_ref_status = str(visual_reference_probe.get("status") or "unavailable")
        if visual_ref_status == "warn":
            warnings += 1
            checks.append(
                _check(
                    "visual_reference_similarity",
                    "warn",
                    f"Visual ref warnings: {', '.join(visual_reference_probe.get('warnings') or ['unknown'])}",
                    "warning",
                )
            )
        elif visual_ref_status == "pass":
            checks.append(
                _check(
                    "visual_reference_similarity",
                    "pass",
                    f"avg={visual_reference_probe.get('average_best_similarity')}, max={visual_reference_probe.get('max_similarity')}",
                )
            )

    strong_gate = evaluate_strong_quality_gate(
        bible=bible,
        shot=shot,
        render_mode=render_mode,
        model_key=model_key,
        video_url=video_url,
        prediction_id=prediction_id,
        duration_s=duration_s,
        reference_image_count=reference_image_count,
        reference_video_count=reference_video_count,
        reference_audio_count=reference_audio_count,
        chained_from=chained_from,
        output_scope=output_scope,
        media_probe=media_probe,
        frame_samples=frame_samples,
        semantic_quality=semantic_quality,
        text_artifacts=text_artifacts,
        visual_reference_probe=visual_reference_probe,
    )
    gate_status = str(strong_gate.get("status") or "warn")
    if gate_status == "fail":
        hard_fail = True
        checks.append(
            _check(
                "strong_quality_gate",
                "fail",
                f"Production gate failed: {strong_gate.get('retry_reason') or 'quality contract failed'}.",
                "error",
            )
        )
    elif gate_status == "warn":
        warnings += 1
        checks.append(
            _check(
                "strong_quality_gate",
                "warn",
                f"Production gate warns: {strong_gate.get('warning_reason') or 'manual review recommended'}.",
                "warning",
            )
        )
    else:
        checks.append(
            _check(
                "strong_quality_gate",
                "pass",
                f"Production gate passed with score={strong_gate.get('score')}.",
            )
        )

    has_identity_contract = bool(bible.characters or bible.products or bible.reference_assets)
    if has_identity_contract and reference_image_count == 0 and reference_video_count == 0:
        warnings += 1
        checks.append(
            _check(
                "reference_contract",
                "warn",
                "Bible has identity/product/reference anchors but render received no image/video references.",
                "warning",
            )
        )
    else:
        checks.append(
            _check(
                "reference_contract",
                "pass",
                f"Refs passed: images={reference_image_count}, videos={reference_video_count}, audio={reference_audio_count}.",
            )
        )

    checks.append(
        _check(
            "visual_semantic_qa",
            "pending",
            "Pixel-level identity, product, caption, camera, and audio verification requires a visual/audio evaluator.",
        )
    )

    must_avoid = _trim_list(bible.constraints.must_avoid)
    must_have = _trim_list(bible.constraints.must_have)
    criteria = {
        "scope": output_scope,
        "shot_id": shot.shot_id if shot else "ALL",
        "model_key": model_key,
        "render_mode": render_mode,
        "must_have": must_have,
        "must_avoid": must_avoid,
        "character_ids": [c.id for c in bible.characters],
        "product_ids": [p.id for p in bible.products],
        "style_anchor": shot.continuity.style_anchor if shot else bible.visual_style.camera_language,
        "caption": shot.audio.caption_on_screen if shot else None,
        "media_probe": media_probe or {},
        "frame_samples": frame_samples or {},
        "semantic_quality": semantic_quality or {},
        "text_artifacts": text_artifacts or {},
        "visual_reference_probe": visual_reference_probe or {},
        "strong_quality_gate": strong_gate,
    }

    status = "fail" if hard_fail else ("warn" if warnings else "pass")
    retry_recommended = (
        hard_fail
        or bool(strong_gate.get("retry_recommended"))
        or bool((semantic_quality or {}).get("retry_recommended"))
    )
    return {
        "status": status,
        "score": strong_gate.get("score", (semantic_quality or {}).get("score")),
        "score_reason": (
            "Deterministic production gate score with semantic QA folded in."
        ),
        "retry_recommended": retry_recommended,
        "manual_review_recommended": bool(hard_fail or warnings or strong_gate.get("manual_review_recommended")),
        "retry_reason": (
            strong_gate.get("retry_reason")
            or ("missing_required_render_output" if hard_fail else None)
            or (semantic_quality or {}).get("retry_reason")
        ),
        "checks": checks,
        "criteria": criteria,
        "strong_quality_gate": strong_gate,
        "auto_retry_policy": {
            "enabled": bool(retry_recommended),
            "next_step": (
                "Retry only shots that fail hard technical, semantic, duration, reference, "
                "caption, or expected-audio gates; model-backed identity/product/lip-sync "
                "checks remain the next production upgrade."
            ),
        },
    }
