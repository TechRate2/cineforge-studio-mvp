"""Production treatment for autonomous video generation.

A treatment is the director/producer/editor contract that sits between a raw
idea and per-shot prompts. It keeps long-form and niche-specific work from
becoming a bag of independent clips by locking narrative shape, camera grammar,
reference policy, editing rhythm, and QA risks before rendering.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ProductionTreatment:
    runtime_class: str
    production_format: str
    story_engine: str
    scene_design: list[str]
    camera_language: list[str]
    editing_rhythm: list[str]
    dialogue_policy: list[str]
    reference_policy: list[str]
    seedance_execution: list[str]
    qa_risks: list[str]
    delivery_notes: list[str]

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def build_production_treatment(
    *,
    user_idea: str,
    niche: str,
    runtime_structure: dict[str, Any],
    niche_playbook: dict[str, Any],
    market_playbook: dict[str, Any],
    reference_counts: dict[str, int],
) -> ProductionTreatment:
    runtime_class = str(runtime_structure.get("runtime_class") or "short")
    production_format = _production_format(runtime_class, niche)
    story_engine = _story_engine(
        user_idea=user_idea,
        niche=niche,
        runtime_class=runtime_class,
        niche_playbook=niche_playbook,
    )
    return ProductionTreatment(
        runtime_class=runtime_class,
        production_format=production_format,
        story_engine=story_engine,
        scene_design=_scene_design(runtime_class, niche_playbook),
        camera_language=_camera_language(runtime_class, niche_playbook),
        editing_rhythm=_editing_rhythm(runtime_class, niche),
        dialogue_policy=_dialogue_policy(market_playbook, reference_counts),
        reference_policy=_reference_policy(runtime_class, reference_counts),
        seedance_execution=_seedance_execution(runtime_class),
        qa_risks=_qa_risks(niche, runtime_class, niche_playbook),
        delivery_notes=_delivery_notes(runtime_class, market_playbook),
    )


def _production_format(runtime_class: str, niche: str) -> str:
    if runtime_class == "short":
        return "single viral short with one hook, one proof loop, one payoff"
    if runtime_class == "sequence":
        return "two-scene social sequence with a clear before/after or problem/proof arc"
    if runtime_class == "micro_film":
        return "three-act micro film with cold open, escalation, and payoff"
    if runtime_class == "short_film":
        return "short film assembled from scene groups, each with a motivated handoff"
    return f"episode-scale {niche or 'story'} production with resumable scene/chunk graph"


def _story_engine(*, user_idea: str, niche: str, runtime_class: str, niche_playbook: dict[str, Any]) -> str:
    beat_flow = " -> ".join(str(x) for x in (niche_playbook.get("beat_flow") or [])[:6])
    if niche in {"ugc_review", "ecommerce_catalog", "tech", "app_saas"}:
        engine = "proof-first commercial story: show result, expose problem, demonstrate proof, close softly"
    elif niche in {"drama", "anime_comic", "music_video"}:
        engine = "emotional narrative story: object/face hook, escalating tension, reveal, aftertaste"
    elif niche in {"education", "finance_education", "medical_wellness", "documentary"}:
        engine = "clarity story: question, wrong assumption, visual explanation, safe takeaway"
    elif niche in {"food", "beauty", "fashion", "asmr", "lifestyle", "travel", "restaurant_hospitality"}:
        engine = "sensory story: texture or atmosphere hook, ritual/process, transformation, craving/payoff"
    else:
        engine = "platform-native story: visual hook, escalating proof, memorable final image"
    return f"{engine}. Beat flow: {beat_flow or 'hook -> setup -> escalation -> payoff'}. Idea: {user_idea[:160]}"


def _scene_design(runtime_class: str, niche_playbook: dict[str, Any]) -> list[str]:
    quality = [str(x) for x in (niche_playbook.get("quality_bar") or [])[:4]]
    if runtime_class in {"short", "sequence"}:
        return [
            "one physical idea per shot",
            "first shot must be understandable with sound off",
            "avoid scene resets unless the cut creates clear contrast",
            *quality,
        ]
    return [
        "each scene needs a dramatic question and closing handoff image",
        "change location/time only at scene boundaries",
        "every scene must contain one consequence that makes the next scene necessary",
        "dialogue or VO must support visible action, never replace it",
        *quality,
    ]


def _camera_language(runtime_class: str, niche_playbook: dict[str, Any]) -> list[str]:
    camera = [str(x) for x in (niche_playbook.get("camera") or [])[:5]]
    if runtime_class in {"short", "sequence"}:
        return [
            "open with the strongest readable shot size, usually ECU/CU/product-in-use",
            "cut only when shot size, camera angle, or proof value changes",
            *camera,
        ]
    return [
        "use establishing shot only when it anchors geography or mood",
        "use close-ups for decisions, object clues, product proof, and emotional turns",
        "use a repeated camera motif to make scene groups feel connected",
        "reserve wide shots for scene transitions, not filler",
        *camera,
    ]


def _editing_rhythm(runtime_class: str, niche: str) -> list[str]:
    if niche in {"asmr", "food", "beauty"}:
        base = ["hold sensory macro shots long enough for texture payoff", "sync cuts to tactile SFX"]
    elif niche in {"tech", "app_saas", "ecommerce_catalog"}:
        base = ["cut on proof moments", "avoid unreadable UI/text walls", "show result before explanation"]
    elif niche in {"drama", "anime_comic"}:
        base = ["cut on emotional reversals", "use reaction shots as continuity glue"]
    else:
        base = ["cut on visible change", "keep every transition motivated"]
    if runtime_class in {"short", "sequence"}:
        return [*base, "front-load the hook and remove setup that is not visual"]
    return [*base, "treat each 30-60s scene group as a mini-scene, but render it as 4-15s shots"]


def _dialogue_policy(market_playbook: dict[str, Any], reference_counts: dict[str, int]) -> list[str]:
    lang = market_playbook.get("primary_language") or "inferred language"
    style = market_playbook.get("dialogue_style") or "natural concise speech"
    policy = [
        f"language target: {lang}",
        f"speech style: {style}",
        "one spoken idea per shot unless the shot is a dialogue insert",
        "caption text should be composed for post-production, not hallucinated inside generated frames",
    ]
    if int(reference_counts.get("audios") or 0) > 0:
        policy.append("audio references drive beat, voice, or lip-sync intent before any generic music choice")
    return policy


def _reference_policy(runtime_class: str, reference_counts: dict[str, int]) -> list[str]:
    images = int(reference_counts.get("images") or 0)
    videos = int(reference_counts.get("videos") or 0)
    audios = int(reference_counts.get("audios") or 0)
    policy = [
        f"image refs available: {images}; use them for identity, product, style, or environment",
        f"video refs available: {videos}; use them for camera path, gesture, action rhythm, or motion style",
        f"audio refs available: {audios}; use them for beat, SFX, ambience, voice, or lip-sync intent",
        "never mix too many competing image refs into a shot when one character/product anchor matters most",
    ]
    if runtime_class not in {"short", "sequence"}:
        policy.extend([
            "promote approved good outputs into the asset library before continuing a long film",
            "carry last-frame anchors across adjacent shots only when identity/location continuity matters",
        ])
    return policy


def _seedance_execution(runtime_class: str) -> list[str]:
    base = [
        "write prompts as subject + action + setting + camera + lighting + motion + sound intent",
        "keep each Seedance action physically filmable within 4-15 seconds",
        "use reference-to-video for multi-reference shots and i2v for last-frame continuation",
    ]
    if runtime_class in {"short", "sequence"}:
        return [*base, "single-call multi-shot is allowed only when the whole request fits inside 15 seconds"]
    return [
        *base,
        "render scene/chunk/shot graph instead of one long prompt",
        "QA every rendered shot before assembly and retry only the failed unit",
    ]


def _qa_risks(niche: str, runtime_class: str, niche_playbook: dict[str, Any]) -> list[str]:
    risks = [
        "identity drift",
        "product or logo drift",
        "duration mismatch",
        "fake text or caption artifacts",
        "audio missing when dialogue/SFX is expected",
        *[str(x) for x in (niche_playbook.get("safety_rules") or [])[:4]],
    ]
    if niche in {"finance_education", "medical_wellness", "documentary", "kids_family"}:
        risks.append("claims or safety framing require human review before production claim")
    if runtime_class not in {"short", "sequence"}:
        risks.extend(["scene-to-scene location drift", "unmotivated time jump", "assembly pacing collapse"])
    return risks


def _delivery_notes(runtime_class: str, market_playbook: dict[str, Any]) -> list[str]:
    notes = [
        f"caption language: {market_playbook.get('caption_language') or 'inferred'}",
        f"claim style: {market_playbook.get('claim_style') or 'show proof visually'}",
        "final export should include caption, hashtags, QA report, and production graph evidence",
    ]
    if runtime_class not in {"short", "sequence"}:
        notes.append("deliver scene-level progress and failed-shot reasons in Production Inspector")
    return notes


__all__ = ["ProductionTreatment", "build_production_treatment"]
