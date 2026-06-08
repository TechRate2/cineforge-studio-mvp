from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_video_worker_require_deliverable_video_url_rejects_local_and_stub_urls() -> None:
    from workers.video_worker import _require_deliverable_video_url

    for value in (
        "file:///tmp/render.mp4",
        "stub://render/output",
        "C:/tmp/render.mp4",
        "http://localhost:3000/render.mp4",
        "http://127.0.0.1:8000/render.mp4",
        "",
        None,
    ):
        with pytest.raises(RuntimeError, match="deliverable HTTP\\(S\\) video_url"):
            _require_deliverable_video_url(value, context="unit render")


def test_video_worker_require_deliverable_video_url_accepts_http_urls() -> None:
    from workers.video_worker import _require_deliverable_video_url

    assert (
        _require_deliverable_video_url("https://cdn.example.com/render.mp4", context="unit render")
        == "https://cdn.example.com/render.mp4"
    )


def test_first_seedance_output_url_filters_non_deliverable_segments() -> None:
    from workers.video_worker import _first_seedance_output_url

    result = SimpleNamespace(
        rendered_segments=[
            SimpleNamespace(video_url="file:///tmp/local.mp4"),
            SimpleNamespace(video_url="stub://fake-output"),
            SimpleNamespace(video_url="https://cdn.example.com/real.mp4"),
        ]
    )

    assert _first_seedance_output_url(result) == "https://cdn.example.com/real.mp4"


def test_dynamic_keyframe_memory_ignores_non_deliverable_render_outputs() -> None:
    from workers.video_worker import _populate_dynamic_keyframe_memory_from_render

    plan = SimpleNamespace(
        continuity_bible=SimpleNamespace(
            storytelling_meta={
                "scene_memory_pack": {
                    "runtime_class": "long_form",
                    "scene_count": 1,
                    "shot_count": 2,
                    "scene_memory": [{"scene_id": "SC01", "first_shot_id": "shot_1", "last_shot_id": "shot_2"}],
                    "shot_scene_map": [
                        {"shot_id": "shot_1", "scene_id": "SC01"},
                        {"shot_id": "shot_2", "scene_id": "SC01"},
                    ],
                },
                "production_graph": {"graph_id": "graph_test", "runtime_class": "long_form"},
            }
        )
    )

    memory = _populate_dynamic_keyframe_memory_from_render(
        plan=plan,  # type: ignore[arg-type]
        chain_meta=[
            {
                "shot_id": "shot_1",
                "video_url": "file:///tmp/local-shot.mp4",
                "last_frame_url": "file:///tmp/local-frame.jpg",
                "quality": {"status": "pass", "score": 94},
            },
            {
                "shot_id": "shot_2",
                "video_url": "https://cdn.example.com/shot-2.mp4",
                "last_frame_url": "stub://frame",
                "quality": {"status": "pass", "score": 91},
            },
        ],
    )

    assert memory is not None
    rendered = memory["memory_bank"]["rendered_anchors"]
    assert len(rendered) == 1
    assert rendered[0]["shot_id"] == "shot_2"
    assert rendered[0]["video_url"] == "https://cdn.example.com/shot-2.mp4"
    assert rendered[0]["last_frame_url"] is None
    assert "file:///tmp/local-shot.mp4" not in str(rendered)


def test_dynamic_keyframe_memory_contract_filters_local_and_stub_urls() -> None:
    from agent.dynamic_keyframe_memory import build_dynamic_keyframe_memory_contract

    memory = build_dynamic_keyframe_memory_contract(
        scene_memory_pack={
            "runtime_class": "long_form",
            "scene_memory": [{"scene_id": "SC01", "first_shot_id": "shot_1", "last_shot_id": "shot_2"}],
            "shot_scene_map": [
                {"shot_id": "shot_1", "scene_id": "SC01"},
                {"shot_id": "shot_2", "scene_id": "SC01"},
            ],
        },
        production_graph={"graph_id": "graph_test", "runtime_class": "long_form"},
        accepted_outputs=[
            {
                "shot_id": "shot_1",
                "video_url": "file:///tmp/local-shot.mp4",
                "last_frame_url": "https://cdn.example.com/should-not-write.jpg",
                "qa_score": 90,
            },
            {
                "shot_id": "shot_2",
                "output_url": "https://cdn.example.com/shot-2.mp4",
                "first_frame_url": "stub://first-frame",
                "last_frame_url": "file:///tmp/local-frame.jpg",
                "keyframe_url": "https://cdn.example.com/keyframe-2.jpg",
                "qa_score": 92,
            },
        ],
    )

    rendered = memory["memory_bank"]["rendered_anchors"]
    assert len(rendered) == 1
    assert rendered[0]["shot_id"] == "shot_2"
    assert rendered[0]["video_url"] == "https://cdn.example.com/shot-2.mp4"
    assert rendered[0]["first_frame_url"] is None
    assert rendered[0]["last_frame_url"] == "https://cdn.example.com/keyframe-2.jpg"
    assert rendered[0]["keyframe_url"] == "https://cdn.example.com/keyframe-2.jpg"
    assert "file:///tmp/local-shot.mp4" not in str(rendered)
    assert "stub://first-frame" not in str(rendered)
