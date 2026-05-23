"""AUDIO TIMELINE BUILDER — V4 Sprint 1.

Replaces the naïve "single voice file overlay" pattern with a per-shot
synced timeline that respects each shot's start_s / end_s / duration_s
from the Director Plan.

Industry pattern (synthesized from MindStudio + AtlasCloud + Lovart):
    1. Per-shot TTS clips with silence padding to start_s anchor
    2. BGM cross-fade across full timeline (acrossfade 0.5s)
    3. SFX layered with `adelay` per shot trigger
    4. Final amix preserves voice clarity (voice 1.0, BGM 0.08, SFX 0.4)

Pure FFmpeg — no third-party deps beyond what assemble_worker already uses.
Returns a manifest dict; the caller passes that to AssembleWorker which
runs the actual ffmpeg commands.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
import subprocess
import tempfile

from loguru import logger


@dataclass
class AudioClip:
    """A single audio segment to lay on the timeline."""
    path: str                   # local mp3/wav path
    start_s: float              # when on the final timeline to start
    duration_s: Optional[float] = None  # auto-detect via ffprobe if None
    volume: float = 1.0
    role: str = "voice"         # voice | sfx | bgm


@dataclass
class TimelineManifest:
    """Output of build_audio_timeline. Caller passes to ffmpeg builder."""
    voice_clips: list[AudioClip] = field(default_factory=list)
    sfx_clips: list[AudioClip] = field(default_factory=list)
    bgm_path: Optional[str] = None
    bgm_volume: float = 0.08
    total_duration_s: float = 0.0


def ffprobe_duration(audio_path: str) -> Optional[float]:
    """Return audio duration in seconds via ffprobe, or None if probe fails.

    AUDIT FIX L5: silent fallback to a fixed 2.0s was hiding broken TTS
    artifacts — caller could think they had a 2-second clip when the file
    was actually 0 bytes or 30 seconds long. Now returns None on any
    failure so callers can branch (skip clip vs. use coarse estimate).
    """
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ], stderr=subprocess.STDOUT, timeout=10)
        return float(out.decode().strip())
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning(f"[audio_timeline] ffprobe fail on {audio_path}")
        return None


def build_timeline(
    shots: list[dict],
    voice_clips_by_shot_id: dict[str, str],
    *,
    sfx_clips_by_shot_id: Optional[dict[str, list[str]]] = None,
    bgm_path: Optional[str] = None,
    total_duration_s: Optional[float] = None,
) -> TimelineManifest:
    """Build a TimelineManifest from a Director Plan shot_list + TTS artifacts.

    Args:
        shots: list of shot dicts from plan.shot_list (need shot_id, start_s, duration_s).
        voice_clips_by_shot_id: {shot_id: local_path_to_TTS_mp3}
        sfx_clips_by_shot_id: optional {shot_id: [sfx_path1, sfx_path2]}
        bgm_path: optional local BGM track (auto-cross-faded)
        total_duration_s: explicit final duration; defaults to last shot end_s.
    """
    manifest = TimelineManifest(bgm_path=bgm_path)
    if not shots:
        return manifest

    # ---- Voice clips: anchor each at shot.start_s --------------------------
    for shot in shots:
        shot_id = shot.get("shot_id")
        if not shot_id or shot_id not in voice_clips_by_shot_id:
            continue
        path = voice_clips_by_shot_id[shot_id]
        if not Path(path).exists():
            logger.warning(f"[audio_timeline] voice clip missing: {path}")
            continue
        actual_dur = ffprobe_duration(path)
        if actual_dur is None:
            # AUDIT FIX L5: skip the clip rather than silently treating a broken
            # file as 2s of silence. Caller still gets the rest of the timeline.
            logger.warning(
                f"[audio_timeline] {shot_id} skipped — ffprobe failed (file size? codec?)"
            )
            continue
        shot_dur = float(shot.get("duration_s") or 2.0)
        # If TTS audio exceeds shot duration, log warning — caller may want
        # to speed up TTS or split dialogue. We DO NOT auto-clip here so
        # nothing is silently lost.
        if actual_dur > shot_dur + 0.5:
            logger.warning(
                f"[audio_timeline] {shot_id} TTS ({actual_dur:.1f}s) "
                f"exceeds shot duration ({shot_dur:.1f}s) — may overflow into next shot"
            )
        manifest.voice_clips.append(AudioClip(
            path=path,
            start_s=float(shot.get("start_s") or 0.0),
            duration_s=actual_dur,
            volume=1.0,
            role="voice",
        ))

    # ---- SFX clips: anchor at shot.start_s + small offset ------------------
    if sfx_clips_by_shot_id:
        for shot in shots:
            shot_id = shot.get("shot_id")
            sfx_list = sfx_clips_by_shot_id.get(shot_id) or []
            for i, sfx_path in enumerate(sfx_list):
                if not Path(sfx_path).exists():
                    continue
                sfx_dur = ffprobe_duration(sfx_path)
                if sfx_dur is None:
                    continue
                manifest.sfx_clips.append(AudioClip(
                    path=sfx_path,
                    start_s=float(shot.get("start_s") or 0.0) + i * 0.15,
                    duration_s=sfx_dur,
                    volume=0.4,
                    role="sfx",
                ))

    # ---- Total duration ----------------------------------------------------
    if total_duration_s is not None:
        manifest.total_duration_s = float(total_duration_s)
    elif shots:
        last_shot = shots[-1]
        manifest.total_duration_s = float(
            last_shot.get("end_s") or
            (last_shot.get("start_s", 0) + last_shot.get("duration_s", 0))
        )
    return manifest


def render_timeline_to_audio(
    manifest: TimelineManifest,
    video_path: str,
    output_path: str,
) -> str:
    """Mux the full audio timeline onto a video. Pure FFmpeg.

    Strategy (single ffmpeg invocation):
        1. Each voice/SFX → adelay <start_ms>|<start_ms> to anchor in time
        2. amix all → master audio bus
        3. If BGM present, loop-pad it to total duration then amix at low vol
        4. Map video stream from input video, audio from filter_complex output
    """
    if not manifest.voice_clips and not manifest.sfx_clips and not manifest.bgm_path:
        # No audio overlay needed
        import shutil
        shutil.copy(video_path, output_path)
        return output_path

    inputs = ["-i", video_path]
    filter_parts: list[str] = []
    amix_labels: list[str] = []

    idx = 1  # input index 0 = video
    # Voice clips
    for clip in manifest.voice_clips:
        inputs.extend(["-i", clip.path])
        delay_ms = int(clip.start_s * 1000)
        label_in = f"{idx}:a"
        label_out = f"v{idx}"
        filter_parts.append(
            f"[{label_in}]adelay={delay_ms}|{delay_ms},volume={clip.volume}[{label_out}]"
        )
        amix_labels.append(f"[{label_out}]")
        idx += 1

    # SFX clips
    for clip in manifest.sfx_clips:
        inputs.extend(["-i", clip.path])
        delay_ms = int(clip.start_s * 1000)
        label_in = f"{idx}:a"
        label_out = f"s{idx}"
        filter_parts.append(
            f"[{label_in}]adelay={delay_ms}|{delay_ms},volume={clip.volume}[{label_out}]"
        )
        amix_labels.append(f"[{label_out}]")
        idx += 1

    # BGM (loop to total duration, low volume)
    if manifest.bgm_path and Path(manifest.bgm_path).exists():
        inputs.extend(["-stream_loop", "-1", "-i", manifest.bgm_path])
        dur_ms = int(manifest.total_duration_s * 1000)
        label_in = f"{idx}:a"
        label_out = "bgm"
        filter_parts.append(
            f"[{label_in}]atrim=end={manifest.total_duration_s},"
            f"volume={manifest.bgm_volume}[{label_out}]"
        )
        amix_labels.append(f"[{label_out}]")
        idx += 1

    # Master mix
    if amix_labels:
        n_inputs = len(amix_labels)
        mix = "".join(amix_labels) + f"amix=inputs={n_inputs}:duration=longest:normalize=0[aout]"
        filter_parts.append(mix)
        filter_str = ";".join(filter_parts)

        cmd = ["ffmpeg", *inputs,
               "-filter_complex", filter_str,
               "-map", "0:v", "-map", "[aout]",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
               "-shortest", "-y", output_path]
        logger.info(f"[audio_timeline] ffmpeg cmd len={len(filter_str)} chars, "
                    f"{len(manifest.voice_clips)} voice, {len(manifest.sfx_clips)} sfx, "
                    f"bgm={bool(manifest.bgm_path)}")
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        except subprocess.CalledProcessError as e:
            logger.error(f"[audio_timeline] ffmpeg fail: {e.stderr.decode()[:500] if e.stderr else '?'}")
            raise
    return output_path
