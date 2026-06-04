"""Local media probing for render QA.

Uses ffprobe/ffmpeg when available to validate downloaded MP4 clips before assembly.
This is a deterministic technical gate; semantic/pixel checks remain the job of
the future visual evaluator.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional


def probe_media_file(path: str | Path, *, expected_duration_s: Optional[float] = None) -> dict[str, Any]:
    """Return a fail-soft ffprobe report for a local media file."""
    p = Path(path)
    report: dict[str, Any] = {
        "path": str(p),
        "exists": p.exists(),
        "size_bytes": p.stat().st_size if p.exists() else 0,
        "expected_duration_s": expected_duration_s,
        "status": "unavailable",
        "errors": [],
        "warnings": [],
    }
    if not p.exists():
        report["status"] = "fail"
        report["errors"].append("file_missing")
        return report
    if report["size_bytes"] <= 0:
        report["status"] = "fail"
        report["errors"].append("file_empty")
        return report

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        report["warnings"].append("ffprobe_not_available")
        return report

    try:
        proc = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(p),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception as exc:
        report["status"] = "warn"
        report["warnings"].append(f"ffprobe_exception:{type(exc).__name__}")
        return report

    if proc.returncode != 0:
        report["status"] = "fail"
        report["errors"].append((proc.stderr or "ffprobe_failed").strip()[:240])
        return report

    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        report["status"] = "warn"
        report["warnings"].append("ffprobe_json_parse_failed")
        return report

    streams = data.get("streams") or []
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    fmt = data.get("format") or {}
    duration = _to_float(fmt.get("duration"))
    if duration is None and video_streams:
        duration = _to_float(video_streams[0].get("duration"))

    report.update({
        "status": "pass",
        "duration_s": duration,
        "format_name": fmt.get("format_name"),
        "bit_rate": _to_int(fmt.get("bit_rate")),
        "video_stream_count": len(video_streams),
        "audio_stream_count": len(audio_streams),
        "width": _to_int(video_streams[0].get("width")) if video_streams else None,
        "height": _to_int(video_streams[0].get("height")) if video_streams else None,
        "video_codec": video_streams[0].get("codec_name") if video_streams else None,
        "audio_codec": audio_streams[0].get("codec_name") if audio_streams else None,
    })

    if not video_streams:
        report["status"] = "fail"
        report["errors"].append("no_video_stream")

    if expected_duration_s and duration:
        delta = abs(float(duration) - float(expected_duration_s))
        report["duration_delta_s"] = round(delta, 3)
        if delta > max(1.5, float(expected_duration_s) * 0.25):
            report["status"] = "warn" if report["status"] == "pass" else report["status"]
            report["warnings"].append("duration_mismatch")
    if audio_streams:
        report["audio_quality"] = analyze_audio_quality(p, duration_s=duration)
    return report


def analyze_audio_quality(path: str | Path, *, duration_s: Optional[float] = None) -> dict[str, Any]:
    """Return fail-soft loudness and silence metrics for a rendered clip.

    Uses ffmpeg's built-in `silencedetect` and `volumedetect` filters. This is
    deterministic and cheap; it does not attempt speech/lip-sync semantics.
    """
    p = Path(path)
    report: dict[str, Any] = {
        "status": "unavailable",
        "source_path": str(p),
        "duration_s": duration_s,
        "warnings": [],
        "errors": [],
    }
    if not p.exists():
        report["status"] = "fail"
        report["errors"].append("file_missing")
        return report

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        report["warnings"].append("ffmpeg_not_available")
        return report

    try:
        proc = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-nostats",
                "-i", str(p),
                "-af", "silencedetect=noise=-45dB:d=1,volumedetect",
                "-f", "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
    except Exception as exc:
        report["status"] = "warn"
        report["warnings"].append(f"ffmpeg_audio_exception:{type(exc).__name__}")
        return report

    stderr = proc.stderr or ""
    if proc.returncode != 0 and "mean_volume" not in stderr:
        report["status"] = "warn"
        report["warnings"].append((stderr or "ffmpeg_audio_failed").strip()[:240])
        return report

    mean_volume = _parse_db(stderr, "mean_volume")
    max_volume = _parse_db(stderr, "max_volume")
    silence_total = _parse_silence_total(stderr)
    duration = float(duration_s or 0)
    silence_ratio = (silence_total / duration) if duration > 0 else None
    report.update({
        "status": "pass",
        "mean_volume_db": mean_volume,
        "max_volume_db": max_volume,
        "silence_total_s": round(silence_total, 3),
        "silence_ratio": round(silence_ratio, 3) if silence_ratio is not None else None,
    })

    if mean_volume is None and max_volume is None:
        report["status"] = "warn"
        report["warnings"].append("audio_volume_metrics_unavailable")
    elif (max_volume is not None and max_volume < -38) or (mean_volume is not None and mean_volume < -50):
        report["status"] = "warn"
        report["warnings"].append("audio_probably_too_quiet")

    if silence_ratio is not None and silence_ratio >= 0.85:
        report["status"] = "warn"
        report["warnings"].append("audio_mostly_silent")
    elif silence_ratio is not None and silence_ratio >= 0.55:
        report["status"] = "warn"
        report["warnings"].append("audio_high_silence_ratio")
    return report


def sample_video_frames(
    path: str | Path,
    output_dir: str | Path,
    *,
    duration_s: Optional[float] = None,
    prefix: str = "frame",
) -> dict[str, Any]:
    """Extract first/middle/last-ish frames for future visual QA.

    Returns a fail-soft report with local frame paths. The caller owns cleanup
    because the render worker already removes its per-job temp directory after
    successful upload.
    """
    p = Path(path)
    out_dir = Path(output_dir)
    report: dict[str, Any] = {
        "status": "unavailable",
        "source_path": str(p),
        "output_dir": str(out_dir),
        "frames": [],
        "errors": [],
        "warnings": [],
    }
    if not p.exists():
        report["status"] = "fail"
        report["errors"].append("file_missing")
        return report

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        report["warnings"].append("ffmpeg_not_available")
        return report

    out_dir.mkdir(parents=True, exist_ok=True)
    duration = float(duration_s or 0)
    timestamps = _sample_timestamps(duration)
    ok_count = 0
    for label, timestamp in timestamps:
        out_path = out_dir / f"{prefix}_{label}.jpg"
        try:
            proc = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-ss", f"{timestamp:.3f}",
                    "-i", str(p),
                    "-frames:v", "1",
                    "-q:v", "3",
                    str(out_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except Exception as exc:
            report["warnings"].append(f"ffmpeg_exception:{label}:{type(exc).__name__}")
            continue
        if proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            ok_count += 1
            report["frames"].append({
                "label": label,
                "timestamp_s": round(timestamp, 3),
                "path": str(out_path),
                "size_bytes": out_path.stat().st_size,
            })
        else:
            report["warnings"].append(f"frame_sample_failed:{label}:{(proc.stderr or '')[:120]}")

    if ok_count == 0:
        report["status"] = "warn"
        report["warnings"].append("no_frames_sampled")
    else:
        report["status"] = "pass" if ok_count == len(timestamps) else "warn"
    return report


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_db(text: str, key: str) -> Optional[float]:
    match = re.search(rf"{re.escape(key)}:\s*(-?(?:inf|\d+(?:\.\d+)?))\s*dB", text)
    if not match:
        return None
    value = match.group(1)
    if value == "-inf":
        return -999.0
    try:
        return float(value)
    except ValueError:
        return None


def _parse_silence_total(text: str) -> float:
    total = 0.0
    for match in re.finditer(r"silence_duration:\s*(\d+(?:\.\d+)?)", text):
        try:
            total += float(match.group(1))
        except ValueError:
            continue
    return total


def _sample_timestamps(duration_s: float) -> list[tuple[str, float]]:
    if duration_s <= 0:
        return [("first", 0.1), ("middle", 1.0), ("last", 2.0)]
    first = min(0.25, max(0.05, duration_s * 0.05))
    middle = max(first, duration_s * 0.5)
    last = max(first, duration_s - min(0.5, duration_s * 0.1))
    return [("first", first), ("middle", middle), ("last", last)]


__all__ = ["probe_media_file", "sample_video_frames", "analyze_audio_quality"]
