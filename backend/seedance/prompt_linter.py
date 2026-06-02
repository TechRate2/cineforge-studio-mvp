"""Seedance prompt linter with Phase 1b rule integration.

Rules in this module are derived from dexhunter's Seedance reference/prompt
guidance and Lanshu's prompt formula/debugging methodology. The linter remains
deterministic and vendor-free.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict


LintSeverity = Literal["info", "warning", "error"]

_DURATION_RE = re.compile(r"\b(?:duration|thoi luong|time)\s*:\s*(\d{1,3})\s*s\b", re.IGNORECASE)
_SECTION_RE = re.compile(r"^\s*([A-Za-z][A-Za-z _-]{1,32})\s*:\s*(.+?)\s*$", re.MULTILINE)
_AT_REF_RE = re.compile(r"@(Image|Video|Audio|image|video|audio)[ _-]?(\d+)")
_TIMED_SEGMENT_RE = re.compile(r"\b\d{1,2}\s*(?:-|\u2013)\s*\d{1,2}\s*s\b", re.IGNORECASE)
_ACTION_SPLIT_RE = re.compile(r"\b(then|after that|next|before|while|and then|cut to|switch to)\b|->", re.IGNORECASE)
_CAMERA_MOVEMENTS = {
    "static",
    "locked",
    "push",
    "pull",
    "pan",
    "tilt",
    "track",
    "tracking",
    "follow",
    "orbit",
    "revolve",
    "handheld",
    "crane",
    "dolly",
    "whip",
    "zoom",
}
_STATIC_TOKENS = {"static", "locked", "tripod", "fixed"}
_MOTION_TOKENS = {"push", "pull", "pan", "tilt", "track", "tracking", "follow", "orbit", "revolve", "crane", "dolly", "whip", "zoom"}
_GENERIC_SUBJECTS = {"person", "people", "someone", "subject", "character", "product", "object", "scene"}
_ROLE_WORDS = {
    "first frame",
    "last frame",
    "character",
    "subject",
    "scene",
    "background",
    "camera",
    "movement",
    "action",
    "motion",
    "effects",
    "transitions",
    "rhythm",
    "tempo",
    "voice",
    "tone",
    "bgm",
    "music",
    "sound effects",
    "sfx",
    "outfit",
    "clothing",
    "product",
}
_STYLE_WORDS = {
    "cinematic",
    "documentary",
    "photorealistic",
    "anime",
    "cel-shaded",
    "vintage",
    "film",
    "commercial",
    "editorial",
    "ugc",
    "mockumentary",
}


class PromptLintIssue(BaseModel):
    """One prompt lint issue found before Seedance execution."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    message: str
    severity: LintSeverity = "warning"
    field: str | None = None


class PromptLinter:
    """Deterministic linter for Seedance prompt structure and common risks."""

    max_prompt_chars: int

    def __init__(self, *, max_prompt_chars: int = 2200) -> None:
        self.max_prompt_chars = max_prompt_chars

    def lint(self, prompt: str) -> list[PromptLintIssue]:
        """Run all Phase 1b prompt checks."""
        text = str(prompt or "").strip()
        sections = _extract_sections(text)
        issues: list[PromptLintIssue] = []
        issues.extend(self._lint_phase1a_basics(text, sections))
        issues.extend(self.lint_prompt_formula(text))
        issues.extend(self.lint_subject_stability(text))
        issues.extend(self.lint_reference_assignments(text))
        issues.extend(self.lint_camera_conflicts(text))
        issues.extend(self.lint_duration_complexity(text))
        issues.extend(self.lint_negative_constraints(text))
        issues.extend(self.lint_style_continuity(text))
        return _dedupe_issues(issues)

    def lint_prompt_formula(self, prompt: str) -> list[PromptLintIssue]:
        """Check Lanshu 8-element formula completeness."""
        sections = _extract_sections(prompt)
        required = ["subject", "action", "scene", "lighting", "camera", "style", "quality", "constraints"]
        issues: list[PromptLintIssue] = []
        for key in required:
            if not _has_meaningful_value(sections, key):
                issues.append(PromptLintIssue(
                    rule_id=f"lanshu.formula.missing_{key}",
                    field=key,
                    severity="error" if key in {"subject", "action", "camera"} else "warning",
                    message=f"Prompt is missing Lanshu formula element: {key}.",
                ))
        return issues

    def lint_subject_stability(self, prompt: str) -> list[PromptLintIssue]:
        """Check whether subject text has enough stable identifying traits."""
        sections = _extract_sections(prompt)
        subject = sections.get("subject", "")
        if not subject:
            return []
        norm = _norm(subject)
        if norm in _GENERIC_SUBJECTS:
            return [PromptLintIssue(
                rule_id="lanshu.subject.generic_subject",
                field="subject",
                severity="warning",
                message="Subject is too generic to anchor identity or product details.",
            )]
        trait_count = _stable_trait_count(subject)
        if trait_count < 2:
            return [PromptLintIssue(
                rule_id="lanshu.subject.insufficient_stable_traits",
                field="subject",
                severity="warning",
                message="Subject should include at least 2-3 stable identifying traits.",
            )]
        return []

    def lint_reference_assignments(self, prompt: str) -> list[PromptLintIssue]:
        """Check dexhunter @ reference assignment clarity."""
        issues: list[PromptLintIssue] = []
        for match in _AT_REF_RE.finditer(prompt):
            ref = match.group(0)
            window = prompt[max(0, match.start() - 80): min(len(prompt), match.end() + 120)].lower()
            if not any(role_word in window for role_word in _ROLE_WORDS):
                issues.append(PromptLintIssue(
                    rule_id="dexhunter.reference.vague_assignment",
                    field="references",
                    severity="warning",
                    message=f"{ref} is mentioned without a clear role assignment.",
                ))
        return issues

    def lint_camera_conflicts(self, prompt: str) -> list[PromptLintIssue]:
        """Detect static-vs-moving camera conflicts and overloaded movement."""
        sections = _extract_sections(prompt)
        camera = _norm(sections.get("camera", ""))
        if not camera:
            return []
        tokens = {token for token in _CAMERA_MOVEMENTS if token in camera}
        issues: list[PromptLintIssue] = []
        if tokens & _STATIC_TOKENS and tokens & _MOTION_TOKENS:
            issues.append(PromptLintIssue(
                rule_id="dexhunter.camera.static_motion_conflict",
                field="camera",
                severity="warning",
                message="Camera asks for static/locked framing and movement in the same unit.",
            ))
        moving_tokens = sorted(tokens & _MOTION_TOKENS)
        if len(moving_tokens) > 2:
            issues.append(PromptLintIssue(
                rule_id="lanshu.camera.too_many_movements",
                field="camera",
                severity="warning",
                message="Use one primary camera movement per Seedance shot.",
            ))
        return issues

    def lint_duration_complexity(self, prompt: str) -> list[PromptLintIssue]:
        """Check whether prompt complexity matches selected duration."""
        duration_s = _extract_duration_s(prompt, _extract_sections(prompt))
        if duration_s is None:
            return []
        segment_count = len(_TIMED_SEGMENT_RE.findall(prompt))
        transition_count = len(_ACTION_SPLIT_RE.findall(prompt))
        if duration_s <= 5 and (segment_count > 1 or transition_count > 2):
            return [PromptLintIssue(
                rule_id="dexhunter.duration.too_complex_for_short_unit",
                field="duration",
                severity="warning",
                message="Prompt packs too many scenes/actions into a 4-5 second unit.",
            )]
        if duration_s >= 10 and segment_count == 0:
            return [PromptLintIssue(
                rule_id="dexhunter.duration.long_prompt_without_segments",
                field="duration",
                severity="info",
                message="Videos 10s or longer should consider time-segmented prompting.",
            )]
        return []

    def lint_negative_constraints(self, prompt: str) -> list[PromptLintIssue]:
        """Check standard no-text/logo/watermark and clone/twin constraints."""
        text = _norm(prompt)
        issues: list[PromptLintIssue] = []
        missing: list[str] = []
        if "subtitle" not in text and "text overlay" not in text and "no text" not in text:
            missing.append("no subtitles/text overlays")
        if "logo" not in text:
            missing.append("no logo")
        if "watermark" not in text:
            missing.append("no watermark")
        if missing:
            issues.append(PromptLintIssue(
                rule_id="lanshu.constraints.missing_negative_constraints",
                field="constraints",
                severity="warning",
                message="Prompt is missing negative constraints: " + ", ".join(missing) + ".",
            ))
        sections = _extract_sections(prompt)
        identity_text = _norm(" ".join([
            sections.get("subject", ""),
            sections.get("action", ""),
            sections.get("scene", ""),
        ]))
        references_people = "@image" in text or any(
            word in identity_text
            for word in ["character", "person", "people", "face", "woman", "man", "actor", "model"]
        )
        if references_people and not any(word in text for word in ["clone", "twin", "duplicate identity", "no duplicate"]):
            issues.append(PromptLintIssue(
                rule_id="lanshu.constraints.clone_twin_risk",
                field="constraints",
                severity="info",
                message="Character prompts should explicitly block clones/twins when identity matters.",
            ))
        return issues

    def lint_style_continuity(self, prompt: str) -> list[PromptLintIssue]:
        """Check style drift and weak character/product lock cues."""
        text = _norm(prompt)
        sections = _extract_sections(prompt)
        issues: list[PromptLintIssue] = []
        style = _norm(sections.get("style", "") + " " + sections.get("style mood", ""))
        if style and not any(word in style for word in _STYLE_WORDS):
            issues.append(PromptLintIssue(
                rule_id="lanshu.style.weak_style_anchor",
                field="style",
                severity="info",
                message="Style section is present but lacks a recognizable visual style anchor.",
            ))
        mentions_character_ref = "@image" in text and any(word in text for word in ["character", "face", "person"])
        if mentions_character_ref and not any(word in text for word in ["preserve", "consistent", "identity", "same face"]):
            issues.append(PromptLintIssue(
                rule_id="lanshu.continuity.weak_character_lock",
                field="constraints",
                severity="warning",
                message="Character reference is present but character consistency is weakly specified.",
            ))
        mentions_product = "@image" in text and any(word in text for word in ["product", "packaging", "bottle", "label"])
        if mentions_product and not any(word in text for word in ["preserve product", "geometry", "packaging", "label"]):
            issues.append(PromptLintIssue(
                rule_id="lanshu.continuity.weak_product_lock",
                field="constraints",
                severity="info",
                message="Product prompt should preserve geometry, packaging, color, and labels.",
            ))
        if "anime" in text and any(word in text for word in ["photorealistic character", "realistic face", "live action character"]):
            issues.append(PromptLintIssue(
                rule_id="lanshu.style.style_drift_conflict",
                field="style",
                severity="warning",
                message="Prompt mixes anime and realistic character style cues that may drift.",
            ))
        return issues

    def _lint_phase1a_basics(self, text: str, sections: dict[str, str]) -> list[PromptLintIssue]:
        issues: list[PromptLintIssue] = []
        if not _has_meaningful_value(sections, "subject"):
            issues.append(PromptLintIssue(
                rule_id="seedance.basic.missing_subject",
                field="subject",
                severity="error",
                message="Prompt is missing a clear Subject field.",
            ))
        if not _has_meaningful_value(sections, "action"):
            issues.append(PromptLintIssue(
                rule_id="seedance.basic.missing_action",
                field="action",
                severity="error",
                message="Prompt is missing a clear Action field.",
            ))
        if not _has_meaningful_value(sections, "camera"):
            issues.append(PromptLintIssue(
                rule_id="seedance.basic.missing_camera",
                field="camera",
                severity="error",
                message="Prompt is missing a clear Camera field.",
            ))
        duration_s = _extract_duration_s(text, sections)
        if duration_s is not None and not 4 <= duration_s <= 15:
            issues.append(PromptLintIssue(
                rule_id="seedance.basic.duration_out_of_range",
                field="duration",
                severity="error",
                message="Seedance prompt duration must be between 4 and 15 seconds.",
            ))
        if len(text) > self.max_prompt_chars:
            issues.append(PromptLintIssue(
                rule_id="seedance.basic.prompt_too_long",
                field="prompt",
                severity="warning",
                message=f"Prompt is too long for configured baseline ({len(text)} chars).",
            ))
        return issues


def _extract_sections(prompt: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for match in _SECTION_RE.finditer(prompt):
        key = " ".join(match.group(1).strip().lower().replace("-", " ").split())
        value = match.group(2).strip()
        sections[key] = value
    return sections


def _has_meaningful_value(sections: dict[str, str], key: str) -> bool:
    value = sections.get(key, "").strip()
    return bool(value and value.lower() not in {"none", "n/a", "unknown", "auto"})


def _extract_duration_s(prompt: str, sections: dict[str, str]) -> int | None:
    section_value = sections.get("duration") or sections.get("timing")
    if section_value:
        match = re.search(r"\b(\d{1,3})\s*s\b", section_value, re.IGNORECASE)
        if match:
            return int(match.group(1))
    match = _DURATION_RE.search(prompt)
    if match:
        return int(match.group(1))
    return None


def _stable_trait_count(subject: str) -> int:
    text = _norm(subject)
    tokens = [token for token in re.findall(r"[a-zA-Z0-9]+", text) if len(token) > 2]
    trait_words = {
        "glass",
        "bottle",
        "perfume",
        "black",
        "white",
        "red",
        "blue",
        "gold",
        "silver",
        "long",
        "short",
        "hair",
        "jacket",
        "dress",
        "logo",
        "packaging",
        "asian",
        "woman",
        "man",
        "child",
        "wooden",
        "metal",
        "linen",
        "ceramic",
    }
    count = sum(1 for token in tokens if token in trait_words)
    if "," in subject:
        count += min(2, subject.count(","))
    return max(count, min(len(tokens), 3) if len(tokens) >= 4 else count)


def _norm(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _dedupe_issues(issues: list[PromptLintIssue]) -> list[PromptLintIssue]:
    seen: set[tuple[str, str | None]] = set()
    out: list[PromptLintIssue] = []
    for issue in issues:
        key = (issue.rule_id, issue.field)
        if key in seen:
            continue
        seen.add(key)
        out.append(issue)
    return out


__all__ = ["LintSeverity", "PromptLintIssue", "PromptLinter"]
