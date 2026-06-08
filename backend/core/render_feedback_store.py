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

from core.deliverable_url import deliverable_http_url


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
POSITIVE_RATINGS = {"approved", "good"}


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
    _validate_rating_tag_consistency(clean_rating, clean_tags)
    clean_output_url = _validate_output_url(output_url, explicit=True)
    doc = load_feedback_doc(clean_job_id) or _new_doc(clean_job_id)
    now = datetime.now(timezone.utc).isoformat()
    job_record = job_record or {}
    job_output_url = _validate_output_url(job_record.get("output_url"), explicit=False)
    _validate_positive_feedback_gate(
        rating=clean_rating,
        tags=clean_tags,
        output_url=clean_output_url or job_output_url,
        job_record=job_record,
    )
    delivery_qa = _delivery_qa(job_record)
    job_local_output = _local_output_path(job_record)
    entry = {
        "id": f"fb_{uuid.uuid4().hex[:12]}",
        "created_at": now,
        "rating": clean_rating,
        "issue_tags": clean_tags,
        "notes": (notes or "").strip()[:1200],
        "reviewer": (reviewer or "operator").strip()[:80],
        "output_url": clean_output_url or job_output_url or "",
        "local_output_path": job_local_output,
        "job_status": job_record.get("status"),
        "job_mode": job_record.get("mode"),
        "model_key": job_record.get("model_key") or job_record.get("requested_model_key"),
        "delivery_qa_status": str(delivery_qa.get("status") or "").strip() if delivery_qa else "",
        "delivery_qa_errors": _string_list(delivery_qa.get("errors") if delivery_qa else []),
        "delivery_qa_warnings": _string_list(delivery_qa.get("warnings") if delivery_qa else []),
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
    integrity = feedback_evidence_integrity(doc)
    return {
        "schema_version": "cinejelly.render_feedback_evidence.v1",
        "job_id": doc["job_id"],
        "summary": summarize_feedback_doc(doc),
        "entries": doc.get("entries", []),
        "integrity": integrity,
        "promotion_note": (
            "Human feedback is supporting evidence only; promotion still requires "
            "real output QA, benchmark scores, cost and latency evidence."
        ),
    }


def summarize_feedback_doc(doc: dict[str, Any]) -> dict[str, Any]:
    entries = doc.get("entries") if isinstance(doc.get("entries"), list) else []
    if not entries:
        return _empty_summary()
    integrity = feedback_evidence_integrity(doc)
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
            or not integrity["promotion_safe"]
        ),
        "has_invalid_positive_evidence": not integrity["promotion_safe"],
        "evidence_integrity_issues": integrity["issues"],
        "recommended_next_action": _next_action(latest, has_negative, integrity["issues"]),
    }


def feedback_evidence_integrity(doc: dict[str, Any]) -> dict[str, Any]:
    entries = doc.get("entries") if isinstance(doc.get("entries"), list) else []
    issues: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            issues.append(f"entry_{index}_invalid_shape")
            continue
        rating = str(entry.get("rating") or "").strip()
        tags = [str(tag or "").strip() for tag in (entry.get("issue_tags") or []) if str(tag or "").strip()]
        tag_set = set(tags)
        positive = rating in POSITIVE_RATINGS or tag_set == {"good"}
        if rating in POSITIVE_RATINGS and tag_set & NEGATIVE_TAGS:
            issues.append(f"entry_{index}_positive_feedback_has_issue_tags")
        if rating in NEGATIVE_RATINGS and "good" in tag_set:
            issues.append(f"entry_{index}_negative_feedback_has_good_tag")
        if positive:
            if not deliverable_http_url(entry.get("output_url")):
                issues.append(f"entry_{index}_positive_feedback_missing_real_output_url")
            if not _delivery_qa_passed_cleanly(_delivery_qa(entry)):
                issues.append(f"entry_{index}_positive_feedback_missing_clean_delivery_qa")
    return {
        "schema_version": "cinejelly.render_feedback_integrity.v1",
        "promotion_safe": len(issues) == 0,
        "issues": list(dict.fromkeys(issues)),
    }


def _next_action(latest: dict[str, Any], has_negative: bool, integrity_issues: list[str] | None = None) -> str:
    if not latest:
        return "collect_feedback_after_real_render"
    if integrity_issues:
        return "review_feedback_integrity_before_promotion"
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


def _validate_rating_tag_consistency(rating: str, tags: list[str]) -> None:
    tag_set = set(tags)
    if rating in POSITIVE_RATINGS and tag_set & NEGATIVE_TAGS:
        raise ValueError("positive feedback cannot include issue tags")
    if rating in NEGATIVE_RATINGS and "good" in tag_set:
        raise ValueError("negative feedback cannot include good tag")


def _validate_positive_feedback_gate(
    *,
    rating: str,
    tags: list[str],
    output_url: str,
    job_record: dict[str, Any],
) -> None:
    """Positive feedback is promotion-adjacent evidence; require clean delivery QA."""
    positive = rating in POSITIVE_RATINGS or (set(tags) == {"good"})
    if not positive:
        return
    if not output_url:
        raise ValueError("approved feedback requires a real HTTP(S) output URL")
    qa = _delivery_qa(job_record)
    if not _delivery_qa_passed_cleanly(qa):
        raise ValueError("approved feedback requires final delivery QA pass with no warnings/errors")


def _validate_output_url(value: Optional[str], *, explicit: bool) -> str:
    if not str(value or "").strip():
        return ""
    url = deliverable_http_url(value)
    if url:
        return url
    if explicit:
        raise ValueError("output_url must be a real HTTP(S) render URL")
    return ""


def _local_output_path(job_record: dict[str, Any]) -> str:
    output_path = str(job_record.get("output_path") or "").strip()
    output_url = str(job_record.get("output_url") or "").strip()
    if output_path and not deliverable_http_url(output_path):
        return output_path
    if output_url and not deliverable_http_url(output_url):
        return output_url
    return ""


def _delivery_qa(job_record: dict[str, Any]) -> dict[str, Any]:
    assembly = job_record.get("assembly_result")
    if not isinstance(assembly, dict):
        assembly = job_record.get("assembly")
    if not isinstance(assembly, dict):
        assembly = {}
    qa = assembly.get("final_delivery_qa") or job_record.get("final_delivery_qa")
    if isinstance(qa, dict):
        return qa
    if job_record.get("delivery_qa_status"):
        return {
            "status": job_record.get("delivery_qa_status"),
            "errors": job_record.get("delivery_qa_errors") or [],
            "warnings": job_record.get("delivery_qa_warnings") or [],
        }
    return {}


def _delivery_qa_passed_cleanly(qa: dict[str, Any]) -> bool:
    status = str(qa.get("status") or "").strip().lower()
    if status not in {"pass", "success", "succeeded"}:
        return False
    return not _string_list(qa.get("errors")) and not _string_list(qa.get("warnings"))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _path(job_id: str) -> Path:
    return _ROOT / f"{job_id}.json"


def _write_doc(job_id: str, doc: dict[str, Any]) -> None:
    _ROOT.mkdir(parents=True, exist_ok=True)
    path = _path(job_id)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)
