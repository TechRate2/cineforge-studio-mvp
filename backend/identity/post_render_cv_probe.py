"""OpenCV-backed post-render visual consistency probe.

The probe derives deterministic signals from the rendered segment video and
reference images. It is intentionally model-light: OpenCV frame extraction,
Haar face detection, color histograms, edge histograms, and ORB feature matching
provide real measurements without introducing an external CV service contract.
Future CV services can replace this class while keeping the same signal schema.
"""
from __future__ import annotations

import logging
import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

from core.config import settings
from pipeline.contracts import AssetRef, ReferenceRole, SeedanceShotPlan
from workers.segment_renderer import SegmentRenderResult

logger = logging.getLogger(__name__)


class OpenCVPostRenderProbe:
    """Extract visual consistency metrics from real rendered video frames."""

    signal_source = "opencv_post_render_probe"

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        max_frames: int | None = None,
        download_timeout_s: int | None = None,
    ) -> None:
        self.enabled = settings.post_render_cv_probe_enabled if enabled is None else bool(enabled)
        self.max_frames = max(2, int(max_frames or settings.post_render_cv_probe_max_frames or 6))
        self.download_timeout_s = max(5, int(download_timeout_s or settings.post_render_cv_probe_download_timeout_s or 30))

    def probe(self, *, shot: SeedanceShotPlan, result: SegmentRenderResult) -> dict[str, Any]:
        """Return CV/probe signals for one rendered segment.

        The returned payload is safe to merge under `qa_signals["cv_probe"]`.
        It never invents missing metrics; unavailable checks are reported through
        warnings and signal quality fields.
        """
        if not self.enabled:
            return {
                "signal_source": self.signal_source,
                "probe_enabled": False,
                "warnings": ["cv_probe_disabled"],
            }
        if result.status != "completed" or not result.video_url:
            return {
                "signal_source": self.signal_source,
                "probe_enabled": True,
                "warnings": ["cv_probe_skipped_no_completed_video"],
            }

        work_dir = Path(tempfile.mkdtemp(prefix=f"cineforge_cv_probe_{shot.shot_id}_"))
        try:
            import cv2  # type: ignore

            video_path = _materialize_media(str(result.video_url), work_dir, "rendered_segment.mp4", timeout_s=self.download_timeout_s)
            frames = _sample_video_frames(cv2, video_path, self.max_frames)
            references = _load_reference_images(cv2, shot.references, work_dir, timeout_s=self.download_timeout_s)
            warnings: list[str] = []
            if not frames:
                warnings.append("cv_probe_no_decodable_frames")
            if not references:
                warnings.append("cv_probe_no_reference_images")

            metrics: dict[str, float] = {}
            signal_quality: dict[str, Any] = {
                "frame_count": len(frames),
                "reference_count": len(references),
                "reference_roles": sorted({item["role"] for item in references}),
            }
            character_refs = [item for item in references if item["role"] in _CHARACTER_ROLES]
            product_refs = [item for item in references if item["role"] in _PRODUCT_ROLES]
            style_refs = [item for item in references if item["role"] in _STYLE_ROLES]
            brand_refs = [item for item in references if item["role"] in _BRAND_ROLES]

            if frames and character_refs:
                face_score, face_warnings, face_quality = _face_similarity(cv2, frames, character_refs)
                signal_quality["face"] = face_quality
                warnings.extend(face_warnings)
                if face_score is not None:
                    metrics["face_similarity"] = face_score
                    emotion_score = _emotion_proxy_score(cv2, frames, character_refs)
                    if emotion_score is not None:
                        metrics["emotion_similarity"] = emotion_score

            if frames and product_refs:
                product_score = _object_reference_similarity(cv2, frames, product_refs)
                if product_score is not None:
                    metrics["product_visibility"] = product_score

            if frames and (brand_refs or product_refs):
                logo_score = _object_reference_similarity(cv2, frames, brand_refs or product_refs)
                if logo_score is not None:
                    metrics["logo_label_similarity"] = logo_score

            if frames and (style_refs or references):
                style_score = _style_similarity(cv2, frames, style_refs or references)
                if style_score is not None:
                    metrics["style_similarity"] = style_score

            if _requires_any_consistency(shot.metadata) and not metrics:
                warnings.append("cv_probe_no_metrics_for_required_consistency")

            return {
                "signal_source": self.signal_source,
                "probe_enabled": True,
                "metrics": metrics,
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


def _sample_video_frames(cv2: Any, video_path: Path, max_frames: int) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total <= 0:
        positions = list(range(max_frames))
    else:
        positions = sorted(set(int(round(x)) for x in np.linspace(0, max(0, total - 1), max_frames)))
    frames: list[np.ndarray] = []
    for pos in positions:
        if total > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ok, frame = cap.read()
        if ok and frame is not None:
            frames.append(_resize_for_probe(cv2, frame))
    cap.release()
    return frames


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
            out.append({
                "asset_id": ref.asset_id,
                "role": ref.role.value if hasattr(ref.role, "value") else str(ref.role),
                "image": _resize_for_probe(cv2, image),
            })
        except Exception as exc:
            logger.warning(
                "post_render_cv_probe_reference_load_failed",
                extra={"asset_id": ref.asset_id, "role": str(ref.role), "error": _safe_error(exc)},
            )
    return out


def _resize_for_probe(cv2: Any, image: np.ndarray, *, max_side: int = 640) -> np.ndarray:
    h, w = image.shape[:2]
    side = max(h, w)
    if side <= max_side:
        return image
    scale = max_side / float(side)
    return cv2.resize(image, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)


def _face_similarity(cv2: Any, frames: list[np.ndarray], refs: list[dict[str, Any]]) -> tuple[float | None, list[str], dict[str, Any]]:
    detector = _face_detector(cv2)
    ref_faces = [_largest_face_crop(cv2, detector, item["image"]) for item in refs]
    ref_faces = [face for face in ref_faces if face is not None]
    frame_faces = [_largest_face_crop(cv2, detector, frame) for frame in frames]
    frame_faces = [face for face in frame_faces if face is not None]
    quality = {"reference_faces": len(ref_faces), "frame_faces": len(frame_faces)}
    warnings: list[str] = []
    if not ref_faces:
        warnings.append("cv_probe_missing_reference_face")
    if not frame_faces:
        warnings.append("cv_probe_missing_rendered_face")
    if not ref_faces or not frame_faces:
        return None, warnings, quality
    scores = [_hist_similarity(cv2, frame_face, ref_face) for frame_face in frame_faces for ref_face in ref_faces]
    scores = [score for score in scores if score is not None]
    if not scores:
        return None, warnings + ["cv_probe_face_similarity_unavailable"], quality
    return round(float(np.mean(sorted(scores, reverse=True)[: min(3, len(scores))])), 4), warnings, quality


def _emotion_proxy_score(cv2: Any, frames: list[np.ndarray], refs: list[dict[str, Any]]) -> float | None:
    detector = _face_detector(cv2)
    ref_faces = [_largest_face_crop(cv2, detector, item["image"]) for item in refs]
    frame_faces = [_largest_face_crop(cv2, detector, frame) for frame in frames]
    ref_faces = [face for face in ref_faces if face is not None]
    frame_faces = [face for face in frame_faces if face is not None]
    if not ref_faces or not frame_faces:
        return None
    texture_scores = [_edge_similarity(cv2, frame_face, ref_face) for frame_face in frame_faces for ref_face in ref_faces]
    texture_scores = [score for score in texture_scores if score is not None]
    if not texture_scores:
        return None
    temporal = _temporal_stability(cv2, frame_faces)
    return round(float((np.mean(texture_scores) * 0.7) + (temporal * 0.3)), 4)


def _object_reference_similarity(cv2: Any, frames: list[np.ndarray], refs: list[dict[str, Any]]) -> float | None:
    scores: list[float] = []
    for frame in frames:
        for item in refs:
            orb = _orb_similarity(cv2, frame, item["image"])
            hist = _hist_similarity(cv2, frame, item["image"])
            edge = _edge_similarity(cv2, frame, item["image"])
            candidates = [score for score in (orb, hist, edge) if score is not None]
            if candidates:
                scores.append(float(max(candidates)))
    if not scores:
        return None
    return round(float(np.mean(sorted(scores, reverse=True)[: min(3, len(scores))])), 4)


def _style_similarity(cv2: Any, frames: list[np.ndarray], refs: list[dict[str, Any]]) -> float | None:
    scores = [_hist_similarity(cv2, frame, item["image"], hsv=True) for frame in frames for item in refs]
    scores = [score for score in scores if score is not None]
    if not scores:
        return None
    return round(float(np.mean(scores)), 4)


def _face_detector(cv2: Any) -> Any:
    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    return cv2.CascadeClassifier(str(cascade_path))


def _largest_face_crop(cv2: Any, detector: Any, image: np.ndarray) -> np.ndarray | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(32, 32))
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda item: int(item[2]) * int(item[3]))
    return image[y : y + h, x : x + w]


def _hist_similarity(cv2: Any, a: np.ndarray, b: np.ndarray, *, hsv: bool = False) -> float | None:
    try:
        if hsv:
            a = cv2.cvtColor(a, cv2.COLOR_BGR2HSV)
            b = cv2.cvtColor(b, cv2.COLOR_BGR2HSV)
            channels = [0, 1]
            ranges = [0, 180, 0, 256]
            bins = [32, 32]
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
        edge_a = cv2.Canny(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), 80, 160)
        edge_b = cv2.Canny(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), 80, 160)
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
        orb = cv2.ORB_create(nfeatures=500)
        kp_a, des_a = orb.detectAndCompute(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), None)
        kp_b, des_b = orb.detectAndCompute(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), None)
        if des_a is None or des_b is None or not kp_a or not kp_b:
            return None
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = matcher.match(des_a, des_b)
        if not matches:
            return None
        good = [match for match in matches if match.distance <= 64]
        return _clamp01(len(good) / max(8.0, float(min(len(kp_a), len(kp_b)))))
    except Exception:
        return None


def _temporal_stability(cv2: Any, faces: list[np.ndarray]) -> float:
    if len(faces) < 2:
        return 1.0
    scores = [_hist_similarity(cv2, faces[i - 1], faces[i]) for i in range(1, len(faces))]
    scores = [score for score in scores if score is not None]
    return float(np.mean(scores)) if scores else 0.5


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


__all__ = ["OpenCVPostRenderProbe"]
