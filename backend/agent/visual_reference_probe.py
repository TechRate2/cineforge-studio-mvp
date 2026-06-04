"""Fail-soft visual reference similarity probe.

This is a lightweight baseline, not a face/product embedding model. It compares
sampled video frames with the image references using perceptual average hashes
and coarse color histograms. Low similarity is useful evidence for review/retry,
but high similarity is not proof of identity or product fidelity.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from PIL import Image, ImageOps


def probe_visual_reference_similarity(
    *,
    frame_samples: dict[str, Any],
    reference_image_urls: list[str],
    timeout_s: float = 8.0,
) -> dict[str, Any]:
    frames = [
        f for f in (frame_samples.get("frames") or [])
        if f.get("path") and Path(str(f.get("path"))).exists()
    ][:3]
    refs = list(reference_image_urls or [])[:4]
    report: dict[str, Any] = {
        "status": "unavailable",
        "frame_count": len(frames),
        "reference_count": len(refs),
        "warnings": [],
        "errors": [],
        "matches": [],
        "average_best_similarity": None,
        "max_similarity": None,
    }
    if not frames:
        report["warnings"].append("no_local_frames_for_visual_reference_probe")
        return report
    if not refs:
        report["warnings"].append("no_image_refs_for_visual_reference_probe")
        return report

    try:
        frame_features = [
            _features_from_image(Image.open(str(frame["path"])).convert("RGB"))
            for frame in frames
        ]
    except Exception as exc:
        report["status"] = "warn"
        report["warnings"].append(f"frame_feature_error:{type(exc).__name__}")
        return report

    ref_features: list[dict[str, Any]] = []
    for url in refs:
        try:
            ref_features.append(_features_from_image(_load_reference_image(url, timeout_s=timeout_s)))
        except Exception as exc:
            report["warnings"].append(f"ref_load_error:{type(exc).__name__}")

    if not ref_features:
        report["warnings"].append("no_reference_features")
        return report

    matches: list[dict[str, Any]] = []
    best_scores: list[float] = []
    for frame_index, feature in enumerate(frame_features):
        scored = [
            _similarity(feature, ref_feature)
            for ref_feature in ref_features
        ]
        best = max(scored) if scored else 0.0
        best_scores.append(best)
        matches.append({
            "frame_index": frame_index,
            "best_similarity": round(best, 3),
        })

    avg_best = sum(best_scores) / max(1, len(best_scores))
    max_similarity = max(best_scores) if best_scores else 0.0
    report.update({
        "matches": matches,
        "average_best_similarity": round(avg_best, 3),
        "max_similarity": round(max_similarity, 3),
    })
    if avg_best < 0.22 and max_similarity < 0.30:
        report["status"] = "warn"
        report["warnings"].append("visual_reference_similarity_low")
    else:
        report["status"] = "pass"
    return report


def _load_reference_image(url: str, *, timeout_s: float) -> Image.Image:
    if url.startswith("file://"):
        return Image.open(url[7:]).convert("RGB")
    path = Path(url)
    if path.exists():
        return Image.open(path).convert("RGB")
    if url.startswith(("http://", "https://")):
        with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
            res = client.get(url)
            res.raise_for_status()
            return Image.open(BytesIO(res.content)).convert("RGB")
    raise ValueError("unsupported_reference_url")


def _features_from_image(img: Image.Image) -> dict[str, Any]:
    img = ImageOps.exif_transpose(img).convert("RGB")
    small = ImageOps.grayscale(img.resize((8, 8), Image.Resampling.LANCZOS))
    arr = np.asarray(small, dtype=np.float32)
    ahash = arr >= float(arr.mean())
    hist_img = img.resize((96, 96), Image.Resampling.BILINEAR)
    rgb = np.asarray(hist_img, dtype=np.uint8)
    hist, _ = np.histogramdd(
        rgb.reshape(-1, 3),
        bins=(4, 4, 4),
        range=((0, 256), (0, 256), (0, 256)),
    )
    hist = hist.astype(np.float32).reshape(-1)
    total = float(hist.sum()) or 1.0
    hist = hist / total
    return {"ahash": ahash, "hist": hist}


def _similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
    hash_a = np.asarray(a["ahash"], dtype=bool)
    hash_b = np.asarray(b["ahash"], dtype=bool)
    hash_sim = 1.0 - (float(np.count_nonzero(hash_a != hash_b)) / 64.0)
    hist_a = np.asarray(a["hist"], dtype=np.float32)
    hist_b = np.asarray(b["hist"], dtype=np.float32)
    hist_sim = float(np.minimum(hist_a, hist_b).sum())
    return max(0.0, min(1.0, (0.55 * hash_sim) + (0.45 * hist_sim)))


__all__ = ["probe_visual_reference_similarity"]
