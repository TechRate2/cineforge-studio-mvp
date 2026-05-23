"""
DURATION EXTENDER — Chia long-form duration thành multi-generation + continuity refs.

Ví dụ: User chọn 25s + Vidu Q3 (max 8s) → Tự chia 3 gen × 8.3s với continuity chain.
"""

import math
from typing import Optional


def plan_generations(
    total_duration_s: int,
    model_max_duration_s: int,
) -> list[dict]:
    """Chia tổng duration thành N generation.

    Returns:
        [
          {"gen_index": 0, "duration_s": 8.0, "needs_continuity_ref": False},
          {"gen_index": 1, "duration_s": 8.0, "needs_continuity_ref": True},
          {"gen_index": 2, "duration_s": 9.0, "needs_continuity_ref": True},
        ]
    """
    if total_duration_s <= model_max_duration_s:
        return [
            {
                "gen_index": 0,
                "duration_s": total_duration_s,
                "needs_continuity_ref": False,
            }
        ]

    n_gens = math.ceil(total_duration_s / model_max_duration_s)
    base_duration = total_duration_s // n_gens
    remainder = total_duration_s - (base_duration * n_gens)

    plans = []
    for i in range(n_gens):
        duration = base_duration + (1 if i < remainder else 0)
        plans.append({
            "gen_index": i,
            "duration_s": duration,
            "needs_continuity_ref": i > 0,
        })

    return plans


def get_continuity_ref_url(
    gen_index: int,
    previous_video_urls: list[str],
) -> Optional[str]:
    """Get URL của last_frame_of_previous_gen làm continuity reference.

    Trong production: trích frame cuối của video gen-1 bằng FFmpeg
    rồi upload R2 → trả về URL.
    """
    if gen_index == 0 or not previous_video_urls:
        return None

    # TODO: Trích last frame của previous_video_urls[gen_index-1] bằng FFmpeg
    # Hiện tại return placeholder
    return f"{previous_video_urls[gen_index-1]}#t=last_frame"


def extract_last_frame_ffmpeg(video_path: str, output_path: str) -> str:
    """Trích frame cuối của video bằng FFmpeg.

    Production usage trong assemble_worker:
        last_frame = extract_last_frame_ffmpeg(
            video_path="/tmp/gen0.mp4",
            output_path="/tmp/last_frame_gen0.png"
        )
        # Upload last_frame lên R2 → return URL
        # URL này dùng làm ref cho gen 1
    """
    import subprocess

    cmd = [
        "ffmpeg",
        "-sseof", "-0.1",  # Seek to last 100ms
        "-i", video_path,
        "-frames:v", "1",
        "-y",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path
