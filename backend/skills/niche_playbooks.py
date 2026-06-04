"""Niche playbooks for CineJelly Autonomous Director.

These are deterministic creative guardrails used after AutoPlanner selects a
niche. They keep the agent from treating beauty, food, drama, education, and
product videos as the same generic short.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


_COMMON = {
    "seedance_notes": [
        "Use concrete subject-action-setting-camera wording, not abstract adjectives.",
        "Keep each action physically filmable inside one 4-15s Seedance shot.",
        "Use reference images for identity/product/style, video refs for camera/motion, audio refs for beat/SFX pacing.",
    ],
    "avoid": [
        "generic people doing generic actions",
        "text-only scenes",
        "unmotivated camera movement",
        "CTA or logo in the first 3 seconds unless user explicitly asks",
    ],
}


_PLAYBOOKS: dict[str, dict[str, Any]] = {
    "beauty": {
        "best_for": "skincare, makeup, haircare, fragrance, before-after transformation",
        "hook_moves": ["macro texture surprise", "mirror reveal", "before-after split action"],
        "beat_flow": ["hook", "problem texture", "application ritual", "visible transformation", "confidence close"],
        "camera": ["ECU macro", "mirror OTS", "slow push-in", "soft handheld close-up"],
        "audio": "soft ASMR taps, gentle swipe sounds, low-volume elegant beat",
        "quality_bar": ["skin texture believable", "product packaging stable", "no face morphing", "no impossible before-after jump"],
    },
    "food": {
        "best_for": "street food, recipe, restaurant teaser, mukbang, product food demo",
        "hook_moves": ["sizzle close-up", "knife cut reveal", "steam pull-back", "sauce pour"],
        "beat_flow": ["sensory hook", "ingredient/process", "texture payoff", "first bite", "craving CTA"],
        "camera": ["top-down process", "macro texture", "slow-motion pour", "handheld street POV"],
        "audio": "sizzle, crunch, pour, chop, warm street ambience",
        "quality_bar": ["food physics credible", "no rubber texture", "hands consistent", "steam/sauce direction plausible"],
    },
    "tech": {
        "best_for": "gadgets, apps, AI tools, SaaS feature demos, comparisons",
        "hook_moves": ["unexpected result first", "screen-to-real transition", "problem stopwatch"],
        "beat_flow": ["result hook", "pain point", "feature action", "proof/comparison", "use-case close"],
        "camera": ["clean desk overhead", "screen insert", "product orbit", "snap zoom on result"],
        "audio": "clean digital clicks, UI ticks, concise beat accents",
        "quality_bar": ["UI readable but not over-texted", "device/product stable", "feature shown through action"],
    },
    "lifestyle": {
        "best_for": "daily routine, home, travel, wellness, personal brand, aspirational moments",
        "hook_moves": ["micro-moment interruption", "POV reveal", "calm contrast before/after"],
        "beat_flow": ["emotional hook", "context", "ritual/action", "payoff", "warm closing beat"],
        "camera": ["POV handheld", "window-light close-up", "wide establishing", "slow push-in"],
        "audio": "ambient room tone, soft music, natural foley",
        "quality_bar": ["mood coherent", "setting continuity", "no random object drift"],
    },
    "drama": {
        "best_for": "short drama, relationship tension, plot twist, mini narrative",
        "hook_moves": ["emotion close-up", "object clue", "doorway reveal", "silent confrontation"],
        "beat_flow": ["hook incident", "setup stakes", "tension escalation", "reveal/twist", "emotional aftermath"],
        "camera": ["ECU eyes/hands", "OTS confrontation", "slow dolly-in", "locked-off reveal"],
        "audio": "low tension bed, breath, door/phone/object SFX, sparse dialogue",
        "quality_bar": ["same character wardrobe/face", "clear spatial continuity", "motivated cuts", "no melodrama without visual evidence"],
    },
    "ugc_review": {
        "best_for": "TikTok shop review, testimonial, creator POV, product reaction",
        "hook_moves": ["honest claim test", "unexpected flaw/fix", "result shown before explanation"],
        "beat_flow": ["result hook", "why viewer cares", "test in hand", "proof result", "soft recommendation"],
        "camera": ["selfie POV", "desk handheld", "macro product proof", "quick reaction close-up"],
        "audio": "natural room voice, small foley, creator-style beat",
        "quality_bar": ["authentic handheld imperfections", "product visible", "claim demonstrated not narrated only"],
    },
    "fashion": {
        "best_for": "outfit transition, accessories, lookbook, styling tips, brand campaign",
        "hook_moves": ["outfit snap transition", "fabric macro", "walk-in reveal"],
        "beat_flow": ["style hook", "base look", "detail close-ups", "movement fit check", "hero pose"],
        "camera": ["full-body vertical", "low-angle walk", "fabric ECU", "mirror pan"],
        "audio": "beat-synced cuts, fabric rustle, confident rhythm",
        "quality_bar": ["outfit consistency", "body proportions stable", "fabric texture credible"],
    },
    "automotive": {
        "best_for": "car showcase, dealership ad, modification, road POV, feature demo",
        "hook_moves": ["headlight ignition", "engine detail", "rolling reveal", "interior tech close-up"],
        "beat_flow": ["power hook", "exterior identity", "feature detail", "motion proof", "beauty close"],
        "camera": ["low tracking shot", "wheel macro", "interior POV", "drone/wide reveal"],
        "audio": "engine purr, door thump, road ambience, cinematic hits",
        "quality_bar": ["car geometry stable", "logo/plate not hallucinated", "motion direction coherent"],
    },
    "fitness": {
        "best_for": "workout, transformation, supplement, gym routine, coaching tips",
        "hook_moves": ["rep failure moment", "timer challenge", "before-after posture"],
        "beat_flow": ["challenge hook", "form setup", "workout action", "micro win", "motivating close"],
        "camera": ["wide form check", "low-angle strength shot", "sweat/detail close-up", "timer insert"],
        "audio": "impact beat, breath, gym ambience, controlled SFX",
        "quality_bar": ["anatomy plausible", "exercise form safe", "no impossible joint motion"],
    },
    "education": {
        "best_for": "explainer, tutorial, how-to, myth-busting, learning hook",
        "hook_moves": ["myth contradiction", "visual analogy", "mistake demo first"],
        "beat_flow": ["question hook", "wrong assumption", "visual explanation", "example", "memory anchor"],
        "camera": ["clean board/desk", "object demonstration", "split visual analogy", "close-up on key step"],
        "audio": "clear VO rhythm, subtle UI/marker sounds, calm beat",
        "quality_bar": ["one concept per shot", "visual proof over text", "no cluttered diagrams"],
    },
    "asmr": {
        "best_for": "satisfying product, cleaning, cooking, texture, packaging, craft",
        "hook_moves": ["texture crush", "peel/pull reveal", "liquid/foam macro"],
        "beat_flow": ["sensory hook", "repeatable texture action", "variation", "payoff reveal", "calm close"],
        "camera": ["locked macro", "top-down hands", "slow push", "high-detail texture close-up"],
        "audio": "native ASMR foley, no loud music, crisp tactile sounds",
        "quality_bar": ["sound/action sync", "stable hands", "texture continuity"],
    },
    "documentary": {
        "best_for": "mini documentary, founder story, social issue, nature/history explainer",
        "hook_moves": ["cold-open consequence", "rare archive-style visual", "one human detail before context"],
        "beat_flow": ["cold open", "context", "evidence", "human moment", "meaningful takeaway"],
        "camera": ["observational handheld", "wide establishing", "detail insert", "slow interview push-in"],
        "audio": "natural ambience, restrained documentary bed, sparse VO, location foley",
        "quality_bar": ["facts visually supported", "no fake news framing", "clear time/place context", "avoid overdramatic reenactment"],
        "safety_rules": ["Do not present invented facts as real reporting.", "Use cautious documentary language when exact sources are not provided."],
    },
    "real_estate": {
        "best_for": "property tour, rental listing, hotel room, commercial space, neighborhood teaser",
        "hook_moves": ["door-open reveal", "view reveal", "space-saving surprise", "before-after room transition"],
        "beat_flow": ["hero entrance", "layout flow", "key feature", "lifestyle use", "location/value close"],
        "camera": ["wide stabilized walkthrough", "corner-to-corner pan", "window view push", "detail close-up"],
        "audio": "clean room tone, subtle upscale music, door/footstep foley",
        "quality_bar": ["spatial layout consistent", "no impossible room geometry", "windows/doors stable", "avoid misleading size cues"],
    },
    "ecommerce_catalog": {
        "best_for": "SKU showcase, marketplace listing video, product bundle, feature carousel",
        "hook_moves": ["product-in-use proof", "macro feature reveal", "packaging-to-result transition"],
        "beat_flow": ["hero product", "feature 1", "feature 2", "use case", "clean CTA"],
        "camera": ["locked product turntable", "macro material detail", "hands-in-use demo", "flat lay comparison"],
        "audio": "clean product clicks, light commercial beat, subtle packaging foley",
        "quality_bar": ["product shape/logo stable", "no unsupported claims", "one SKU per shot unless comparison", "packaging readable but not text-heavy"],
    },
    "music_video": {
        "best_for": "artist teaser, lyric mood piece, dance visual, fashion/music montage",
        "hook_moves": ["beat-hit visual cut", "silhouette reveal", "signature move first", "light flash transition"],
        "beat_flow": ["beat hook", "motif repeat", "performance/action", "visual escalation", "final signature image"],
        "camera": ["beat-synced handheld", "orbit move", "low-angle performance", "stylized close-up"],
        "audio": "provided track or beat reference drives edit rhythm; avoid random SFX over music",
        "quality_bar": ["movement on beat", "consistent artist styling", "no off-rhythm cuts", "avoid lyric text clutter"],
    },
    "anime_comic": {
        "best_for": "anime trailer, comic adaptation, stylized character scene, manga panel motion",
        "hook_moves": ["impact frame", "eye close-up reveal", "panel-to-motion transition", "power/object clue"],
        "beat_flow": ["impact hook", "character intent", "conflict beat", "stylized action", "emotional freeze-frame"],
        "camera": ["manga panel composition", "dynamic push-in", "speed-line style motion", "dramatic low angle"],
        "audio": "stylized hit, whoosh, room tone, concise dialogue or inner monologue",
        "quality_bar": ["style consistency", "character design stable", "no mixed photoreal/anime drift", "action readable"],
    },
    "app_saas": {
        "best_for": "app demo, SaaS feature launch, workflow automation, AI tool explainer",
        "hook_moves": ["result dashboard first", "manual-vs-automated contrast", "time-saved stopwatch"],
        "beat_flow": ["result hook", "pain point", "workflow action", "proof metric", "next-step CTA"],
        "camera": ["screen insert", "desk POV", "UI-to-real transition", "clean cursor/gesture close-up"],
        "audio": "clean UI ticks, subtle digital beat, concise VO",
        "quality_bar": ["UI state legible", "feature shown through action", "no unreadable text wall", "claim tied to visual proof"],
    },
    "restaurant_hospitality": {
        "best_for": "restaurant promo, cafe atmosphere, hotel/resort teaser, service experience",
        "hook_moves": ["signature dish reveal", "doorway ambience reveal", "guest reaction", "table detail close-up"],
        "beat_flow": ["sensory hook", "space atmosphere", "service/action", "hero experience", "booking/visit close"],
        "camera": ["warm handheld walkthrough", "dish macro", "table-level push", "wide ambience reveal"],
        "audio": "warm room ambience, plate/coffee/service foley, tasteful music bed",
        "quality_bar": ["food/place identity stable", "no empty generic venue", "lighting consistent", "avoid fake crowd clutter"],
    },
    "travel": {
        "best_for": "destination teaser, itinerary, hotel + local experience, creator travel POV",
        "hook_moves": ["impossible view first", "POV arrival reveal", "map-to-location transition", "local detail close-up"],
        "beat_flow": ["destination hook", "arrival/context", "experience sequence", "human/local detail", "save/share CTA"],
        "camera": ["POV walk", "wide scenic reveal", "transport window shot", "detail insert"],
        "audio": "location ambience, soft travel beat, footsteps/transport foley",
        "quality_bar": ["geography coherent", "weather/time consistent", "avoid landmark hallucination when exact place matters", "human scale present"],
    },
    "gaming": {
        "best_for": "game trailer, gameplay-style promo, esports hype, game asset reveal",
        "hook_moves": ["boss/action moment first", "rare item reveal", "HUD reaction", "speedrun contrast"],
        "beat_flow": ["action hook", "challenge/stakes", "mechanic proof", "reward/reveal", "hype close"],
        "camera": ["third-person action cam", "UI/HUD insert", "slow-motion impact", "over-shoulder tracking"],
        "audio": "impact hits, controller/UI clicks, energetic beat, game-like ambience",
        "quality_bar": ["readable action", "consistent character/asset design", "avoid fake unreadable HUD text", "physics consistent with game style"],
    },
    "finance_education": {
        "best_for": "personal finance explainer, business concept, investing basics, creator education",
        "hook_moves": ["mistake demo first", "number reveal through object/action", "before-after decision"],
        "beat_flow": ["question hook", "common mistake", "simple visual model", "example", "risk-aware takeaway"],
        "camera": ["desk demonstration", "clean chart insert", "object analogy", "creator close-up"],
        "audio": "calm clear VO, subtle marker/click sounds, low-distraction beat",
        "quality_bar": ["no financial advice guarantee", "risk disclaimer tone", "one concept per shot", "avoid fake numbers as facts"],
        "safety_rules": ["No guaranteed returns or personalized financial advice.", "Frame content as education, not investment instruction."],
    },
    "medical_wellness": {
        "best_for": "wellness education, clinic explainer, habit guidance, product-safe health content",
        "hook_moves": ["myth contradiction", "symptom-to-habit visual", "routine mistake reveal"],
        "beat_flow": ["careful hook", "context", "safe explanation", "visual habit demo", "consult/proof-aware close"],
        "camera": ["clean clinic/desk setup", "hands demo", "calm close-up", "simple visual analogy"],
        "audio": "calm trustworthy VO, soft room tone, minimal SFX",
        "quality_bar": ["no diagnosis claims", "no cure guarantees", "safe anatomy/habit depiction", "avoid fearmongering"],
        "safety_rules": ["No diagnosis, cure, or treatment guarantees.", "Encourage professional consultation for medical concerns."],
    },
    "kids_family": {
        "best_for": "family lifestyle, toy demo, child-safe learning, parent-oriented product",
        "hook_moves": ["joyful reaction", "toy/action surprise", "parent problem solved visually"],
        "beat_flow": ["safe hook", "setup", "play/learning action", "parent proof", "warm close"],
        "camera": ["eye-level family POV", "safe wide shot", "hands/toy close-up", "warm home detail"],
        "audio": "gentle playful music, safe foley, minimal loud sounds",
        "quality_bar": ["child-safe framing", "no unsafe behavior", "no exploitative emotion", "clear parent context"],
        "safety_rules": ["Keep child-safe framing and avoid unsafe challenges.", "Do not use manipulative or exploitative emotional framing."],
    },
}


def get_niche_playbook(niche: str) -> dict[str, Any]:
    """Return a copy-safe playbook for the selected niche."""
    key = (niche or "").strip().lower()
    data = deepcopy(_PLAYBOOKS.get(key) or _PLAYBOOKS["ugc_review"])
    data["niche"] = key if key in _PLAYBOOKS else "ugc_review"
    data["seedance_notes"] = list(_COMMON["seedance_notes"])
    data["avoid"] = [*data.get("avoid", []), *_COMMON["avoid"]]
    return data


def list_niche_keys() -> list[str]:
    """Return supported niche keys for prompts/admin diagnostics."""
    return sorted(_PLAYBOOKS.keys())


__all__ = ["get_niche_playbook", "list_niche_keys"]
