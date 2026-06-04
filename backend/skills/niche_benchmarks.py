"""Canonical benchmark cases for CineJelly niche coverage.

These cases are not unit tests for vendor output. They are production smoke
prompts: each supported niche gets a representative idea, target market,
duration, reference strategy, and acceptance criteria. Use them for regression
runs when changing planner/storyboard/director prompts or model routing.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .niche_playbooks import list_niche_keys


_CASES: dict[str, dict[str, Any]] = {
    "anime_comic": {
        "idea": "A stylized anime trailer where a young courier discovers a glowing letter that changes the city lights.",
        "target_market": "global",
        "duration_hint_s": 45,
        "reference_strategy": ["character sheet image", "style frame image", "music/impact audio"],
        "success_criteria": ["style remains consistent", "character design does not drift", "action is readable"],
    },
    "app_saas": {
        "idea": "A founder shows how an AI inbox app turns 200 customer messages into a prioritized action plan.",
        "target_market": "us",
        "duration_hint_s": 30,
        "reference_strategy": ["product UI screenshot", "creator desk reference"],
        "success_criteria": ["feature is shown through action", "UI is not text clutter", "benefit is proven visually"],
    },
    "asmr": {
        "idea": "A satisfying macro video of luxury packaging being peeled, tapped, and opened on a clean desk.",
        "target_market": "global",
        "duration_hint_s": 20,
        "reference_strategy": ["product image", "audio texture reference"],
        "success_criteria": ["sound/action sync", "hands stable", "texture continuity"],
    },
    "automotive": {
        "idea": "A night teaser for an electric SUV: headlight ignition, wheel close-up, silent city drive, interior tech reveal.",
        "target_market": "global",
        "duration_hint_s": 45,
        "reference_strategy": ["vehicle reference image", "rolling camera video reference"],
        "success_criteria": ["car geometry stable", "motion direction coherent", "interior/exterior identity consistent"],
    },
    "beauty": {
        "idea": "A Vietnamese creator tests a premium lipstick in a Saigon cafe with macro texture and mirror reveal.",
        "target_market": "vn",
        "duration_hint_s": 30,
        "reference_strategy": ["creator image", "product image", "soft ASMR audio"],
        "success_criteria": ["skin texture believable", "product packaging stable", "no face morphing"],
    },
    "documentary": {
        "idea": "A mini documentary about a family coffee shop surviving after 20 years through one morning routine.",
        "target_market": "vn",
        "duration_hint_s": 180,
        "reference_strategy": ["location images", "ambient audio", "owner portrait"],
        "success_criteria": ["time/place context clear", "facts visually supported", "tone not overdramatic"],
    },
    "drama": {
        "idea": "A short film where a woman finds an old voice message before leaving the apartment for the last time.",
        "target_market": "global",
        "duration_hint_s": 300,
        "reference_strategy": ["main character image", "apartment image", "voice/audio reference"],
        "success_criteria": ["emotion arc clear", "wardrobe/face stable", "spatial continuity preserved"],
    },
    "ecommerce_catalog": {
        "idea": "A clean marketplace video for a travel backpack showing compartments, laptop fit, zipper quality, and carry comfort.",
        "target_market": "sea",
        "duration_hint_s": 30,
        "reference_strategy": ["product hero image", "detail images"],
        "success_criteria": ["SKU shape stable", "one feature per shot", "claims demonstrated not narrated only"],
    },
    "education": {
        "idea": "Explain why people forget new words using a visual memory-box analogy and one practical study method.",
        "target_market": "global",
        "duration_hint_s": 60,
        "reference_strategy": ["desk setup image", "simple prop images"],
        "success_criteria": ["one concept per shot", "visual analogy clear", "no cluttered diagrams"],
    },
    "fashion": {
        "idea": "A creator turns one black dress into three looks: office, dinner, and weekend street style.",
        "target_market": "kr",
        "duration_hint_s": 30,
        "reference_strategy": ["outfit reference", "beat audio reference"],
        "success_criteria": ["outfit consistency", "body proportions stable", "beat-synced cuts"],
    },
    "finance_education": {
        "idea": "A simple visual explainer showing why emergency funds matter before investing, using jars and monthly bills.",
        "target_market": "us",
        "duration_hint_s": 60,
        "reference_strategy": ["desk/prop image"],
        "success_criteria": ["no guaranteed financial outcome", "risk-aware takeaway", "numbers not presented as universal facts"],
    },
    "fitness": {
        "idea": "A coach shows the difference between unsafe and safe squat form in a small gym, ending with a posture win.",
        "target_market": "global",
        "duration_hint_s": 30,
        "reference_strategy": ["coach image", "gym image"],
        "success_criteria": ["anatomy plausible", "exercise form safe", "movement readable"],
    },
    "food": {
        "idea": "A street food vendor makes crispy banh mi from bread crackle to sauce pour to first bite reaction.",
        "target_market": "vn",
        "duration_hint_s": 30,
        "reference_strategy": ["food/product image", "sizzle/crunch audio"],
        "success_criteria": ["food physics credible", "hands consistent", "craving payoff clear"],
    },
    "gaming": {
        "idea": "A game trailer moment where a player dodges a boss attack, unlocks a rare weapon, and escapes at one HP.",
        "target_market": "global",
        "duration_hint_s": 30,
        "reference_strategy": ["character/game art reference", "impact audio"],
        "success_criteria": ["action readable", "asset design stable", "HUD not fake text clutter"],
    },
    "kids_family": {
        "idea": "A parent shows a safe educational toy helping a child learn colors through a warm playtime scene.",
        "target_market": "global",
        "duration_hint_s": 30,
        "reference_strategy": ["toy image", "home setting image"],
        "success_criteria": ["child-safe framing", "no unsafe behavior", "parent context clear"],
    },
    "lifestyle": {
        "idea": "A calm Sunday reset routine from messy desk to clean room, tea, journal, and warm sunset close.",
        "target_market": "global",
        "duration_hint_s": 30,
        "reference_strategy": ["room image", "mood/style image"],
        "success_criteria": ["mood coherent", "setting continuity", "no random object drift"],
    },
    "medical_wellness": {
        "idea": "A wellness educator explains a gentle night routine that may support better sleep without making cure claims.",
        "target_market": "global",
        "duration_hint_s": 45,
        "reference_strategy": ["calm bedroom/desk image"],
        "success_criteria": ["no diagnosis/cure claims", "safe habit depiction", "calm trustworthy tone"],
    },
    "music_video": {
        "idea": "A 30-second music visual where a dancer moves through neon reflections, with cuts locked to the beat.",
        "target_market": "global",
        "duration_hint_s": 30,
        "reference_strategy": ["artist/dancer image", "beat audio reference"],
        "success_criteria": ["movement on beat", "artist styling consistent", "no lyric text clutter"],
    },
    "real_estate": {
        "idea": "A vertical apartment tour opening on the balcony view, then showing living room flow, kitchen, bedroom, and evening lights.",
        "target_market": "sea",
        "duration_hint_s": 45,
        "reference_strategy": ["property photos", "walkthrough video reference"],
        "success_criteria": ["layout coherent", "room geometry plausible", "feature order feels like a real tour"],
    },
    "restaurant_hospitality": {
        "idea": "A cafe promo showing the door opening, espresso pull, signature dessert, friendly service, and evening table vibe.",
        "target_market": "vn",
        "duration_hint_s": 30,
        "reference_strategy": ["venue image", "dish/drink image", "room ambience audio"],
        "success_criteria": ["venue identity stable", "food/place not generic", "service beat visible"],
    },
    "tech": {
        "idea": "A desk creator demonstrates a tiny AI camera gadget identifying objects and saving a searchable clip.",
        "target_market": "us",
        "duration_hint_s": 30,
        "reference_strategy": ["device image", "desk setup image"],
        "success_criteria": ["device stable", "feature shown through action", "result appears before explanation"],
    },
    "travel": {
        "idea": "A creator lands in Da Nang, reveals the beach at sunrise, local breakfast, scooter POV, and a save-this-route ending.",
        "target_market": "vn",
        "duration_hint_s": 60,
        "reference_strategy": ["destination images", "location ambience audio"],
        "success_criteria": ["geography coherent", "weather/time consistent", "human scale present"],
    },
    "ugc_review": {
        "idea": "A creator honestly tests a budget portable blender with ice, fruit, cleaning, and final texture proof.",
        "target_market": "vn",
        "duration_hint_s": 30,
        "reference_strategy": ["creator image", "product image", "room audio"],
        "success_criteria": ["authentic handheld feel", "product visible", "claim demonstrated"],
    },
}


def list_benchmark_cases() -> list[dict[str, Any]]:
    """Return copy-safe cases sorted by niche key."""
    return [
        {"niche": niche, **deepcopy(_CASES[niche])}
        for niche in sorted(_CASES.keys())
    ]


def get_benchmark_case(niche: str) -> dict[str, Any]:
    """Return one benchmark case; falls back to ugc_review."""
    key = (niche or "").strip().lower()
    resolved = key if key in _CASES else "ugc_review"
    return {"niche": resolved, **deepcopy(_CASES[resolved])}


def validate_benchmark_coverage() -> dict[str, Any]:
    """Check benchmark cases cover every supported niche playbook."""
    supported = set(list_niche_keys())
    cases = set(_CASES.keys())
    return {
        "supported_count": len(supported),
        "case_count": len(cases),
        "missing": sorted(supported - cases),
        "extra": sorted(cases - supported),
        "ok": supported == cases,
    }


__all__ = [
    "list_benchmark_cases",
    "get_benchmark_case",
    "validate_benchmark_coverage",
]
