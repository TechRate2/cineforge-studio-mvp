"""Deterministic production QA gate for rendered CineJelly clips.

This layer turns technical probe data, sampled-frame availability, semantic QA
metadata, and the production bible into a clear pass/warn/fail verdict. It does
not pretend to replace model-backed identity, product, or lip-sync evaluation;
it gives the worker a stricter non-paid gate before those evaluators are added.
"""
from __future__ import annotations

from typing import Any, Optional

from agent.schemas import ContinuityBible, Shot


def evaluate_strong_quality_gate(
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
    checks: list[dict[str, Any]] = []
    hard_failures: list[str] = []
    warnings: list[str] = []
    score = 100.0

    def add(
        name: str,
        status: str,
        detail: str,
        *,
        severity: str = "info",
        penalty: float = 0.0,
        retry_reason: Optional[str] = None,
    ) -> None:
        nonlocal score
        checks.append(
            {
                "name": name,
                "status": status,
                "severity": severity,
                "detail": detail,
                "retry_reason": retry_reason,
            }
        )
        if status == "fail":
            hard_failures.append(retry_reason or name)
        elif status == "warn":
            warnings.append(retry_reason or name)
        score = max(0.0, score - penalty)

    if video_url:
        add("render_output", "pass", "Video URL is present.")
    else:
        add(
            "render_output",
            "fail",
            "Vendor returned no video URL.",
            severity="error",
            penalty=45,
            retry_reason="missing_video_url",
        )

    if prediction_id:
        add("prediction_tracking", "pass", "Prediction id is available for audit/cancel tracking.")
    else:
        add(
            "prediction_tracking",
            "warn",
            "Missing prediction id metadata.",
            severity="warning",
            penalty=3,
            retry_reason="missing_prediction_id",
        )

    _check_media_contract(
        add=add,
        media_probe=media_probe or {},
        target_duration_s=float(duration_s or 0),
        dialogue_or_audio_expected=_dialogue_or_audio_expected(bible, shot, reference_audio_count),
    )
    _check_frame_sampling(add=add, frame_samples=frame_samples or {})
    _check_text_artifacts(add=add, text_artifacts=text_artifacts or {}, shot=shot)
    _check_visual_reference_probe(
        add=add,
        visual_reference_probe=visual_reference_probe or {},
        reference_image_count=reference_image_count,
    )
    _check_reference_contract(
        add=add,
        bible=bible,
        shot=shot,
        reference_image_count=reference_image_count,
        reference_video_count=reference_video_count,
        reference_audio_count=reference_audio_count,
    )
    _check_continuity_contract(add=add, shot=shot, chained_from=chained_from)
    _check_semantic_contract(add=add, semantic_quality=semantic_quality or {})
    _check_caption_contract(add=add, shot=shot)
    _check_seedance_contract(
        add=add,
        render_mode=render_mode,
        model_key=model_key,
        duration_s=duration_s,
        output_scope=output_scope,
        reference_image_count=reference_image_count,
    )

    if hard_failures:
        status = "fail"
    elif warnings:
        status = "warn"
    else:
        status = "pass"

    retry_reason = hard_failures[0] if hard_failures else (warnings[0] if warnings else None)
    return {
        "status": status,
        "score": round(score, 1),
        "retry_recommended": bool(hard_failures),
        "manual_review_recommended": bool(hard_failures or warnings),
        "retry_reason": retry_reason if hard_failures else None,
        "warning_reason": retry_reason if warnings and not hard_failures else None,
        "hard_failures": hard_failures,
        "warnings": warnings,
        "checks": checks,
        "model_backed_gates_still_required": [
            "face_or_character_embedding_match",
            "product_logo_and_packaging_match",
            "robust_multilingual_text_artifact_detection",
            "speech_lip_sync_alignment",
        ],
    }


def _check_media_contract(*, add: Any, media_probe: dict[str, Any], target_duration_s: float, dialogue_or_audio_expected: bool) -> None:
    status = str(media_probe.get("status") or "unavailable")
    if status == "fail":
        add(
            "media_probe",
            "fail",
            f"Media probe failed: {', '.join(media_probe.get('errors') or ['unknown'])}",
            severity="error",
            penalty=35,
            retry_reason="media_probe_failed",
        )
        return
    if status == "unavailable":
        add(
            "media_probe",
            "warn",
            "ffprobe unavailable; technical media contract could not be fully verified.",
            severity="warning",
            penalty=8,
            retry_reason="media_probe_unavailable",
        )
        return
    if media_probe.get("video_stream_count") == 0:
        add(
            "video_stream",
            "fail",
            "Rendered file has no video stream.",
            severity="error",
            penalty=40,
            retry_reason="missing_video_stream",
        )
    else:
        add(
            "video_stream",
            "pass",
            f"{media_probe.get('width')}x{media_probe.get('height')} {media_probe.get('video_codec') or 'video'} stream detected.",
        )

    duration = _to_float(media_probe.get("duration_s"))
    if target_duration_s > 0 and duration is not None:
        delta = abs(duration - target_duration_s)
        if delta > max(2.5, target_duration_s * 0.35):
            add(
                "duration_fit",
                "fail",
                f"Duration {duration:.2f}s is too far from target {target_duration_s:.2f}s.",
                severity="error",
                penalty=30,
                retry_reason="duration_mismatch_hard",
            )
        elif delta > max(1.25, target_duration_s * 0.2):
            add(
                "duration_fit",
                "warn",
                f"Duration {duration:.2f}s differs from target {target_duration_s:.2f}s.",
                severity="warning",
                penalty=10,
                retry_reason="duration_mismatch",
            )
        else:
            add("duration_fit", "pass", f"Duration {duration:.2f}s fits target {target_duration_s:.2f}s.")

    if dialogue_or_audio_expected and int(media_probe.get("audio_stream_count") or 0) == 0:
        add(
            "audio_presence",
            "fail",
            "Dialogue/audio was expected but rendered file has no audio stream.",
            severity="error",
            penalty=30,
            retry_reason="missing_expected_audio",
        )
    elif dialogue_or_audio_expected:
        add("audio_presence", "pass", "Expected audio stream is present.")
        _check_audio_quality(add=add, audio_quality=media_probe.get("audio_quality") or {})


def _check_frame_sampling(*, add: Any, frame_samples: dict[str, Any]) -> None:
    status = str(frame_samples.get("status") or "unavailable")
    count = len(frame_samples.get("frames") or [])
    if status == "pass" and count >= 3:
        add("frame_samples", "pass", "First/middle/last QA frames were sampled.")
    elif count > 0:
        add(
            "frame_samples",
            "warn",
            f"Only {count} QA frame(s) sampled; visual QA confidence is reduced.",
            severity="warning",
            penalty=7,
            retry_reason="insufficient_qa_frames",
        )
    else:
        add(
            "frame_samples",
            "warn",
            "No QA frames were sampled.",
            severity="warning",
            penalty=12,
            retry_reason="missing_qa_frames",
        )


def _check_audio_quality(*, add: Any, audio_quality: dict[str, Any]) -> None:
    status = str(audio_quality.get("status") or "unavailable")
    if status == "unavailable":
        add(
            "audio_loudness_silence",
            "warn",
            "Audio stream exists, but loudness/silence metrics are unavailable.",
            severity="warning",
            penalty=6,
            retry_reason="audio_quality_metrics_unavailable",
        )
        return
    warnings = list(audio_quality.get("warnings") or [])
    silence_ratio = _to_float(audio_quality.get("silence_ratio"))
    mean_volume = _to_float(audio_quality.get("mean_volume_db"))
    max_volume = _to_float(audio_quality.get("max_volume_db"))

    if "audio_mostly_silent" in warnings or (silence_ratio is not None and silence_ratio >= 0.85):
        add(
            "audio_loudness_silence",
            "fail",
            (
                f"Expected audio is mostly silent "
                f"(silence_ratio={silence_ratio}, mean={mean_volume}dB, max={max_volume}dB)."
            ),
            severity="error",
            penalty=25,
            retry_reason="expected_audio_mostly_silent",
        )
    elif "audio_probably_too_quiet" in warnings or "audio_high_silence_ratio" in warnings:
        add(
            "audio_loudness_silence",
            "warn",
            (
                f"Audio may be too quiet or sparse "
                f"(silence_ratio={silence_ratio}, mean={mean_volume}dB, max={max_volume}dB)."
            ),
            severity="warning",
            penalty=12,
            retry_reason="audio_too_quiet_or_sparse",
        )
    else:
        add(
            "audio_loudness_silence",
            "pass",
            f"Audio loudness/silence metrics look usable (mean={mean_volume}dB, max={max_volume}dB).",
        )


def _check_text_artifacts(*, add: Any, text_artifacts: dict[str, Any], shot: Optional[Shot]) -> None:
    status = str(text_artifacts.get("status") or "unavailable")
    if status == "unavailable":
        add(
            "text_artifact_ocr",
            "warn",
            "OCR text-artifact probe unavailable; visible fake text/caption artifacts were not verified.",
            severity="warning",
            penalty=5,
            retry_reason="text_artifact_ocr_unavailable",
        )
        return

    warnings = list(text_artifacts.get("warnings") or [])
    detections = list(text_artifacts.get("detections") or [])
    caption_expected = bool((shot.audio.caption_on_screen if shot else None) or text_artifacts.get("caption_expected"))
    if "visible_text_artifact_risk" in warnings:
        add(
            "text_artifact_ocr",
            "fail",
            f"OCR found suspicious visible text in sampled frames: {_detection_summary(detections)}",
            severity="error",
            penalty=20,
            retry_reason="visible_text_artifact_risk",
        )
    elif "unexpected_visible_text" in warnings and not caption_expected:
        add(
            "text_artifact_ocr",
            "warn",
            f"OCR found unexpected visible text: {_detection_summary(detections)}",
            severity="warning",
            penalty=10,
            retry_reason="unexpected_visible_text",
        )
    else:
        add("text_artifact_ocr", "pass", "OCR text-artifact probe found no blocking visible text issue.")


def _detection_summary(detections: list[Any]) -> str:
    snippets = []
    for detection in detections[:2]:
        if isinstance(detection, dict) and detection.get("text"):
            snippets.append(str(detection["text"])[:80])
    return "; ".join(snippets) or "text detected"


def _check_visual_reference_probe(
    *,
    add: Any,
    visual_reference_probe: dict[str, Any],
    reference_image_count: int,
) -> None:
    if reference_image_count <= 0:
        return
    status = str(visual_reference_probe.get("status") or "unavailable")
    if status == "unavailable":
        add(
            "visual_reference_similarity",
            "warn",
            "Visual reference similarity baseline unavailable; identity/product drift still needs review.",
            severity="warning",
            penalty=5,
            retry_reason="visual_reference_probe_unavailable",
        )
        return
    warnings = list(visual_reference_probe.get("warnings") or [])
    avg = visual_reference_probe.get("average_best_similarity")
    max_score = visual_reference_probe.get("max_similarity")
    if "visual_reference_similarity_low" in warnings:
        add(
            "visual_reference_similarity",
            "warn",
            f"Rendered QA frames look visually distant from image refs (avg={avg}, max={max_score}).",
            severity="warning",
            penalty=12,
            retry_reason="visual_reference_similarity_low",
        )
    else:
        add(
            "visual_reference_similarity",
            "pass",
            f"Visual reference baseline found some frame/ref similarity (avg={avg}, max={max_score}).",
        )


def _check_reference_contract(
    *,
    add: Any,
    bible: ContinuityBible,
    shot: Optional[Shot],
    reference_image_count: int,
    reference_video_count: int,
    reference_audio_count: int,
) -> None:
    needs_visual_anchor = bool(
        bible.characters
        or bible.products
        or bible.reference_assets
        or (shot and (shot.continuity.character_ids or shot.continuity.product_ids or shot.continuity.reference_indices))
    )
    if needs_visual_anchor and reference_image_count == 0 and reference_video_count == 0:
        add(
            "reference_binding",
            "warn",
            "Identity/product/style contract exists but no image/video references reached this render.",
            severity="warning",
            penalty=15,
            retry_reason="missing_visual_reference_binding",
        )
    else:
        add(
            "reference_binding",
            "pass",
            f"References bound: images={reference_image_count}, videos={reference_video_count}, audio={reference_audio_count}.",
        )


def _check_continuity_contract(*, add: Any, shot: Optional[Shot], chained_from: Optional[str]) -> None:
    previous = shot.continuity.previous_shot_id if shot else None
    if previous and not chained_from:
        add(
            "continuity_chain",
            "warn",
            f"Shot expects previous_shot_id={previous}, but no chain anchor was used.",
            severity="warning",
            penalty=12,
            retry_reason="missing_continuity_chain_anchor",
        )
    elif previous:
        add("continuity_chain", "pass", f"Continuity chain anchor {chained_from} was used.")
    else:
        add("continuity_chain", "pass", "No continuity chain required.")


def _check_semantic_contract(*, add: Any, semantic_quality: dict[str, Any]) -> None:
    status = str(semantic_quality.get("status") or "unavailable")
    score = _to_float(semantic_quality.get("score"))
    if status == "fail" or (score is not None and score < 5.0):
        add(
            "semantic_visual_qa",
            "fail",
            f"Vision QA failed: {semantic_quality.get('retry_reason') or ', '.join(semantic_quality.get('failures') or ['low score'])}",
            severity="error",
            penalty=35,
            retry_reason=str(semantic_quality.get("retry_reason") or "semantic_visual_qa_failed"),
        )
    elif status == "warn" or (score is not None and score < 7.0):
        add(
            "semantic_visual_qa",
            "warn",
            f"Vision QA warning: {', '.join(semantic_quality.get('failures') or ['borderline score'])}",
            severity="warning",
            penalty=15,
            retry_reason="semantic_visual_qa_warn",
        )
    elif status == "pass":
        add("semantic_visual_qa", "pass", f"Vision QA passed with score {score}.")
    else:
        add(
            "semantic_visual_qa",
            "warn",
            f"Vision QA unavailable: {semantic_quality.get('reason') or 'not run'}.",
            severity="warning",
            penalty=8,
            retry_reason="semantic_visual_qa_unavailable",
        )


def _check_caption_contract(*, add: Any, shot: Optional[Shot]) -> None:
    caption = (shot.audio.caption_on_screen if shot else None) or ""
    if not caption:
        add("caption_contract", "pass", "No burned-in caption required for this render.")
        return
    if len(caption) > 80:
        add(
            "caption_contract",
            "warn",
            "Caption is long for a generated frame; post-production burn-in should handle final text.",
            severity="warning",
            penalty=6,
            retry_reason="caption_too_long_for_model_render",
        )
    else:
        add("caption_contract", "pass", "Caption contract is short enough for post-production handling.")


def _check_seedance_contract(
    *,
    add: Any,
    render_mode: str,
    model_key: str,
    duration_s: int,
    output_scope: str,
    reference_image_count: int,
) -> None:
    key = f"{model_key} {render_mode}".lower()
    if "seedance" in key and output_scope == "shot" and duration_s > 15:
        add(
            "model_duration_fit",
            "warn",
            "Seedance shot target exceeds 15s; split into smaller physical actions for stronger continuity.",
            severity="warning",
            penalty=10,
            retry_reason="seedance_shot_too_long",
        )
    elif "seedance" in key:
        add("model_duration_fit", "pass", "Seedance duration contract fits this render scope.")

    if "ref" in key and reference_image_count > 9:
        add(
            "reference_count",
            "warn",
            "Reference count exceeds the intended 9-image cap; identity focus may degrade.",
            severity="warning",
            penalty=8,
            retry_reason="too_many_reference_images",
        )


def _dialogue_or_audio_expected(bible: ContinuityBible, shot: Optional[Shot], reference_audio_count: int) -> bool:
    if reference_audio_count > 0:
        return True
    if shot and (shot.audio.dialogue_vn or shot.audio.music_cue or shot.audio.sfx):
        return True
    style = " ".join(
        [
            bible.audio_design.dialogue_style or "",
            bible.audio_design.music_genre or "",
            bible.audio_design.mood or "",
        ]
    ).lower()
    return any(token in style for token in ("dialogue", "voice", "vo", "monologue", "asmr", "music"))


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["evaluate_strong_quality_gate"]
