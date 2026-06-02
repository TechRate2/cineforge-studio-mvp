"""Cinematic grammar contract for autonomous production.

Niche playbooks say what kind of content the video is. This module says how it
should be filmed and edited so the agent behaves more like a director/editor
than a generic prompt expander.
"""
from __future__ import annotations

from typing import Any

from skills.market_playbooks import get_market_playbook
from skills.niche_playbooks import get_niche_playbook


_PROOF_NICHES = {"ugc_review", "ecommerce_catalog", "tech", "app_saas", "finance_education", "education"}
_SENSORY_NICHES = {"asmr", "beauty", "fashion", "food", "restaurant_hospitality", "lifestyle"}
_NARRATIVE_NICHES = {"drama", "anime_comic", "documentary", "kids_family", "music_video"}
_SPATIAL_NICHES = {"automotive", "real_estate", "travel", "fitness"}


def build_cinematic_grammar_contract(
    *,
    niche: str,
    runtime_payload: dict[str, Any],
    target_market: str = "auto",
    creative_treatment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return director/editor grammar for a niche/runtime route."""
    playbook = get_niche_playbook(niche)
    market = get_market_playbook(target_market)
    runtime_class = str(runtime_payload.get("runtime_class") or "short")
    treatment_id = str((creative_treatment or {}).get("treatment_id") or "")
    archetype = _story_archetype(niche=niche, runtime_class=runtime_class, treatment_id=treatment_id)
    shot_palette = _shot_palette(niche=niche, runtime_class=runtime_class, playbook=playbook)
    return {
        "schema_version": "cinejelly.cinematic_grammar.v1",
        "niche": playbook.get("niche") or niche,
        "runtime_class": runtime_class,
        "target_market": market.get("target_market") or target_market,
        "treatment_id": treatment_id or "auto",
        "story_archetype": archetype,
        "shot_palette": shot_palette,
        "transition_logic": _transition_logic(niche=niche, runtime_class=runtime_class),
        "editor_pacing": _editor_pacing(niche=niche, runtime_class=runtime_class),
        "sound_strategy": _sound_strategy(niche=niche, market=market, playbook=playbook),
        "prompt_directives": _prompt_directives(archetype=archetype, shot_palette=shot_palette),
        "anti_patterns": _anti_patterns(niche=niche, runtime_class=runtime_class),
        "qa_questions": _qa_questions(niche=niche, runtime_class=runtime_class),
    }


def _story_archetype(*, niche: str, runtime_class: str, treatment_id: str) -> dict[str, str]:
    if treatment_id == "short_drama_arc" or niche in _NARRATIVE_NICHES:
        base = {
            "name": "conflict_reveal_aftertaste",
            "promise": "an unresolved visual question becomes a reveal and emotional final image",
            "turn": "each scene changes what the viewer believes",
        }
    elif niche in _PROOF_NICHES:
        base = {
            "name": "result_problem_proof",
            "promise": "show the result before explaining the mechanism",
            "turn": "viewer skepticism is answered by visible proof",
        }
    elif niche in _SENSORY_NICHES:
        base = {
            "name": "texture_ritual_payoff",
            "promise": "make the viewer feel texture, atmosphere, or transformation",
            "turn": "process detail resolves into a sensory payoff",
        }
    elif niche in _SPATIAL_NICHES:
        base = {
            "name": "space_identity_motion",
            "promise": "establish place/object identity, then prove motion or spatial value",
            "turn": "wide geography becomes a concrete feature or experience",
        }
    else:
        base = {
            "name": "hook_action_payoff",
            "promise": "one clear visual incident creates curiosity and resolves through action",
            "turn": "each cut reveals new proof, not random decoration",
        }
    if runtime_class in {"short_film", "episode"}:
        base["long_form_rule"] = "repeat the archetype inside each scene, with a stronger unresolved handoff at scene end"
    else:
        base["long_form_rule"] = "keep the archetype compact; no subplot"
    return base


def _shot_palette(*, niche: str, runtime_class: str, playbook: dict[str, Any]) -> list[dict[str, str]]:
    camera = [str(x) for x in (playbook.get("camera") or [])]
    if niche in _PROOF_NICHES:
        roles = [
            ("result_hook", camera[0] if camera else "CU result first"),
            ("problem_context", "MS or POV showing the pain point"),
            ("proof_insert", "ECU/macro proof action"),
            ("reaction_or_result", "CU reaction or before-after result"),
        ]
    elif niche in _SENSORY_NICHES:
        roles = [
            ("sensory_hook", camera[0] if camera else "ECU texture"),
            ("ritual_process", "hands-in-frame process shot"),
            ("material_detail", "macro material or texture insert"),
            ("payoff_close", "slow push-in to final transformation"),
        ]
    elif niche in _SPATIAL_NICHES:
        roles = [
            ("identity_establish", "wide or tracking establishing shot"),
            ("feature_path", "POV/tracking motion through space"),
            ("detail_insert", "CU feature or object proof"),
            ("return_anchor", "wide return shot that preserves geography"),
        ]
    elif niche in _NARRATIVE_NICHES:
        roles = [
            ("emotion_hook", camera[0] if camera else "ECU face or hands"),
            ("object_clue", "CU clue insert"),
            ("relationship_space", "OTS or two-shot showing power relation"),
            ("reveal_aftertaste", "locked-off reveal or slow push-in"),
        ]
    else:
        roles = [
            ("hook", "strong readable opening shot"),
            ("action", "clear physical action shot"),
            ("proof", "detail insert"),
            ("payoff", "memorable final image"),
        ]
    if runtime_class in {"short_film", "episode"}:
        roles.append(("scene_bridge", "last-frame handoff or repeated motif"))
    return [
        {"role": role, "camera": shot, "purpose": _role_purpose(role)}
        for role, shot in roles
    ]


def _role_purpose(role: str) -> str:
    return {
        "result_hook": "stop scroll by showing outcome first",
        "proof_insert": "make the claim visible",
        "sensory_hook": "create tactile curiosity",
        "identity_establish": "lock location/object geography",
        "emotion_hook": "make viewer read character stakes",
        "scene_bridge": "carry continuity into the next scene",
    }.get(role, "advance the beat through visible action")


def _transition_logic(*, niche: str, runtime_class: str) -> list[str]:
    if niche in _SENSORY_NICHES:
        base = ["cut on tactile action", "match motion direction between hand/product shots", "avoid random beauty montage"]
    elif niche in _PROOF_NICHES:
        base = ["cut when proof value changes", "show result before explanation", "avoid text walls as transitions"]
    elif niche in _SPATIAL_NICHES:
        base = ["preserve screen direction", "return to a geography anchor after detail inserts", "avoid impossible room/location jumps"]
    elif niche in _NARRATIVE_NICHES:
        base = ["cut on emotional reversal", "use object inserts as continuity glue", "hold reaction long enough for meaning"]
    else:
        base = ["cut on visible change", "keep transition motivation clear"]
    if runtime_class in {"short_film", "episode"}:
        base.append("end each scene on a handoff image that asks a new question")
    return base


def _editor_pacing(*, niche: str, runtime_class: str) -> dict[str, Any]:
    if runtime_class == "short":
        return {"tempo": "fast", "rule": "front-load hook; remove all non-visual setup", "average_shot_s": "4-8"}
    if runtime_class == "sequence":
        return {"tempo": "tight", "rule": "two-scene contrast with clear payoff", "average_shot_s": "5-10"}
    if runtime_class == "micro_film":
        return {"tempo": "controlled", "rule": "3-act rhythm, each act has a visual turn", "average_shot_s": "6-12"}
    return {"tempo": "scene-driven", "rule": "each scene has setup, turn, and handoff; render as 4-15s units", "average_shot_s": "8-12"}


def _sound_strategy(*, niche: str, market: dict[str, Any], playbook: dict[str, Any]) -> dict[str, str]:
    primary = str(playbook.get("audio") or "natural foley and platform-native music")
    return {
        "primary_texture": primary,
        "dialogue_register": str(market.get("dialogue_style") or "natural concise speech"),
        "caption_rule": "compose captions in post; do not ask video model to draw caption text",
        "sync_rule": "audio/SFX must follow physical action, not cover weak visuals",
    }


def _prompt_directives(*, archetype: dict[str, str], shot_palette: list[dict[str, str]]) -> list[str]:
    roles = ", ".join(item["role"] for item in shot_palette[:5])
    return [
        f"Use story archetype: {archetype['name']}.",
        f"Shot roles to cover: {roles}.",
        "Every shot must have subject, action, setting, camera, sound intent, and continuity anchor.",
        "Prefer visible proof, object clues, or physical transformation over narration.",
    ]


def _anti_patterns(*, niche: str, runtime_class: str) -> list[str]:
    items = [
        "generic cinematic adjectives without physical action",
        "random camera movement that does not reveal new information",
        "text overlays generated inside video frames",
        "multiple unrelated actions inside one 4-15s Seedance unit",
    ]
    if runtime_class in {"short_film", "episode"}:
        items.extend([
            "scene endings without a handoff image",
            "location or wardrobe reset without screenplay reason",
        ])
    if niche in _PROOF_NICHES:
        items.append("claim stated only in dialogue without visual proof")
    if niche in _SENSORY_NICHES:
        items.append("texture/action mismatch with audio")
    return items


def _qa_questions(*, niche: str, runtime_class: str) -> list[str]:
    questions = [
        "Can a viewer understand the first shot with sound off?",
        "Does each shot show one filmable action?",
        "Does every cut reveal new proof, emotion, space, or texture?",
        "Are identity, product geometry, lighting, and style stable?",
    ]
    if runtime_class in {"short_film", "episode"}:
        questions.extend([
            "Does each scene change the story state?",
            "Does each scene ending motivate the next scene?",
        ])
    if niche in _PROOF_NICHES:
        questions.append("Is the claim demonstrated visually?")
    if niche in _SENSORY_NICHES:
        questions.append("Do SFX and motion land on the same physical action?")
    return questions


__all__ = ["build_cinematic_grammar_contract"]
