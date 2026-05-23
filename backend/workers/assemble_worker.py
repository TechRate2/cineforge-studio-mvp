"""
ASSEMBLE WORKER — Ghép videos + audio + caption thành MP4 cuối bằng FFmpeg.

Input:
- generations: list video URLs từ AtlasCloud (đã download local)
- audio_plan: voice_script + TTS audio_url HOẶC sfx_sequence
- caption_text_vn

Output: 1 MP4 9:16 ready upload R2
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from loguru import logger


class AssembleWorker:
    """FFmpeg pipeline ghép video + audio + caption."""

    def __init__(self, work_dir: Optional[str] = None):
        self.work_dir = Path(work_dir or tempfile.gettempdir()) / "ugc_assemble"
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def assemble(
        self,
        video_paths: list[str],
        audio_plan: dict,
        output_path: str,
        bgm_path: Optional[str] = None,
        target_resolution: Optional[tuple[int, int]] = None,  # (width, height) — None=9:16 default
    ) -> str:
        """Ghép tất cả thành MP4 final.

        Fix BUG-C3: target_resolution accept để aspect-aware (16:9, 1:1, 9:16).
        Fix BUG-C2: sfx_audio_url (1 MP3 đã ghép từ render_pipeline) được dùng.
        """
        logger.info(
            f"Assembling {len(video_paths)} clips → {output_path}, "
            f"target_res={target_resolution or '(1080,1920)'}"
        )

        # Sprint2 M5 — validate audio_plan UPFRONT (before expensive concat).
        # Trước đây mode="dialogue_vo" + voice_url=None silently fallback
        # shutil.copy (silent output) — user nghĩ có voice nhưng không có.
        mode = audio_plan.get("mode", "silent_native")
        voice_url = audio_plan.get("voice_audio_url")
        sfx_audio_url = audio_plan.get("sfx_audio_url")
        sfx_sequence = audio_plan.get("sfx_sequence") or []
        if mode == "dialogue_vo" and not voice_url:
            raise ValueError(
                "audio_plan.mode='dialogue_vo' requires audio_plan.voice_audio_url. "
                "Pre-render TTS via /api/v1/audio/direct/generate hoặc đổi mode='silent_native'."
            )
        if mode == "asmr_macro" and not (sfx_audio_url or sfx_sequence):
            raise ValueError(
                "audio_plan.mode='asmr_macro' requires audio_plan.sfx_audio_url "
                "(merged MP3) hoặc audio_plan.sfx_sequence[]. Pre-render SFX hoặc "
                "đổi mode='silent_native'."
            )

        # Step 1: Concat videos với aspect-aware scale
        concat_path = self.work_dir / "concat.mp4"
        self._concat_with_crossfade(video_paths, str(concat_path), target_resolution)

        # Step 2: Add audio overlay
        with_audio_path = self.work_dir / "with_audio.mp4"

        if mode == "dialogue_vo" and voice_url:
            self._overlay_voiceover(
                str(concat_path),
                voice_url,
                str(with_audio_path),
                bgm_path=bgm_path,
            )
        elif mode == "asmr_macro" and sfx_audio_url:
            # BUG-C2 fix: dùng sfx_audio_url (1 MP3 đã ghép) thay sfx_sequence
            self._overlay_voiceover(  # treat SFX MP3 như voiceover
                str(concat_path),
                sfx_audio_url,
                str(with_audio_path),
                bgm_path=bgm_path,
            )
        elif mode in ("silent_native", "asmr_macro") and sfx_sequence:
            # Legacy path — sfx_sequence list dict format
            self._overlay_sfx_and_bgm(
                str(concat_path),
                sfx_sequence,
                str(with_audio_path),
                bgm_path=bgm_path,
            )
        else:
            # No audio overlay — just copy
            shutil.copy(str(concat_path), str(with_audio_path))

        # Step 3: Burn caption VN
        with_caption_path = self.work_dir / "with_caption.mp4"
        self._burn_caption_vn(
            str(with_audio_path),
            audio_plan.get("caption_text_vn", []),
            str(with_caption_path),
        )

        # Step 4: Final touches — film grain noise cho "real UGC" feel
        self._add_film_grain(str(with_caption_path), output_path)

        logger.info(f"Assembly done: {output_path}")
        return output_path

    def _concat_with_crossfade(
        self,
        video_paths: list[str],
        output_path: str,
        target_resolution: Optional[tuple[int, int]] = None,
    ):
        """Concat N videos với scale aspect-aware.

        Fix BUG-C3: target_resolution dynamic thay vì hardcode 1080:1920.
        """
        list_file = self.work_dir / "concat_list.txt"
        list_file.write_text(
            "\n".join([f"file '{p}'" for p in video_paths])
        )

        w, h = target_resolution or (1080, 1920)  # default 9:16 nếu không truyền
        scale_filter = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
        )

        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-vf", scale_filter,
            "-y",
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    def _overlay_voiceover(
        self,
        video_path: str,
        voice_audio_path: str,
        output_path: str,
        bgm_path: Optional[str] = None,
    ):
        """Overlay TTS voice + BGM lofi."""
        if bgm_path:
            # Mix voice (100%) + BGM (-22dB)
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-i", voice_audio_path,
                "-i", bgm_path,
                "-filter_complex",
                "[1:a]volume=1.0[voice];[2:a]volume=0.08[bgm];[voice][bgm]amix=inputs=2:duration=first[aout]",
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                "-y",
                output_path,
            ]
        else:
            # Chỉ voice
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-i", voice_audio_path,
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                "-y",
                output_path,
            ]
        subprocess.run(cmd, check=True, capture_output=True)

    def _overlay_sfx_and_bgm(
        self,
        video_path: str,
        sfx_sequence: list[dict],   # [{"time_s": "0-4", "sfx_file": "/tmp/sfx0.mp3"}, ...]
        output_path: str,
        bgm_path: Optional[str] = None,
    ):
        """Overlay nhiều SFX layered + BGM lofi."""
        # Build complex filter graph
        # Production: implement multi-track overlay
        # Simplified: just BGM if available
        if bgm_path:
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-i", bgm_path,
                "-filter_complex",
                "[1:a]volume=0.15[bgm]",
                "-map", "0:v",
                "-map", "[bgm]",
                "-c:v", "copy",
                "-shortest",
                "-y",
                output_path,
            ]
            subprocess.run(cmd, check=True, capture_output=True)
        else:
            shutil.copy(video_path, output_path)

    def _burn_caption_vn(
        self,
        video_path: str,
        captions: list[dict],  # [{"time_s": "0-6", "text": "..."}]
        output_path: str,
    ):
        """Burn caption VN bằng ASS subtitle."""
        if not captions:
            shutil.copy(video_path, output_path)
            return

        # Generate .ass file
        ass_path = self.work_dir / "captions.ass"
        ass_content = self._build_ass_subtitle(captions)
        ass_path.write_text(ass_content, encoding="utf-8")

        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vf", f"ass={ass_path}",
            "-c:a", "copy",
            "-y",
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    def _build_ass_subtitle(self, captions: list[dict]) -> str:
        """Build .ass subtitle file."""
        header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BorderStyle, Outline, Alignment, MarginL, MarginR, MarginV
Style: Default,Be Vietnam Pro,48,&H00FFFFFF,&H00000000,1,3,2,20,20,200

[Events]
Format: Layer, Start, End, Style, Text
"""
        events = []
        for cap in captions:
            time_range = cap["time_s"].split("-")
            start = self._seconds_to_ass_time(float(time_range[0]))
            end = self._seconds_to_ass_time(float(time_range[1]))
            text = cap["text"].replace("\n", "\\N")
            events.append(f"Dialogue: 0,{start},{end},Default,{text}")

        return header + "\n".join(events)

    def _seconds_to_ass_time(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    def _add_film_grain(self, video_path: str, output_path: str):
        """Add noise grain để feel 'real UGC iPhone'."""
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vf", "noise=alls=6:allf=t,eq=saturation=1.03",
            "-c:a", "copy",
            "-y",
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
