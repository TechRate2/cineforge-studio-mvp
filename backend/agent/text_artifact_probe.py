"""Optional OCR probe for visible text artifacts in rendered QA frames.

AI video models often hallucinate broken text or burn captions into the frame.
This probe uses a local Tesseract CLI when available. It is fail-soft: absence
of OCR tooling should never break rendering, but the QA report should clearly
show that visible-text verification was not performed.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


_BAD_TEXT_HINTS = (
    "watermark",
    "logo",
    "subscribe",
    "click here",
    "lorem",
)


def probe_text_artifacts(frame_samples: dict[str, Any], *, caption_expected: bool = False) -> dict[str, Any]:
    frames = [
        f for f in (frame_samples.get("frames") or [])
        if f.get("path") and Path(str(f.get("path"))).exists()
    ][:3]
    report: dict[str, Any] = {
        "status": "unavailable",
        "frame_count": len(frames),
        "caption_expected": caption_expected,
        "warnings": [],
        "errors": [],
        "detections": [],
    }
    if not frames:
        report["warnings"].append("no_local_frames_for_ocr")
        return report

    tesseract = shutil.which("tesseract")
    if not tesseract:
        report["warnings"].append("tesseract_not_available")
        return report

    detections: list[dict[str, Any]] = []
    for frame in frames:
        path = str(frame.get("path"))
        try:
            proc = subprocess.run(
                [tesseract, path, "stdout", "--psm", "6"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except Exception as exc:
            report["warnings"].append(f"tesseract_exception:{type(exc).__name__}")
            continue
        if proc.returncode != 0:
            report["warnings"].append(f"tesseract_failed:{Path(path).name}:{(proc.stderr or '')[:120]}")
            continue
        text = _clean_ocr_text(proc.stdout or "")
        if text:
            detections.append({
                "label": frame.get("label"),
                "timestamp_s": frame.get("timestamp_s"),
                "path": path,
                "text": text[:300],
                "suspicious": _is_suspicious_text(text),
            })

    report["detections"] = detections
    suspicious = [d for d in detections if d.get("suspicious")]
    if suspicious:
        report["status"] = "warn"
        report["warnings"].append("visible_text_artifact_risk")
    elif detections and not caption_expected:
        report["status"] = "warn"
        report["warnings"].append("unexpected_visible_text")
    else:
        report["status"] = "pass"
    return report


def _clean_ocr_text(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    cleaned = " ".join(line for line in lines if line)
    # Drop tiny OCR noise while keeping real captions/watermarks.
    tokens = [t for t in cleaned.split() if len(t) >= 2]
    return " ".join(tokens)


def _is_suspicious_text(text: str) -> bool:
    lower = text.lower()
    if any(hint in lower for hint in _BAD_TEXT_HINTS):
        return True
    alnum = re.sub(r"[^a-zA-Z0-9]", "", text)
    if len(alnum) >= 8:
        # Many generated artifacts are long unreadable OCR fragments.
        vowels = sum(1 for ch in alnum.lower() if ch in "aeiou")
        return vowels / max(1, len(alnum)) < 0.18
    return False


__all__ = ["probe_text_artifacts"]
