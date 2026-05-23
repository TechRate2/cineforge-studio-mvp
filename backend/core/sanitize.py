"""Sanitization utilities — BUG-B6 (prompt injection) + BUG-B12 (PII strip).

Áp dụng cho `context_injection` từ user trước khi pass vào LLM prompt.

V3 hardening (CRITICAL C3 fix):
  - Unicode normalize (NFKD + casefold) trước khi match → chặn "ıgnore" bypass
  - Multi-line detect (DOTALL + whitespace-tolerant) — "ignore\\nall\\nprevious"
  - Bổ sung patterns: "act as / pretend you are / roleplay as / simulate"
  - Anti-context-injection: "BEGIN/END SYSTEM PROMPT", "</user>", "<|im_start|>"
"""

import re
import unicodedata
from typing import Any


# ============================================
# BUG-B6 + V3 C3: Prompt injection patterns (HARDENED)
# ============================================
# Các pattern phổ biến hacker dùng để bypass system prompt.
# `re.DOTALL` cho phép `.` match newline → bắt được multi-line injection.
# `\s+` thay vì space cố định → tolerate \n\t giữa keywords.
PROMPT_INJECTION_PATTERNS = [
    # "ignore previous instructions" — tolerate stacked modifiers
    # ("ignore all previous instructions", "ignore the above prompts", …)
    re.compile(
        r"(?i)\b(?:ignore|disregard|forget|skip|bypass)\s+"
        r"(?:(?:the|all|any|previous|prior|above|earlier|all\s+previous)\s+){1,4}"
        r"(?:instruction|prompt|rule|context|message|system)s?",
        re.UNICODE | re.DOTALL,
    ),
    # Role hijack — explicit "system:" / "assistant:" headers
    re.compile(r"(?i)\b(?:system|assistant|user)\s*:\s*", re.UNICODE),
    # "you are now" / "you are an AI that …"
    re.compile(r"(?i)\byou\s+are\s+(?:now|an?|a\s+new)\b", re.UNICODE | re.DOTALL),
    # New role/instruction/directive
    re.compile(r"(?i)\bnew\s+(?:instruction|directive|role|persona|character)s?\b", re.UNICODE),
    # "act as / pretend you are / roleplay as / simulate / impersonate" (V3 C3)
    re.compile(
        r"(?i)\b(?:act|pretend|roleplay|simulate|impersonate|behave)\s+"
        r"(?:as|like)\s+(?:a\s+|an\s+)?"
        r"(?:system|assistant|admin|developer|hacker|lawyer|coder|root)\b",
        re.UNICODE | re.DOTALL,
    ),
    # Override / jailbreak literal mentions
    re.compile(r"(?i)\b(?:jailbreak|override|prompt\s+injection)\b", re.UNICODE),
    # Markdown / XML / instruct-token wrappers — common across LLM vendors
    re.compile(r"```\s*system\b", re.IGNORECASE | re.UNICODE),
    re.compile(r"<\s*system\b", re.IGNORECASE | re.UNICODE),
    re.compile(r"</?\s*(?:user|assistant|system)\s*>", re.IGNORECASE | re.UNICODE),
    re.compile(r"\[INST\]|\[/INST\]", re.UNICODE),                # Llama
    re.compile(r"<\|im_start\|>|<\|im_end\|>", re.UNICODE),       # ChatML
    re.compile(r"<\|begin_of_text\|>|<\|eot_id\|>", re.UNICODE),  # Llama-3
    # Boundary markers some attackers use
    re.compile(r"(?i)\b(?:BEGIN|END)\s+(?:SYSTEM|PROMPT|INSTRUCTION)\b", re.UNICODE),
]


# Homoglyph map — chars that NFKD won't fold but are common bypass tools.
# Source: Unicode confusables (subset covering Turkish, Cyrillic Latin look-alikes).
_HOMOGLYPHS: dict[str, str] = {
    "ı": "i", "İ": "i", "ł": "l", "Ł": "l", "ø": "o", "Ø": "o",
    # Cyrillic look-alikes
    "а": "a", "А": "a", "е": "e", "Е": "e", "о": "o", "О": "o",
    "р": "p", "Р": "p", "с": "c", "С": "c", "х": "x", "Х": "x",
    "і": "i", "І": "i", "у": "y", "У": "y", "к": "k", "К": "k",
}


def _normalize_for_match(text: str) -> str:
    """Unicode-normalize text before regex matching to defeat homoglyph bypasses.

    Steps:
      1. NFKD decomposes characters (handles "ＳＹＳＴＥＭ" full-width → "SYSTEM")
      2. Strip combining marks (accents)
      3. Map remaining homoglyphs (Turkish ı / Cyrillic а / Cyrillic е …) → ASCII
      4. casefold() lowercases aggressively

    Examples now caught:
      - "ıgnore previous" → "ignore previous" → flagged
      - "ＳＹＳＴＥＭ: take over" → "system: take over" → flagged
      - "Іgnore" (Cyrillic І) → "ignore" → flagged
    """
    nfkd = unicodedata.normalize("NFKD", text)
    no_marks = "".join(c for c in nfkd if not unicodedata.combining(c))
    folded = "".join(_HOMOGLYPHS.get(c, c) for c in no_marks)
    return folded.casefold()


def sanitize_prompt_injection(text: str) -> tuple[str, list[str]]:
    """Detect + neutralize prompt injection attempts.

    The detection runs against the Unicode-normalized form to defeat homoglyph /
    full-width bypasses, but the redaction is applied to the ORIGINAL text so
    legitimate-looking user copy is preserved everywhere except where a
    suspicious pattern matched.

    Returns:
        (cleaned_text, list_of_flagged_patterns)
    """
    if not text:
        return text, []

    flagged: list[str] = []
    cleaned = text
    normalized = _normalize_for_match(text)

    for pattern in PROMPT_INJECTION_PATTERNS:
        # Match on normalized form to catch bypasses
        norm_matches = pattern.findall(normalized)
        if not norm_matches:
            continue
        flagged.extend(str(m)[:50] for m in norm_matches)
        # Redact ORIGINAL text using the same pattern — works for non-bypass
        # cases (~99% of attackers don't bother with homoglyphs).
        # For homoglyph-bypassed text the normalized regex won't match the
        # original; fall back to replacing the whole field with [REDACTED]
        # when normalized matches but original doesn't.
        original_matches = pattern.findall(cleaned)
        if original_matches:
            cleaned = pattern.sub("[REDACTED]", cleaned)
        else:
            # Homoglyph bypass detected — nuke the entire string conservatively
            cleaned = "[REDACTED — homoglyph bypass attempt detected]"
            break

    return cleaned, flagged


# ============================================
# BUG-B12: PII strip (Vietnamese context)
# ============================================
# Detect + redact thông tin cá nhân trước khi pass LLM/log.
PII_PATTERNS = {
    "phone_vn": re.compile(
        r"\b(?:\+?84|0)(?:3|5|7|8|9)\d{8}\b"
    ),  # SĐT VN: 0xxx hoặc +84xxx
    "email": re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    ),
    "cccd": re.compile(
        r"\b\d{12}\b"  # CCCD VN 12 số (cả CMND 9 số ko match — safe)
    ),
    "credit_card": re.compile(
        r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"
    ),
    "url_with_token": re.compile(
        r"https?://\S+[?&](?:token|key|secret|password|api_key)=\S+",
        re.IGNORECASE,
    ),
}


def strip_pii(text: str) -> tuple[str, dict[str, int]]:
    """Redact PII patterns. Trả về (cleaned, counts).

    counts = {phone_vn: 2, email: 1, ...}
    """
    if not text:
        return text, {}

    cleaned = text
    counts: dict[str, int] = {}

    for pii_type, pattern in PII_PATTERNS.items():
        matches = pattern.findall(cleaned)
        if matches:
            counts[pii_type] = len(matches)
            cleaned = pattern.sub(f"[{pii_type.upper()}_REDACTED]", cleaned)

    return cleaned, counts


# ============================================
# Combined sanitizer for ContextInjection
# ============================================

def sanitize_context_injection(ctx: dict[str, Any]) -> tuple[dict[str, Any], dict]:
    """Sanitize tất cả text fields trong ContextInjection.

    Returns:
        (cleaned_ctx, report) — report = {flagged_injections: [...], pii_counts: {...}}.
    """
    if not ctx:
        return ctx, {"flagged_injections": [], "pii_counts": {}}

    cleaned: dict[str, Any] = {}
    all_flagged: list[str] = []
    all_pii: dict[str, int] = {}

    text_fields = ("pain_points", "real_reviews", "usps", "forbidden_to_say", "mood_hint")

    for key, value in ctx.items():
        if key in text_fields and isinstance(value, str):
            # Step 1: strip PII (trước)
            clean1, pii = strip_pii(value)
            for k, v in pii.items():
                all_pii[k] = all_pii.get(k, 0) + v

            # Step 2: neutralize prompt injection
            clean2, flagged = sanitize_prompt_injection(clean1)
            all_flagged.extend(flagged)

            cleaned[key] = clean2
        else:
            cleaned[key] = value

    report = {
        "flagged_injections": all_flagged,
        "pii_counts": all_pii,
    }
    return cleaned, report
