"""File-backed render feedback store for post-render evidence.

The benchmark gate must not promote a route from planning claims alone. This
store captures human/operator feedback against real job outputs so later audits
can distinguish proven quality from unverified routing assumptions.
"""
from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


_ROOT = Path(__file__).parent.parent / "data" / "render_feedback"
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,160}$")

ALLOWED_RATINGS = {"approved", "good", "needs_work", "bad"}
ALLOWED_ISSUE_TAGS = {
    "good",
    "weak_hook",
    "face_drift",
    "product_drift",
    "wrong_niche",
    "bad_motion",
    "audio_lipsync_issue",
    "prompt_mismatch",
    "text_artifact",
    "composition_issue",
    "too_generic",
    "safety_or_claim_issue",
    "continuity_break",
    "other",
}
NEGATIVE_RATINGS = {"needs_work", "bad"}
NEGATIVE_TAGS = ALLOWED_ISSUE_TAGS - {"good"}


def record_feedback(
    *,
    job_id: str,
    rating: str,
    issue_tags: list[str],
    notes: Optional[str] = None,
    reviewer: Optional[str] = None,
    output_url: Optional[str] = None,
    job_record: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Append one feedback entry and return the updated evidence document."""
    clean_job_id = _validate_job_id(job_id)
    clean_rating = _validate_rating(rating)
    clean_tags = _validate_tags(issue_tags)
    doc = load_feedback_doc(clean_job_id) or _new_doc(clean_job_id)
    now = datetime.now(timezone.utc).isoformat()
    job_record = job_record or {}
    entry = {
        "id": f"fb_{uuid.uuid4().hex[:12]}",
        "created_at": now,
        "rating": clean_rating,
        "issue_tags": clean_tags,
        "notes": (notes or "").strip()[:1200],
        "reviewer": (reviewer or "operator").strip()[:80],
        "output_url": (output_url or job_record.get("output_url") or job_record.get("output_path") or ""),
        "job_status": job_record.get("status"),
        "job_mode": job_record.get("mode"),
        "model_key": job_record.get("model_key") or job_record.get("requested_model_key"),
    }
    doc["entries"].append(entry)
    doc["updated_at"] = now
    doc["summary"] = summarize_feedback_doc(doc)
    _write_doc(clean_job_id, doc)
    return doc


def load_feedback_doc(job_id: str) -> Optional[dict[str, Any]]:
    """Load the persisted feedback document for one job."""
    clean_job_id = _validate_job_id(job_id)
    path = _path(clean_job_id)
    if not path.exists():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    if "summary" not in doc:
        doc["summary"] = summarize_feedback_doc(doc)
    return doc


def list_feedback(job_id: str) -> list[dict[str, Any]]:
    doc = load_feedback_doc(job_id)
    if not doc:
        return []
    entries = doc.get("entries") if isinstance(doc.get("entries"), list) else []
    return entries


def summarize_job_feedback(job_id: str) -> dict[str, Any]:
    doc = load_feedback_doc(job_id)
    if not doc:
        return _empty_summary()
    return summarize_feedback_doc(doc)


def build_feedback_evidence(job_id: str) -> dict[str, Any]:
    """Return benchmark-ready feedback evidence for a job."""
    doc = load_feedback_doc(job_id) or _new_doc(_validate_job_id(job_id))
    return {
        "schema_version": "cinejelly.render_feedback_evidence.v1",
        "job_id": doc["job_id"],
        "summary": summarize_feedback_doc(doc),
        "entries": doc.get("entries", []),
        "promotion_note": (
            "Human feedback is supporting evidence only; promotion still requires "
            "real output QA, benchmark scores, cost and latency evidence."
        ),
    }


def summarize_feedback_doc(doc: dict[str, Any]) -> dict[str, Any]:
    entries = doc.get("entries") if isinstance(doc.get("entries"), list) else []
    if not entries:
        return _empty_summary()
    tag_counts: Counter[str] = Counter()
    rating_counts: Counter[str] = Counter()
    for entry in entries:
        rating = str(entry.get("rating") or "")
        if rating:
            rating_counts[rating] += 1
        for tag in entry.get("issue_tags") or []:
            tag_counts[str(tag)] += 1
    latest = entries[-1]
    has_negative = any(
        entry.get("rating") in NEGATIVE_RATINGS
        or any(tag in NEGATIVE_TAGS for tag in (entry.get("issue_tags") or []))
        for entry in entries
    )
    return {
        "feedback_count": len(entries),
        "latest_feedback_at": latest.get("created_at"),
        "latest_rating": latest.get("rating"),
        "issue_counts": dict(sorted(tag_counts.items())),
        "rating_counts": dict(sorted(rating_counts.items())),
        "has_negative_feedback": has_negative,
        "has_blocking_issue": bool(
            latest.get("rating") in NEGATIVE_RATINGS
            or any(tag in NEGATIVE_TAGS for tag in (latest.get("issue_tags") or []))
        ),
        "recommended_next_action": _next_action(latest, has_negative),
    }


def _next_action(latest: dict[str, Any], has_negative: bool) -> str:
    if not latest:
        return "collect_feedback_after_real_render"
    if latest.get("rating") in {"approved", "good"} and not has_negative:
        return "eligible_for_controlled_benchmark_review"
    tags = set(latest.get("issue_tags") or [])
    if "prompt_mismatch" in tags or "wrong_niche" in tags:
        return "revise_brief_or_route_before_rerender"
    if "face_drift" in tags or "product_drift" in tags or "continuity_break" in tags:
        return "strengthen_reference_contract_and_keyframes"
    if "weak_hook" in tags or "too_generic" in tags:
        return "revise_hook_and_niche_playbook"
    if "audio_lipsync_issue" in tags:
        return "route_dialogue_or_voice_to_manual_review"
    return "review_feedback_before_promotion"


def _empty_summary() -> dict[str, Any]:
    return {
        "feedback_count": 0,
        "latest_feedback_at": None,
        "latest_rating": None,
        "issue_counts": {},
        "rating_counts": {},
        "has_negative_feedback": False,
        "has_blocking_issue": False,
        "recommended_next_action": "collect_feedback_after_real_render",
    }


def _new_doc(job_id: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": "cinejelly.render_feedback.v1",
        "job_id": job_id,
        "created_at": now,
        "updated_at": now,
        "entries": [],
        "summary": _empty_summary(),
    }


def _validate_job_id(job_id: str) -> str:
    value = str(job_id or "").strip()
    if not _JOB_ID_RE.match(value):
        raise ValueError("invalid job_id")
    return value


def _validate_rating(rating: str) -> str:
    value = str(rating or "").strip()
    if value not in ALLOWED_RATINGS:
        raise ValueError(f"rating must be one of {sorted(ALLOWED_RATINGS)}")
    return value


def _validate_tags(tags: list[str]) -> list[str]:
    clean: list[str] = []
    for raw in tags[:12]:
        tag = str(raw or "").strip()
        if not tag:
            continue
        if tag not in ALLOWED_ISSUE_TAGS:
            raise ValueError(f"unsupported issue tag: {tag}")
        if tag not in clean:
            clean.append(tag)
    return clean


def _path(job_id: str) -> Path:
    return _ROOT / f"{job_id}.json"


def _write_doc(job_id: str, doc: dict[str, Any]) -> None:
    _ROOT.mkdir(parents=True, exist_ok=True)
    path = _path(job_id)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)
