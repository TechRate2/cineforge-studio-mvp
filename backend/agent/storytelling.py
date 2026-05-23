"""STORYTELLING LIBRARY — niche-agnostic structural skeleton for Director Agent.

Synthesized from 7 industry references (ViMax, ArcReel, drama-director-skill,
awesome-seedance-2-prompts, MindStudio film workflow, CrePal product-ads,
AtlasCloud drama). One framework drives beauty / tech / food / fashion / B2B —
LLM only picks HOOK_PATTERN + fills slots from brief, structure stays fixed.

Three primary exports:
    - `HOOK_PATTERNS`: 10 named hook templates with intent + visual cue
    - `beat_sheet_for(duration_s)`: compressed/expanded beat sheet (15s/30s/60s)
    - `validate_plan(plan)`: post-LLM hard validators (product timing, double-contrast)

This module is PURE — no LLM calls, no IO. Used by `director_agent.py` to
inject constraints into the LLM prompt AND to validate plan output before
returning to user.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ============================================================
# A. HOOK PATTERNS — first 1-3s — pick exactly ONE per plan
# ============================================================

@dataclass(frozen=True)
class HookPattern:
    key: str
    label: str
    intent: str
    visual_cue: str
    when_to_use: str
    example_brief: str


HOOK_PATTERNS: dict[str, HookPattern] = {
    "pattern_interrupt": HookPattern(
        key="pattern_interrupt",
        label="Pattern Interrupt",
        intent="Visual anomaly / unexpected scale / motion break — communicates intent instantly without sound",
        visual_cue="Extreme wide aerial → hard cut to extreme close-up, or impossible motion",
        when_to_use="Tech, gaming, lifestyle aesthetic — when you have a striking visual concept",
        example_brief="Tay người khổng lồ cầm điện thoại nhỏ xíu, drone pan ra rồi cut sát màn hình",
    ),
    "direct_question": HookPattern(
        key="direct_question",
        label="Direct Question",
        intent="Speak directly to the pain — viewer answers in head, locked in",
        visual_cue="Character looking into camera, caption text big bold center-screen",
        when_to_use="Beauty / supplement / B2B SaaS — clear pain audience knows",
        example_brief="\"Da khô bong tróc sau make-up?\" — POV nữ Gen Z soi gương sáng",
    ),
    "bold_statement": HookPattern(
        key="bold_statement",
        label="Bold Statement / Status Reveal",
        intent="Provocative claim viewer must verify — curiosity engine",
        visual_cue="Big text overlay on cinematic frame, or first-person reveal",
        when_to_use="Premium product, transformation story, before-after",
        example_brief="\"Son này còn matte sau 8 tiếng nhậu.\" — close-up bàn cụng ly",
    ),
    "lifestyle_cold_open": HookPattern(
        key="lifestyle_cold_open",
        label="Lifestyle Cold-Open",
        intent="Character mid-action, NO setup — drops viewer in flow",
        visual_cue="Already-walking, already-applying — handheld follow, soft natural light",
        when_to_use="UGC organic feel, fashion, food, casual",
        example_brief="Cô gái đang lau son bàn make-up, đèn vàng warm, micro-smile",
    ),
    "pov_confession": HookPattern(
        key="pov_confession",
        label="POV Confession",
        intent="First-person intimate — viewer feels they're being trusted",
        visual_cue="Selfie angle, vertical handheld, micro-tremor, eye-line on camera",
        when_to_use="Beauty review, drama, testimonial, ASMR",
        example_brief="POV nhìn xuống tay run run mở hộp son lần đầu",
    ),
    "social_proof_drop": HookPattern(
        key="social_proof_drop",
        label="Social Proof Drop",
        intent="Number / quote / count — credibility before pitch",
        visual_cue="Number text-overlay punch in 0.5s, then product context",
        when_to_use="Established product, KOL endorsed, scale brand",
        example_brief="\"4.000 reviews 5 sao\" big text → mosaic ảnh khách dùng",
    ),
    "visual_anomaly": HookPattern(
        key="visual_anomaly",
        label="Visual Anomaly",
        intent="Image breaks physics / scale — scroll-stop reflex",
        visual_cue="Liquid frozen mid-air, oversize prop, surreal lighting, vertical floor",
        when_to_use="Tech demos, gaming, food (slow-mo splash)",
        example_brief="Cây cà phê đổ ngược lên ly slow-mo, hạt cà phê bay quanh",
    ),
    "before_after_tease": HookPattern(
        key="before_after_tease",
        label="Before/After Tease",
        intent="Show 'after' state first, withhold cause — curiosity loop",
        visual_cue="Reveal end-state in 1s, hard cut to original problem",
        when_to_use="Skincare, fitness, makeover, home reno",
        example_brief="Da sáng mịn close-up 1s → cut về da khô 1 tuần trước",
    ),
    "reaction_shot": HookPattern(
        key="reaction_shot",
        label="Reaction Shot Cold-Open",
        intent="Silhouette / profile micro-tremor — emotion without face overuse",
        visual_cue="Backlight silhouette, side profile, hand close-up, no full-face",
        when_to_use="Drama, food taste-test, emotional product (perfume, music)",
        example_brief="Silhouette ngả đầu lên gối, ánh đèn từ cửa sổ, hơi thở",
    ),
    "offer_led": HookPattern(
        key="offer_led",
        label="Offer-Led",
        intent="Promo as bait — only when discount is real + scarcity",
        visual_cue="Price slash visual, countdown timer, or ‘ends Sunday’ text",
        when_to_use="Launch week, flash sale, only if real discount — fake offer = trust loss",
        example_brief="\"Tuần ra mắt -30%\" big text → product hero shot 2s",
    ),
}


# ============================================================
# B. BEAT SHEET — duration-aware structural skeleton (slots)
# ============================================================

@dataclass(frozen=True)
class Beat:
    phase: str
    start_s: float
    end_s: float
    intent: str
    shot_count_hint: int


def beat_sheet_for(duration_s: int) -> list[Beat]:
    """Return beat list scaled to total duration. Niche-agnostic.

    15s  → 4 phases compressed (HOOK / SETUP+PAIN merged / REVEAL+PROOF merged / CTA)
    30s  → 5 phases (HOOK / PAIN / TENSION / REVEAL+PROOF / CTA)
    60s  → 6 phases full arc (HOOK / SETUP / PAIN / TENSION / REVEAL / PROOF / CTA)
    """
    if duration_s <= 15:
        return [
            Beat("HOOK", 0.0, 2.0, "Pattern interrupt, no product, no logo", 1),
            Beat("PAIN", 2.0, 5.0, "Show problem viewer recognizes", 1),
            Beat("REVEAL", 5.0, 9.0, "Product appears as the resolution", 1),
            Beat("PROOF", 9.0, 12.5, "Feature demonstrated via action (not text)", 1),
            Beat("CTA", 12.5, float(duration_s), "Explicit verb (Shop / Try / Link)", 1),
        ]
    if duration_s <= 30:
        return [
            Beat("HOOK", 0.0, 2.0, "Pattern interrupt — single hard cut", 1),
            Beat("PAIN", 2.0, 6.0, "Establish character + recognizable problem", 1),
            Beat("TENSION", 6.0, 12.0, "Stakes rise — faster pacing, close-up intercuts", 2),
            Beat("REVEAL", 12.0, 20.0, "Product as answer; slow push-in to land beat", 1),
            Beat("PROOF", 20.0, float(max(duration_s - 3, 21)), "Demo via action, callouts allowed", 2),
            Beat("CTA", float(max(duration_s - 3, 27)), float(duration_s), "Static or push-in, explicit verb", 1),
        ]
    # 60s and longer
    return [
        Beat("HOOK", 0.0, 2.5, "Pattern interrupt, max impact", 1),
        Beat("SETUP", 2.5, 7.0, "World + character introduced", 1),
        Beat("PAIN", 7.0, 14.0, "Problem dramatized with stakes", 2),
        Beat("TENSION", 14.0, 24.0, "Escalation — rising panels, intercuts", 3),
        Beat("REVEAL", 24.0, 36.0, "Product as solution, lighting shift warm", 2),
        Beat("PROOF", 36.0, float(max(duration_s - 5, 50)), "Multi-feature demo, testimonial allowed", 3),
        Beat("CTA", float(max(duration_s - 5, 55)), float(duration_s), "Explicit verb + offer if real", 1),
    ]


# ============================================================
# C. SEEDANCE 2.0 — Three-section prompt schema
# ============================================================

SEEDANCE_PROMPT_TEMPLATE = """\
[STYLE & MOOD]
{style_block}

[DYNAMIC DESCRIPTION]
{dynamic_block}

[STATIC DESCRIPTION]
{static_block}
"""


# ============================================================
# D. NICHE-AGNOSTIC SLOT PATTERN
# ============================================================

NICHE_SLOT_KEYS = [
    "problem_statement",   # what pain audience feels (max 8 words)
    "character_archetype", # who solves it (max 6 words)
    "product_role",        # how product helps (max 8 words)
    "payoff_emotion",      # what viewer feels at REVEAL (1 word)
    "cta_verb",            # imperative verb (Shop / Try / Order / Link)
]


# ============================================================
# E. HARD RULES — auto-validators (run AFTER LLM output)
# ============================================================

@dataclass
class ValidationIssue:
    code: str
    severity: str  # "error" blocks render, "warning" surfaces to user
    message: str
    shot_id: Optional[str] = None


def _product_first_appearance_s(shots: list[dict]) -> Optional[float]:
    """Return start_s of first shot where product appears as subject.

    Heuristic: shot.visual.subject contains "product" word OR
    shot.continuity.product_ids is non-empty AND purpose in {reveal, demo, proof, cta}.
    """
    for s in shots:
        purpose = (s.get("purpose") or "").lower()
        subject = (s.get("visual", {}).get("subject") or "").lower()
        prod_ids = s.get("continuity", {}).get("product_ids") or []
        if prod_ids and (
            "product" in subject
            or purpose in {"reveal", "demo", "proof", "cta"}
        ):
            return float(s.get("start_s", 0.0))
    return None


def _double_contrast_cuts(shots: list[dict]) -> list[ValidationIssue]:
    """Each cut should change BOTH shot size AND camera mode (AtlasCloud rule)."""
    issues: list[ValidationIssue] = []
    prev: Optional[dict] = None
    for s in shots:
        if prev is not None:
            prev_v = prev.get("visual", {})
            cur_v = s.get("visual", {})
            same_size = (prev_v.get("camera_shot") or "").lower() == (cur_v.get("camera_shot") or "").lower()
            same_move = (prev_v.get("camera_movement") or "").lower() == (cur_v.get("camera_movement") or "").lower()
            if same_size and same_move:
                issues.append(ValidationIssue(
                    code="DOUBLE_CONTRAST_VIOLATION",
                    severity="warning",
                    message=f"Shot {s.get('shot_id')}: same camera_shot AND camera_movement as previous — change at least one",
                    shot_id=s.get("shot_id"),
                ))
        prev = s
    return issues


def validate_plan(plan_dict: dict) -> list[ValidationIssue]:
    """Run hard storytelling rules on a DirectorPlan dict.

    Returns list of issues. Caller may surface warnings + block errors.
    Storyboard / refine flows should run this BEFORE spending render credits.
    """
    issues: list[ValidationIssue] = []
    bible = plan_dict.get("continuity_bible") or {}
    shots = plan_dict.get("shot_list") or []
    duration = float(bible.get("duration_s") or 15)

    # Rule 1 — product never opens
    if shots:
        first = shots[0]
        purpose = (first.get("purpose") or "").lower()
        prod_ids = first.get("continuity", {}).get("product_ids") or []
        subject = (first.get("visual", {}).get("subject") or "").lower()
        if prod_ids and ("product" in subject or purpose in {"reveal", "demo", "proof"}):
            issues.append(ValidationIssue(
                code="PRODUCT_OPENS",
                severity="error",
                message="Shot 1 contains product as subject — open with PROBLEM/HOOK, product appears at REVEAL (>=40% runtime)",
                shot_id=first.get("shot_id"),
            ))

    # Rule 2 — product appears at >= 40% runtime
    first_prod_s = _product_first_appearance_s(shots)
    if first_prod_s is not None and duration > 0:
        ratio = first_prod_s / duration
        if ratio < 0.30:  # 30% threshold (slightly lenient than 40%)
            issues.append(ValidationIssue(
                code="PRODUCT_TOO_EARLY",
                severity="warning",
                message=f"Product first appears at {first_prod_s:.1f}s ({ratio*100:.0f}% runtime) — typically REVEAL should land 40%+ into video",
            ))

    # Rule 3 — double-contrast cuts
    issues.extend(_double_contrast_cuts(shots))

    # Rule 4 — total duration matches
    sum_s = sum(float(s.get("duration_s") or 0) for s in shots)
    if abs(sum_s - duration) > 2.0:
        issues.append(ValidationIssue(
            code="DURATION_MISMATCH",
            severity="warning",
            message=f"Shot durations sum to {sum_s:.1f}s, target {duration:.1f}s (tolerance ±2s)",
        ))

    # Rule 5 — beat sheet coverage hint
    beat_phases = {b.phase for b in beat_sheet_for(int(duration))}
    purposes = {(s.get("purpose") or "").upper() for s in shots}
    expected = {"HOOK", "CTA"}  # absolute musts
    missing = expected - purposes - {"REVEAL"}  # REVEAL inferred from product_ids
    if "HOOK" not in purposes and not any("hook" in (s.get("purpose") or "").lower() for s in shots):
        issues.append(ValidationIssue(
            code="MISSING_HOOK",
            severity="error",
            message="No shot has purpose=hook — first beat must be HOOK (pattern interrupt)",
        ))

    # Rule 6 — face anchor consistency
    chars = bible.get("characters") or []
    if chars and not (chars[0].get("face_signature") or "").strip():
        issues.append(ValidationIssue(
            code="WEAK_FACE_ANCHOR",
            severity="warning",
            message="Primary character has empty face_signature — Seedance/Vidu need explicit face DNA to chain shots",
        ))

    return issues


# ============================================================
# F. PROMPT INJECTION HELPERS — build context block for LLM
# ============================================================

def hook_patterns_block() -> str:
    """Compact enum block for LLM prompt — Director picks ONE pattern."""
    lines = ["HOOK_PATTERN enum (pick exactly ONE for shot 1):"]
    for hp in HOOK_PATTERNS.values():
        lines.append(f"- {hp.key}: {hp.intent} | Visual: {hp.visual_cue} | Use when: {hp.when_to_use}")
    return "\n".join(lines)


def beat_sheet_block(duration_s: int) -> str:
    """Compact beat-sheet for LLM prompt — Director fills slots, doesn't pick structure."""
    beats = beat_sheet_for(duration_s)
    lines = [f"BEAT SHEET (duration={duration_s}s, fill but don't restructure):"]
    for b in beats:
        lines.append(
            f"- {b.phase} [{b.start_s:g}-{b.end_s:g}s] — {b.intent} (~{b.shot_count_hint} shot)"
        )
    return "\n".join(lines)


def hard_rules_block() -> str:
    """Pinned negative constraints — embedded in director.md as RULES."""
    return """\
HARD RULES (auto-validated, violation = re-plan):
- Shot 1 MUST NOT contain product as subject — open with HOOK pattern.
- Product first appears at REVEAL phase (>=30% into runtime).
- Each cut changes AT LEAST one of {camera_shot, camera_movement} from previous shot (double-contrast).
- Sum of shot durations must match target_duration_s (±2s tolerance).
- Primary character MUST have non-empty face_signature (visual DNA lock).
- CTA shot must contain explicit imperative verb (Shop / Try / Order / Link in bio / Click).
- No age indicators in character description — use functional descriptors ("photorealistic figure").
- Complex camera motion only on wide/medium shots; close-ups stay static or simple push-in."""


def niche_slot_block() -> str:
    """Slot pattern reminder — Director fills these from brief, no niche template."""
    return f"""\
NICHE-AGNOSTIC SLOTS (extract from user_brief, fill into bible.intent + shot.purpose):
{chr(10).join(f"- {k}" for k in NICHE_SLOT_KEYS)}
This is a SLOT PATTERN, NOT a template. Same skeleton works for beauty, tech, food,
fashion, B2B SaaS, fitness, music, gaming, education — only slot values change."""
