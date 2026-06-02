"""Dialogue and localized speech routing policy for autonomous video.

Seedance 2.0 is the default visual director, but it is not the only good tool
for speech-heavy output. This module keeps the dialogue decision explicit:
short cinematic shots stay on Seedance, exact lip-sync/talking-head inserts are
routed to benchmarked dialogue lanes, and post-render audio is treated as a
separate sound-design pass.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


_MARKET_LANGUAGE = {
    "vn": "Vietnamese",
    "us": "English",
    "sea": "English or inferred Southeast Asian local language",
    "jp": "Japanese or clean English",
    "kr": "Korean or clean English",
    "global": "English or language inferred from brief",
    "auto": "inferred from brief and references",
}

_DIALOGUE_NICHES = {
    "education",
    "finance_education",
    "medical_wellness",
    "documentary",
    "drama",
    "ugc_review",
    "app_saas",
    "tech",
    "real_estate",
    "restaurant_hospitality",
}


@dataclass(frozen=True)
class DialogueRoutePolicy:
    route_type: str
    target_language: str
    visual_model_family: str
    dialogue_candidate: str | None
    post_process_candidate: str | None
    requires_benchmark_before_auto_route: bool
    max_dialogue_segment_s: int
    use_when: list[str]
    avoid_when: list[str]
    quality_gates: list[str]
    notes: list[str]

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def build_dialogue_route_policy(
    *,
    niche: str,
    target_market: str = "auto",
    duration_s: int = 30,
    has_dialogue: bool = False,
    reference_audio_count: int = 0,
    speaker_count: int = 1,
) -> DialogueRoutePolicy:
    """Return a deterministic speech/model route for a job or benchmark case."""
    niche_key = (niche or "ugc_review").strip().lower()
    market_key = (target_market or "auto").strip().lower()
    language = _MARKET_LANGUAGE.get(market_key, _MARKET_LANGUAGE["auto"])
    duration = int(duration_s or 30)
    speakers = max(1, int(speaker_count or 1))
    audio_refs = max(0, int(reference_audio_count or 0))
    dialogue_signal = bool(has_dialogue or (audio_refs and niche_key in _DIALOGUE_NICHES))

    if not dialogue_signal:
        return DialogueRoutePolicy(
            route_type="seedance_native_or_silent",
            target_language=language,
            visual_model_family="seedance_2_0_reference",
            dialogue_candidate=None,
            post_process_candidate="atlascloud/mmaudio-v2" if audio_refs else None,
            requires_benchmark_before_auto_route=bool(audio_refs),
            max_dialogue_segment_s=0,
            use_when=[
                "visual-first video with no exact mouth-sync requirement",
                "music, ambience, foley, ASMR, or SFX can be added after visual QA",
            ],
            avoid_when=[
                "the user expects exact spoken words from a visible face",
                "multi-person dialogue is central to the scene",
            ],
            quality_gates=[
                "visual shot passes Seedance QA first",
                "audio pass does not mask visual defects",
                "sound effect timing matches visible action",
            ],
            notes=[
                "Keep Seedance as the cinematic director; use audio models only as post-render sound design.",
            ],
        )

    if speakers >= 2:
        candidate = "atlascloud/multitalk"
        route_type = "multi_speaker_dialogue_candidate"
        max_segment = 120
        use_when = [
            "two-person conversation, interview, short drama exchange, or podcast-style insert",
            "speaker turn-taking matters more than cinematic camera motion",
        ]
        avoid_when = [
            "crowd scenes or complex body action",
            "product hero shots where packaging identity is the main risk",
        ]
    elif duration > 10:
        candidate = "atlascloud/infinitetalk"
        route_type = "long_talking_head_candidate"
        max_segment = 600
        use_when = [
            "single portrait or presenter needs continuous localized speech",
            "education, founder demo, documentary narration, or product explainer insert",
        ]
        avoid_when = [
            "high-motion cinematic coverage",
            "full-body action where Seedance reference-to-video is the better visual model",
        ]
    else:
        candidate = "wan_2_7_i2v"
        route_type = "short_lipsync_fallback"
        max_segment = 10
        use_when = [
            "5-10 second visible-face dialogue insert",
            "Vietnamese or localized creator line where driven audio matters",
        ]
        avoid_when = [
            "long dialogue scenes",
            "multi-reference product or style shots",
        ]

    return DialogueRoutePolicy(
        route_type=route_type,
        target_language=language,
        visual_model_family="seedance_2_0_reference_for_cinematic_coverage",
        dialogue_candidate=candidate,
        post_process_candidate="bytedance/lipsync/audio-to-video",
        requires_benchmark_before_auto_route=candidate != "wan_2_7_i2v",
        max_dialogue_segment_s=max_segment,
        use_when=use_when,
        avoid_when=avoid_when,
        quality_gates=[
            "localized script fits the target language and culture",
            "speech length fits the selected segment duration",
            "lip-sync accuracy passes human review before default routing",
            "identity/face stability does not regress compared with Seedance/Wan baseline",
            "dialogue insert is cut back into the Seedance scene graph with motivated edit points",
        ],
        notes=[
            f"Target speech language: {language}.",
            "Do not replace Seedance for visual storytelling; use dialogue models as inserts or repair lanes.",
            "Promote any candidate to automatic routing only after stored benchmark outputs pass QA.",
        ],
    )


__all__ = ["DialogueRoutePolicy", "build_dialogue_route_policy"]
