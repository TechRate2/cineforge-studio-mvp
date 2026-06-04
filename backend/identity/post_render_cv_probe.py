"""Hybrid OpenCV post-render visual consistency probe.

The probe derives real visual signals from rendered segment videos and image
references without requiring an external CV service. It keeps OpenCV primitives
for speed, then adds a descriptor/embedding ensemble for materially better
character, product/logo, style, and emotion consistency estimates.

If `POST_RENDER_CV_PROBE_EMBEDDING_MODEL_PATH` points to an ONNX model, the
probe uses OpenCV DNN embeddings in addition to the handcrafted descriptor. When
no model is configured, the handcrafted HSV/HOG/LBP/edge embedding remains a
real deterministic fallback rather than mock data.
"""
from __future__ import annotations

import logging
import shutil
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from core.config import settings
from pipeline.contracts import AssetRef, ReferenceRole, SeedanceShotPlan
from workers.segment_renderer import SegmentRenderResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PairScore:
    """Weighted visual match score plus evidence quality."""

    score: float
    confidence: float
    components: dict[str, float]


class OpenCVHybridEmbedder:
    """Lightweight embedding provider backed by OpenCV descriptors and optional DNN."""

    def __init__(
        self,
        cv2: Any,
        *,
        enabled: bool = True,
        model_path: str = "",
        input_size: int = 224,
    ) -> None:
        self.cv2 = cv2
        self.enabled = enabled
        self.input_size = max(64, int(input_size or 224))
        self.backend = "disabled"
        self._net: Any | None = None
        if not self.enabled:
            return
        path = Path(str(model_path or "")).expanduser()
        if path.exists() and path.is_file():
            try:
                self._net = cv2.dnn.readNetFromONNX(str(path))
                self.backend = "opencv_dnn_onnx+handcrafted"
            except Exception as exc:
                logger.warning(
                    "post_render_cv_embedding_model_load_failed",
                    extra={"model_path": str(path), "error": _safe_error(exc)},
                    exc_info=True,
                )
                self.backend = "handcrafted"
        else:
            self.backend = "handcrafted"

    def descriptor(self, image: np.ndarray) -> np.ndarray:
        """Return a normalized fixed vector for similarity matching."""
        if not self.enabled:
            return np.zeros((1,), dtype=np.float32)
        handcrafted = _handcrafted_descriptor(self.cv2, image, self.input_size)
        if self._net is None:
            return handcrafted
        dnn = self._dnn_descriptor(image)
        if dnn.size == 0:
            return handcrafted
        return _normalize_vector(np.concatenate([dnn * 1.5, handcrafted], axis=0))

    def _dnn_descriptor(self, image: np.ndarray) -> np.ndarray:
        try:
            resized = self.cv2.resize(image, (self.input_size, self.input_size), interpolation=self.cv2.INTER_AREA)
            blob = self.cv2.dnn.blobFromImage(
                resized,
                scalefactor=1.0 / 255.0,
                size=(self.input_size, self.input_size),
                mean=(0.0, 0.0, 0.0),
                swapRB=True,
                crop=False,
            )
            self._net.setInput(blob)
            out = self._net.forward()
            return _normalize_vector(np.asarray(out, dtype=np.float32).reshape(-1))
        except Exception as exc:
            logger.warning("post_render_cv_embedding_forward_failed", extra={"error": _safe_error(exc)})
            return np.zeros((0,), dtype=np.float32)


class OpenCVPostRenderProbe:
    """Extract production visual consistency metrics from rendered video frames."""

    signal_source = "opencv_post_render_probe"
    probe_version = "opencv_hybrid_v2"

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        max_frames: int | None = None,
        download_timeout_s: int | None = None,
        enable_embedding: bool | None = None,
        embedding_model_path: str | None = None,
        embedding_input_size: int | None = None,
        max_regions: int | None = None,
        frame_strategy: str | None = None,
    ) -> None:
        self.enabled = settings.post_render_cv_probe_enabled if enabled is None else bool(enabled)
        self.max_frames = max(2, int(max_frames or settings.post_render_cv_probe_max_frames or 8))
        self.download_timeout_s = max(5, int(download_timeout_s or settings.post_render_cv_probe_download_timeout_s or 30))
        self.enable_embedding = (
            settings.post_render_cv_probe_enable_embedding
            if enable_embedding is None
            else bool(enable_embedding)
        )
        self.embedding_model_path = str(
            embedding_model_path
            if embedding_model_path is not None
            else settings.post_render_cv_probe_embedding_model_path
        )
        self.embedding_input_size = max(
            64,
            int(embedding_input_size or settings.post_render_cv_probe_embedding_input_size or 224),
        )
        self.max_regions = max(2, int(max_regions or settings.post_render_cv_probe_max_regions or 8))
        self.frame_strategy = str(frame_strategy or settings.post_render_cv_probe_frame_strategy or "smart").lower()

    def probe(self, *, shot: SeedanceShotPlan, result: SegmentRenderResult) -> dict[str, Any]:
        """Return structured CV signals for one rendered segment.

        The returned payload is safe to merge under `qa_signals["cv_probe"]`.
        Failures are represented as warnings/errors so the render path can make
        an explicit policy decision instead of silently trusting missing data.
        """
        if not self.enabled:
            return {
                "signal_source": self.signal_source,
                "probe_version": self.probe_version,
                "probe_enabled": False,
                "warnings": ["cv_probe_disabled"],
            }
        if result.status != "completed" or not result.video_url:
            return {
                "signal_source": self.signal_source,
                "probe_version": self.probe_version,
                "probe_enabled": True,
                "warnings": ["cv_probe_skipped_no_completed_video"],
            }

        work_dir = Path(tempfile.mkdtemp(prefix=f"cineforge_cv_probe_{shot.shot_id}_"))
        try:
            import cv2  # type: ignore

            embedder = OpenCVHybridEmbedder(
                cv2,
                enabled=self.enable_embedding,
                model_path=self.embedding_model_path,
                input_size=self.embedding_input_size,
            )
            video_path = _materialize_media(
                str(result.video_url),
                work_dir,
                "rendered_segment.mp4",
                timeout_s=self.download_timeout_s,
            )
            frames = _sample_video_frames(cv2, video_path, self.max_frames, strategy=self.frame_strategy)
            references = _load_reference_images(cv2, shot.references, work_dir, timeout_s=self.download_timeout_s)
            warnings: list[str] = []
            if not frames:
                warnings.append("cv_probe_no_decodable_frames")
            if not references:
                warnings.append("cv_probe_no_reference_images")

            metrics: dict[str, float] = {}
            signal_confidence: dict[str, float] = {}
            signal_quality: dict[str, Any] = {
                "probe_version": self.probe_version,
                "frame_strategy": self.frame_strategy,
                "frame_count": len(frames),
                "max_frames": self.max_frames,
                "reference_count": len(references),
                "reference_roles": sorted({item["role"] for item in references}),
                "embedding_backend": embedder.backend,
                "max_regions": self.max_regions,
            }
            character_refs = [item for item in references if item["role"] in _CHARACTER_ROLES]
            product_refs = [item for item in references if item["role"] in _PRODUCT_ROLES]
            style_refs = [item for item in references if item["role"] in _STYLE_ROLES]
            brand_refs = [item for item in references if item["role"] in _BRAND_ROLES]

            if frames and character_refs:
                face_score, face_warnings, face_quality, confidence = _face_consistency(
                    cv2,
                    embedder,
                    frames,
                    character_refs,
                )
                signal_quality["face"] = face_quality
                warnings.extend(face_warnings)
                if face_score is not None:
                    metrics["face_similarity"] = face_score
                    signal_confidence["face_similarity"] = confidence
                    if face_quality.get("body_outfit_similarity") is not None:
                        metrics["body_outfit_similarity"] = float(face_quality["body_outfit_similarity"])
                        signal_confidence["body_outfit_similarity"] = float(face_quality.get("body_outfit_confidence") or confidence)
                    emotion_score, emotion_confidence = _emotion_proxy_score(cv2, embedder, frames, character_refs)
                    if emotion_score is not None:
                        metrics["emotion_similarity"] = emotion_score
                        signal_confidence["emotion_similarity"] = emotion_confidence

            if frames and product_refs:
                product_score, product_confidence, product_quality = _object_reference_similarity(
                    cv2,
                    embedder,
                    frames,
                    product_refs,
                    max_regions=self.max_regions,
                    strict_logo=False,
                )
                signal_quality["product"] = product_quality
                if product_score is not None:
                    metrics["product_visibility"] = product_score
                    signal_confidence["product_visibility"] = product_confidence

            if frames and (brand_refs or product_refs):
                logo_score, logo_confidence, logo_quality = _object_reference_similarity(
                    cv2,
                    embedder,
                    frames,
                    brand_refs or product_refs,
                    max_regions=self.max_regions,
                    strict_logo=True,
                )
                signal_quality["logo"] = logo_quality
                if logo_score is not None:
                    metrics["logo_label_similarity"] = logo_score
                    signal_confidence["logo_label_similarity"] = logo_confidence

            if frames and (style_refs or references):
                style_score, style_confidence, style_quality = _style_similarity(cv2, embedder, frames, style_refs or references)
                signal_quality["style"] = style_quality
                if style_score is not None:
                    metrics["style_similarity"] = style_score
                    signal_confidence["style_similarity"] = style_confidence

            _append_quality_warnings(warnings, signal_confidence)
            if _requires_any_consistency(shot.metadata) and not metrics:
                warnings.append("cv_probe_no_metrics_for_required_consistency")

            return {
                "signal_source": self.signal_source,
                "probe_version": self.probe_version,
                "probe_enabled": True,
                "metrics": metrics,
                "signal_confidence": signal_confidence,
                "confidence": signal_confidence,
                "signal_quality": signal_quality,
                "warnings": list(dict.fromkeys(warnings)),
                **metrics,
            }
        except Exception as exc:
            logger.warning(
                "post_render_cv_probe_failed",
                extra={"shot_id": shot.shot_id, "error": _safe_error(exc)},
                exc_info=True,
            )
            return {
                "signal_source": self.signal_source,
                "probe_version": self.probe_version,
                "probe_enabled": True,
                "warnings": ["cv_probe_failed"],
                "error": _safe_error(exc),
            }
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


_CHARACTER_ROLES = {
    ReferenceRole.CHARACTER_ANCHOR.value,
    ReferenceRole.SECONDARY_CHARACTER.value,
    ReferenceRole.OUTFIT_REFERENCE.value,
}
_PRODUCT_ROLES = {
    ReferenceRole.PRODUCT_HERO.value,
    ReferenceRole.PRODUCT_DETAIL.value,
}
_STYLE_ROLES = {
    ReferenceRole.STYLE_REFERENCE.value,
    ReferenceRole.ENVIRONMENT.value,
    ReferenceRole.MOTION_STYLE.value,
}
_BRAND_ROLES = {ReferenceRole.BRAND_ASSET.value}


def _materialize_media(source: str, work_dir: Path, filename: str, *, timeout_s: int) -> Path:
    value = str(source or "").strip()
    if not value:
        raise ValueError("empty media source")
    local = Path(value)
    if local.exists():
        return local.resolve()
    if not value.lower().startswith(("http://", "https://")):
        raise ValueError("media source is neither local nor HTTP(S)")
    target = work_dir / filename
    with urllib.request.urlopen(value, timeout=timeout_s) as response:
        with target.open("wb") as fh:
            shutil.copyfileobj(response, fh)
    return target


def _sample_video_frames(cv2: Any, video_path: Path, max_frames: int, *, strategy: str) -> list[np.ndarray]:
    """Sample frames using endpoints plus motion-diverse candidates."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    positions = _candidate_frame_positions(total=total, max_frames=max_frames, strategy=strategy)
    frames_by_pos: dict[int, np.ndarray] = {}
    gray_by_pos: dict[int, np.ndarray] = {}
    previous_gray: np.ndarray | None = None
    motion_scores: list[tuple[float, int]] = []
    for pos in positions:
        if total > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        resized = _resize_for_probe(cv2, frame)
        frames_by_pos[pos] = resized
        gray = cv2.resize(cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY), (96, 96), interpolation=cv2.INTER_AREA)
        gray_by_pos[pos] = gray
        if previous_gray is not None:
            motion = float(np.mean(cv2.absdiff(previous_gray, gray)))
            motion_scores.append((motion, pos))
        previous_gray = gray
    cap.release()
    if not frames_by_pos:
        return []
    selected = set(_linspace_positions(max(frames_by_pos) + 1, min(max_frames, len(frames_by_pos))))
    if strategy in {"smart", "motion"} and motion_scores:
        keep = max(1, max_frames - len(selected))
        selected.update(pos for _, pos in sorted(motion_scores, reverse=True)[:keep])
    selected.update([min(frames_by_pos), max(frames_by_pos)])
    ordered = [pos for pos in sorted(selected) if pos in frames_by_pos]
    if len(ordered) > max_frames:
        ordered = ordered[: max_frames - 1] + [ordered[-1]]
    return [frames_by_pos[pos] for pos in ordered]


def _candidate_frame_positions(*, total: int, max_frames: int, strategy: str) -> list[int]:
    if total <= 0:
        return list(range(max_frames))
    if strategy in {"smart", "motion"}:
        count = min(total, max(max_frames * 4, max_frames))
        return _linspace_positions(total, count)
    return _linspace_positions(total, min(total, max_frames))


def _linspace_positions(total: int, count: int) -> list[int]:
    if total <= 1:
        return [0]
    return sorted(set(int(round(x)) for x in np.linspace(0, max(0, total - 1), max(1, count))))


def _load_reference_images(cv2: Any, refs: list[AssetRef], work_dir: Path, *, timeout_s: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, ref in enumerate(refs):
        if ref.kind != "image" or not ref.url:
            continue
        try:
            path = _materialize_media(ref.url, work_dir, f"ref_{index:02d}.img", timeout_s=timeout_s)
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is None:
                continue
            out.append(
                {
                    "asset_id": ref.asset_id,
                    "role": ref.role.value if hasattr(ref.role, "value") else str(ref.role),
                    "image": _resize_for_probe(cv2, image),
                }
            )
        except Exception as exc:
            logger.warning(
                "post_render_cv_probe_reference_load_failed",
                extra={"asset_id": ref.asset_id, "role": str(ref.role), "error": _safe_error(exc)},
            )
    return out


def _resize_for_probe(cv2: Any, image: np.ndarray, *, max_side: int = 720) -> np.ndarray:
    h, w = image.shape[:2]
    side = max(h, w)
    if side <= max_side:
        return image
    scale = max_side / float(side)
    return cv2.resize(image, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)


def _face_consistency(
    cv2: Any,
    embedder: OpenCVHybridEmbedder,
    frames: list[np.ndarray],
    refs: list[dict[str, Any]],
) -> tuple[float | None, list[str], dict[str, Any], float]:
    detector = _face_detector(cv2)
    ref_faces = [_largest_face_crop(cv2, detector, item["image"]) for item in refs]
    frame_faces = [_largest_face_crop(cv2, detector, frame) for frame in frames]
    ref_faces = [face for face in ref_faces if face is not None]
    frame_faces = [face for face in frame_faces if face is not None]
    warnings: list[str] = []
    quality: dict[str, Any] = {
        "reference_faces": len(ref_faces),
        "frame_faces": len(frame_faces),
    }
    face_scores = [_pair_similarity(cv2, embedder, frame_face, ref_face) for frame_face in frame_faces for ref_face in ref_faces]
    face_scores = [score for score in face_scores if score is not None]
    body_score, body_confidence = _body_outfit_similarity(cv2, embedder, frames, refs)
    if body_score is not None:
        quality["body_outfit_similarity"] = body_score
        quality["body_outfit_confidence"] = body_confidence
    if not ref_faces:
        warnings.append("cv_probe_missing_reference_face")
    if not frame_faces:
        warnings.append("cv_probe_missing_rendered_face")
    if face_scores:
        score = _top_mean([item.score for item in face_scores], limit=4)
        confidence = _top_mean([item.confidence for item in face_scores], limit=4)
        if body_score is not None:
            score = round((score * 0.78) + (body_score * 0.22), 4)
            confidence = round(max(confidence, body_confidence * 0.75), 4)
        quality["face_pair_components"] = _merge_component_quality(face_scores)
        return score, warnings, quality, confidence
    if body_score is not None:
        warnings.append("cv_probe_face_fallback_body_outfit")
        return round(body_score * 0.9, 4), warnings, quality, round(body_confidence * 0.7, 4)
    return None, warnings + ["cv_probe_face_similarity_unavailable"], quality, 0.0


def _body_outfit_similarity(
    cv2: Any,
    embedder: OpenCVHybridEmbedder,
    frames: list[np.ndarray],
    refs: list[dict[str, Any]],
) -> tuple[float | None, float]:
    scores: list[PairScore] = []
    ref_crops = [_body_outfit_crop(cv2, item["image"]) for item in refs]
    frame_crops = [_body_outfit_crop(cv2, frame) for frame in frames]
    for frame_crop in frame_crops:
        for ref_crop in ref_crops:
            score = _pair_similarity(cv2, embedder, frame_crop, ref_crop, orb_weight=0.12, hist_weight=0.28, edge_weight=0.10)
            if score is not None:
                scores.append(score)
    if not scores:
        return None, 0.0
    return _top_mean([item.score for item in scores], limit=4), _top_mean([item.confidence for item in scores], limit=4)


def _body_outfit_crop(cv2: Any, image: np.ndarray) -> np.ndarray:
    detector = _face_detector(cv2)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(24, 24))
    h, w = image.shape[:2]
    if len(faces) > 0:
        x, y, fw, fh = max(faces, key=lambda item: int(item[2]) * int(item[3]))
        x1 = max(0, int(x - fw * 0.8))
        x2 = min(w, int(x + fw * 1.8))
        y1 = max(0, int(y + fh * 0.6))
        y2 = min(h, int(y + fh * 4.2))
        if x2 > x1 and y2 > y1:
            return image[y1:y2, x1:x2]
    x1, x2 = int(w * 0.18), int(w * 0.82)
    y1, y2 = int(h * 0.18), int(h * 0.92)
    return image[y1:y2, x1:x2]


def _emotion_proxy_score(
    cv2: Any,
    embedder: OpenCVHybridEmbedder,
    frames: list[np.ndarray],
    refs: list[dict[str, Any]],
) -> tuple[float | None, float]:
    detector = _face_detector(cv2)
    ref_faces = [_largest_face_crop(cv2, detector, item["image"]) for item in refs]
    frame_faces = [_largest_face_crop(cv2, detector, frame) for frame in frames]
    ref_faces = [face for face in ref_faces if face is not None]
    frame_faces = [face for face in frame_faces if face is not None]
    if not ref_faces or not frame_faces:
        return None, 0.0
    scores = [
        _pair_similarity(cv2, embedder, frame_face, ref_face, orb_weight=0.08, hist_weight=0.22, edge_weight=0.30)
        for frame_face in frame_faces
        for ref_face in ref_faces
    ]
    scores = [score for score in scores if score is not None]
    if not scores:
        return None, 0.0
    temporal = _temporal_stability(cv2, embedder, frame_faces)
    score = (_top_mean([item.score for item in scores], limit=4) * 0.7) + (temporal * 0.3)
    confidence = min(1.0, _top_mean([item.confidence for item in scores], limit=4) * 0.75)
    return round(score, 4), round(confidence, 4)


def _object_reference_similarity(
    cv2: Any,
    embedder: OpenCVHybridEmbedder,
    frames: list[np.ndarray],
    refs: list[dict[str, Any]],
    *,
    max_regions: int,
    strict_logo: bool,
) -> tuple[float | None, float, dict[str, Any]]:
    scores: list[PairScore] = []
    region_counts: list[int] = []
    for frame in frames:
        regions = _candidate_regions(cv2, frame, max_regions=max_regions, strict_logo=strict_logo)
        region_counts.append(len(regions))
        for item in refs:
            ref_regions = _reference_regions(cv2, item["image"], strict_logo=strict_logo)
            best: PairScore | None = None
            for region in regions:
                for ref_region in ref_regions:
                    pair = _pair_similarity(
                        cv2,
                        embedder,
                        region,
                        ref_region,
                        embedding_weight=0.52 if strict_logo else 0.50,
                        orb_weight=0.34 if strict_logo else 0.26,
                        hist_weight=0.08 if strict_logo else 0.14,
                        edge_weight=0.06 if strict_logo else 0.10,
                    )
                    if pair is not None and (best is None or pair.score > best.score):
                        best = pair
            if best is not None:
                scores.append(best)
    quality = {
        "regions_per_frame": round(float(np.mean(region_counts)), 2) if region_counts else 0.0,
        "reference_count": len(refs),
        "pair_count": len(scores),
        "strict_logo": strict_logo,
        "components": _merge_component_quality(scores),
    }
    if not scores:
        return None, 0.0, quality
    limit = min(5, len(scores))
    return _top_mean([item.score for item in scores], limit=limit), _top_mean([item.confidence for item in scores], limit=limit), quality


def _candidate_regions(cv2: Any, frame: np.ndarray, *, max_regions: int, strict_logo: bool) -> list[np.ndarray]:
    h, w = frame.shape[:2]
    regions: list[np.ndarray] = [frame]
    for scale in (0.82, 0.64, 0.46):
        crop_w, crop_h = int(w * scale), int(h * scale)
        x1, y1 = max(0, (w - crop_w) // 2), max(0, (h - crop_h) // 2)
        regions.append(frame[y1 : y1 + crop_h, x1 : x1 + crop_w])
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 60, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[tuple[int, int, int, int, float]] = []
    frame_area = float(max(1, h * w))
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area_ratio = (bw * bh) / frame_area
        min_area = 0.004 if strict_logo else 0.015
        max_area = 0.45 if strict_logo else 0.75
        if bw < 16 or bh < 16 or area_ratio < min_area or area_ratio > max_area:
            continue
        boxes.append((x, y, bw, bh, area_ratio))
    for x, y, bw, bh, _ in sorted(boxes, key=lambda item: item[4], reverse=True)[: max(0, max_regions - len(regions))]:
        pad_x, pad_y = int(bw * 0.16), int(bh * 0.16)
        x1, y1 = max(0, x - pad_x), max(0, y - pad_y)
        x2, y2 = min(w, x + bw + pad_x), min(h, y + bh + pad_y)
        if x2 > x1 and y2 > y1:
            regions.append(frame[y1:y2, x1:x2])
    return [region for region in regions[:max_regions] if region.size > 0]


def _reference_regions(cv2: Any, image: np.ndarray, *, strict_logo: bool) -> list[np.ndarray]:
    if not strict_logo:
        return [image]
    h, w = image.shape[:2]
    regions = [image]
    x1, x2 = int(w * 0.2), int(w * 0.8)
    y1, y2 = int(h * 0.2), int(h * 0.8)
    if x2 > x1 and y2 > y1:
        regions.append(image[y1:y2, x1:x2])
    return regions


def _style_similarity(
    cv2: Any,
    embedder: OpenCVHybridEmbedder,
    frames: list[np.ndarray],
    refs: list[dict[str, Any]],
) -> tuple[float | None, float, dict[str, Any]]:
    frame_desc = [embedder.descriptor(frame) for frame in frames]
    ref_desc = [embedder.descriptor(item["image"]) for item in refs]
    frame_desc = [item for item in frame_desc if item.size > 1]
    ref_desc = [item for item in ref_desc if item.size > 1]
    palette_scores = [_hist_similarity(cv2, frame, item["image"], hsv=True) for frame in frames for item in refs]
    edge_scores = [_edge_similarity(cv2, frame, item["image"]) for frame in frames for item in refs]
    palette_scores = [score for score in palette_scores if score is not None]
    edge_scores = [score for score in edge_scores if score is not None]
    embedding_score = None
    if frame_desc and ref_desc:
        embedding_score = _cosine(np.mean(frame_desc, axis=0), np.mean(ref_desc, axis=0))
    components = {
        "embedding": embedding_score,
        "palette": float(np.mean(palette_scores)) if palette_scores else None,
        "edge": float(np.mean(edge_scores)) if edge_scores else None,
        "temporal": _temporal_stability(cv2, embedder, frames),
    }
    weighted = _weighted_score(
        {
            "embedding": (components["embedding"], 0.50),
            "palette": (components["palette"], 0.28),
            "edge": (components["edge"], 0.12),
            "temporal": (components["temporal"], 0.10),
        }
    )
    quality = {
        "frame_count": len(frames),
        "reference_count": len(refs),
        "embedding_backend": embedder.backend,
        "components": {k: round(float(v), 4) for k, v in components.items() if v is not None},
    }
    if weighted is None:
        return None, 0.0, quality
    score, confidence = weighted
    return round(score, 4), round(confidence, 4), quality


def _face_detector(cv2: Any) -> Any:
    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    return cv2.CascadeClassifier(str(cascade_path))


def _largest_face_crop(cv2: Any, detector: Any, image: np.ndarray) -> np.ndarray | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(32, 32))
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda item: int(item[2]) * int(item[3]))
    pad_x, pad_y = int(w * 0.18), int(h * 0.22)
    x1, y1 = max(0, x - pad_x), max(0, y - pad_y)
    x2, y2 = min(image.shape[1], x + w + pad_x), min(image.shape[0], y + h + pad_y)
    return image[y1:y2, x1:x2]


def _pair_similarity(
    cv2: Any,
    embedder: OpenCVHybridEmbedder,
    a: np.ndarray,
    b: np.ndarray,
    *,
    embedding_weight: float = 0.50,
    orb_weight: float = 0.22,
    hist_weight: float = 0.18,
    edge_weight: float = 0.10,
) -> PairScore | None:
    embedding = _cosine(embedder.descriptor(a), embedder.descriptor(b)) if embedder.enabled else None
    orb = _orb_similarity(cv2, a, b)
    hist = _hist_similarity(cv2, a, b)
    edge = _edge_similarity(cv2, a, b)
    weighted = _weighted_score(
        {
            "embedding": (embedding, embedding_weight),
            "orb": (orb, orb_weight),
            "hist": (hist, hist_weight),
            "edge": (edge, edge_weight),
        }
    )
    if weighted is None:
        return None
    score, confidence = weighted
    components = {
        key: round(float(value), 4)
        for key, value in {
            "embedding": embedding,
            "orb": orb,
            "hist": hist,
            "edge": edge,
        }.items()
        if value is not None
    }
    return PairScore(score=round(score, 4), confidence=round(confidence, 4), components=components)


def _handcrafted_descriptor(cv2: Any, image: np.ndarray, input_size: int) -> np.ndarray:
    resized = cv2.resize(image, (input_size, input_size), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
    hist_hs = cv2.calcHist([hsv], [0, 1], None, [24, 16], [0, 180, 0, 256]).reshape(-1)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    lbp = _lbp_histogram(gray)
    edge_hist = _edge_orientation_histogram(cv2, gray)
    color_moments = _color_moments(hsv)
    hog = _hog_descriptor(cv2, gray, input_size)
    return _normalize_vector(np.concatenate([hist_hs, color_moments, edge_hist, lbp, hog], axis=0).astype(np.float32))


def _color_moments(image: np.ndarray) -> np.ndarray:
    channels = []
    for index in range(image.shape[2]):
        values = image[:, :, index].astype(np.float32).reshape(-1)
        channels.extend([float(np.mean(values)), float(np.std(values)), float(np.percentile(values, 25)), float(np.percentile(values, 75))])
    return np.asarray(channels, dtype=np.float32) / 255.0


def _lbp_histogram(gray: np.ndarray) -> np.ndarray:
    center = gray[1:-1, 1:-1]
    code = np.zeros_like(center, dtype=np.uint8)
    offsets = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]
    for bit, (dy, dx) in enumerate(offsets):
        code |= ((gray[1 + dy : gray.shape[0] - 1 + dy, 1 + dx : gray.shape[1] - 1 + dx] >= center) << bit).astype(np.uint8)
    hist, _ = np.histogram(code, bins=32, range=(0, 256))
    return _normalize_vector(hist.astype(np.float32))


def _edge_orientation_histogram(cv2: Any, gray: np.ndarray) -> np.ndarray:
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude, angle = cv2.cartToPolar(gx, gy, angleInDegrees=True)
    hist, _ = np.histogram(angle.reshape(-1), bins=24, range=(0, 360), weights=magnitude.reshape(-1))
    return _normalize_vector(hist.astype(np.float32))


def _hog_descriptor(cv2: Any, gray: np.ndarray, input_size: int) -> np.ndarray:
    try:
        win = (input_size, input_size)
        hog = cv2.HOGDescriptor(win, (16, 16), (8, 8), (8, 8), 9)
        desc = hog.compute(cv2.resize(gray, win, interpolation=cv2.INTER_AREA))
        if desc is None:
            return np.zeros((0,), dtype=np.float32)
        # Downsample the HOG vector into stable bins so probe payload stays fast.
        flat = desc.reshape(-1).astype(np.float32)
        chunks = np.array_split(flat, 128)
        return _normalize_vector(np.asarray([float(np.mean(chunk)) for chunk in chunks], dtype=np.float32))
    except Exception:
        return np.zeros((0,), dtype=np.float32)


def _hist_similarity(cv2: Any, a: np.ndarray, b: np.ndarray, *, hsv: bool = False) -> float | None:
    try:
        if hsv:
            a = cv2.cvtColor(a, cv2.COLOR_BGR2HSV)
            b = cv2.cvtColor(b, cv2.COLOR_BGR2HSV)
            channels = [0, 1]
            ranges = [0, 180, 0, 256]
            bins = [32, 24]
        else:
            channels = [0, 1, 2]
            ranges = [0, 256, 0, 256, 0, 256]
            bins = [16, 16, 16]
        hist_a = cv2.calcHist([a], channels, None, bins, ranges)
        hist_b = cv2.calcHist([b], channels, None, bins, ranges)
        cv2.normalize(hist_a, hist_a)
        cv2.normalize(hist_b, hist_b)
        score = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)
        return _clamp01((float(score) + 1.0) / 2.0)
    except Exception:
        return None


def _edge_similarity(cv2: Any, a: np.ndarray, b: np.ndarray) -> float | None:
    try:
        edge_a = cv2.Canny(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), 70, 160)
        edge_b = cv2.Canny(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), 70, 160)
        hist_a = cv2.calcHist([edge_a], [0], None, [32], [0, 256])
        hist_b = cv2.calcHist([edge_b], [0], None, [32], [0, 256])
        cv2.normalize(hist_a, hist_a)
        cv2.normalize(hist_b, hist_b)
        score = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)
        return _clamp01((float(score) + 1.0) / 2.0)
    except Exception:
        return None


def _orb_similarity(cv2: Any, a: np.ndarray, b: np.ndarray) -> float | None:
    try:
        orb = cv2.ORB_create(nfeatures=900, scaleFactor=1.2, nlevels=8)
        kp_a, des_a = orb.detectAndCompute(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), None)
        kp_b, des_b = orb.detectAndCompute(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), None)
        if des_a is None or des_b is None or not kp_a or not kp_b:
            return None
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = matcher.match(des_a, des_b)
        if not matches:
            return None
        distances = [float(match.distance) for match in matches]
        good = [distance for distance in distances if distance <= 60]
        ratio = len(good) / max(8.0, float(min(len(kp_a), len(kp_b))))
        quality = 1.0 - min(1.0, (float(np.mean(sorted(distances)[: min(20, len(distances))])) / 96.0))
        return _clamp01((ratio * 0.65) + (quality * 0.35))
    except Exception:
        return None


def _temporal_stability(cv2: Any, embedder: OpenCVHybridEmbedder, images: list[np.ndarray]) -> float:
    if len(images) < 2:
        return 1.0
    scores = [
        _cosine(embedder.descriptor(images[i - 1]), embedder.descriptor(images[i]))
        for i in range(1, len(images))
    ]
    scores = [score for score in scores if score is not None]
    return float(np.mean(scores)) if scores else 0.5


def _weighted_score(components: dict[str, tuple[float | None, float]]) -> tuple[float, float] | None:
    available = [(score, weight) for score, weight in components.values() if score is not None and weight > 0]
    if not available:
        return None
    total_weight = sum(weight for _, weight in available)
    full_weight = sum(weight for _, weight in components.values() if weight > 0)
    score = sum(float(score) * weight for score, weight in available) / max(1e-6, total_weight)
    confidence = min(1.0, total_weight / max(1e-6, full_weight))
    return _clamp01(score), _clamp01(confidence)


def _cosine(a: np.ndarray, b: np.ndarray) -> float | None:
    if a.size == 0 or b.size == 0 or a.shape != b.shape:
        return None
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1e-8:
        return None
    return _clamp01((float(np.dot(a, b) / denom) + 1.0) / 2.0)


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    flat = np.asarray(vector, dtype=np.float32).reshape(-1)
    if flat.size == 0:
        return flat
    norm = float(np.linalg.norm(flat))
    if norm <= 1e-8:
        return flat
    return flat / norm


def _top_mean(values: list[float], *, limit: int) -> float:
    if not values:
        return 0.0
    return round(float(np.mean(sorted(values, reverse=True)[: max(1, limit)])), 4)


def _merge_component_quality(scores: list[PairScore]) -> dict[str, float]:
    if not scores:
        return {}
    keys = sorted({key for score in scores for key in score.components})
    return {
        key: round(float(np.mean([score.components[key] for score in scores if key in score.components])), 4)
        for key in keys
    }


def _append_quality_warnings(warnings: list[str], signal_confidence: dict[str, float]) -> None:
    for metric, confidence in signal_confidence.items():
        if confidence < 0.35:
            warnings.append(f"cv_probe_low_confidence_{metric}")


def _requires_any_consistency(metadata: dict[str, Any]) -> bool:
    return any(
        bool(metadata.get(key))
        for key in (
            "needs_identity_consistency",
            "needs_product_consistency",
            "needs_style_consistency",
            "needs_emotion_consistency",
            "consistency_policy_action",
        )
    )


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _safe_error(exc: Exception) -> str:
    return str(exc).replace("\n", " ").replace("\r", " ")[:300]


__all__ = ["OpenCVPostRenderProbe", "OpenCVHybridEmbedder"]
