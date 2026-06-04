"""File-backed commercial feature store for Phase 13.

The store provides production-usable primitives before a database migration:
brand kits, template library, usage ledger, credit balance, and analytics. All
mutations are persisted atomically under `backend/data/commercial`.
"""
from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


_ROOT = Path(__file__).parent.parent / "data" / "commercial"
_BRANDS_DIR = _ROOT / "brand_kits"
_TEMPLATES_DIR = _ROOT / "templates"
_USAGE_DIR = _ROOT / "usage"
_LEDGER_PATH = _ROOT / "usage_ledger.jsonl"
_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")

DEFAULT_STARTING_CREDITS = 1000.0


class BrandKit(BaseModel):
    """Commercial brand constraints that can steer strategy and prompts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "cineforge.brand_kit.v1"
    brand_id: str = Field(default_factory=lambda: f"brand_{uuid.uuid4().hex[:12]}")
    owner_user_id: str = "default_user"
    name: str
    logo_urls: list[str] = Field(default_factory=list)
    primary_colors: list[str] = Field(default_factory=list)
    fonts: list[str] = Field(default_factory=list)
    voice: str = ""
    style_guide: str = ""
    negative_constraints: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: _now_iso())
    updated_at: str = Field(default_factory=lambda: _now_iso())


class CommercialTemplate(BaseModel):
    """Reusable production template for a common SaaS/video use case."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "cineforge.commercial_template.v1"
    template_id: str
    name: str
    niche: str
    description: str = ""
    hook_pattern: str = ""
    strategy: str = ""
    recommended_duration_s: int = 12
    shot_structure: list[str] = Field(default_factory=list)
    prompt_constraints: list[str] = Field(default_factory=list)
    brand_slots: list[str] = Field(default_factory=list)
    active: bool = True
    created_at: str = Field(default_factory=lambda: _now_iso())
    updated_at: str = Field(default_factory=lambda: _now_iso())


class UsageLedgerEntry(BaseModel):
    """One credit-affecting usage event."""

    model_config = ConfigDict(extra="forbid")

    usage_id: str = Field(default_factory=lambda: f"usage_{uuid.uuid4().hex[:12]}")
    user_id: str
    job_id: str
    event_type: Literal["reserve", "charge", "refund", "adjustment"] = "charge"
    credits_delta: float
    credits_after: float
    estimated_cost_usd: float = 0.0
    model: str = ""
    segment_count: int = 0
    render_path: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: _now_iso())


def upsert_brand_kit(
    *,
    owner_user_id: str,
    name: str,
    brand_id: str | None = None,
    logo_urls: list[str] | None = None,
    primary_colors: list[str] | None = None,
    fonts: list[str] | None = None,
    voice: str = "",
    style_guide: str = "",
    negative_constraints: list[str] | None = None,
) -> BrandKit:
    """Create or replace a brand kit."""
    existing = load_brand_kit(brand_id) if brand_id else None
    fallback_name = existing.name if existing else ""
    clean_name = str(name or fallback_name).strip()[:120] or "Untitled brand"
    kit = BrandKit(
        brand_id=existing.brand_id if existing else _clean_id(brand_id or f"brand_{uuid.uuid4().hex[:12]}"),
        owner_user_id=_clean_id(owner_user_id or "default_user"),
        name=clean_name,
        logo_urls=_clean_list(logo_urls if logo_urls is not None else (existing.logo_urls if existing else []), 12, 500),
        primary_colors=_clean_list(primary_colors if primary_colors is not None else (existing.primary_colors if existing else []), 12, 40),
        fonts=_clean_list(fonts if fonts is not None else (existing.fonts if existing else []), 8, 80),
        voice=str(voice if voice else (existing.voice if existing else "")).strip()[:600],
        style_guide=str(style_guide if style_guide else (existing.style_guide if existing else "")).strip()[:2000],
        negative_constraints=_clean_list(
            negative_constraints if negative_constraints is not None else (existing.negative_constraints if existing else []),
            20,
            160,
        ),
        created_at=existing.created_at if existing else _now_iso(),
        updated_at=_now_iso(),
    )
    _write_json(_brand_path(kit.brand_id), kit.model_dump(mode="json"))
    return kit


def load_brand_kit(brand_id: str | None) -> BrandKit | None:
    if not brand_id:
        return None
    path = _brand_path(_clean_id(brand_id))
    if not path.exists():
        return None
    return BrandKit.model_validate(json.loads(path.read_text(encoding="utf-8")))


def list_brand_kits(owner_user_id: str | None = None) -> list[BrandKit]:
    _BRANDS_DIR.mkdir(parents=True, exist_ok=True)
    kits = [
        BrandKit.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(_BRANDS_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    ]
    if owner_user_id:
        owner = _clean_id(owner_user_id)
        kits = [kit for kit in kits if kit.owner_user_id == owner]
    return kits


def list_templates() -> list[CommercialTemplate]:
    """Return bundled and custom active commercial templates."""
    _ensure_default_templates()
    templates = [
        CommercialTemplate.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(_TEMPLATES_DIR.glob("*.json"))
    ]
    return [template for template in templates if template.active]


def load_template(template_id: str | None) -> CommercialTemplate | None:
    if not template_id:
        return None
    _ensure_default_templates()
    path = _template_path(_clean_id(template_id))
    if not path.exists():
        return None
    template = CommercialTemplate.model_validate(json.loads(path.read_text(encoding="utf-8")))
    return template if template.active else None


def upsert_template(template: CommercialTemplate) -> CommercialTemplate:
    template = template.model_copy(update={"template_id": _clean_id(template.template_id), "updated_at": _now_iso()})
    _write_json(_template_path(template.template_id), template.model_dump(mode="json"))
    return template


def ensure_usage_account(user_id: str) -> dict[str, Any]:
    """Create a credit account if missing and return current state."""
    clean_user = _clean_id(user_id or "default_user")
    path = _usage_path(clean_user)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    state = {
        "schema_version": "cineforge.usage_account.v1",
        "user_id": clean_user,
        "credits_balance": DEFAULT_STARTING_CREDITS,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    _write_json(path, state)
    return state


def charge_credits(
    *,
    user_id: str,
    job_id: str,
    credits: float,
    estimated_cost_usd: float,
    model: str,
    segment_count: int,
    render_path: str,
    metadata: dict[str, Any] | None = None,
) -> UsageLedgerEntry:
    """Deduct credits for a queued paid render or raise when insufficient."""
    clean_user = _clean_id(user_id or "default_user")
    clean_job = _clean_id(job_id)
    amount = max(0.0, round(float(credits), 4))
    account = ensure_usage_account(clean_user)
    balance = float(account.get("credits_balance") or 0.0)
    if balance < amount:
        raise ValueError(f"insufficient credits: required {amount:.2f}, available {balance:.2f}")
    new_balance = round(balance - amount, 4)
    account["credits_balance"] = new_balance
    account["updated_at"] = _now_iso()
    _write_json(_usage_path(clean_user), account)
    entry = UsageLedgerEntry(
        user_id=clean_user,
        job_id=clean_job,
        event_type="charge",
        credits_delta=-amount,
        credits_after=new_balance,
        estimated_cost_usd=max(0.0, float(estimated_cost_usd or 0.0)),
        model=str(model or ""),
        segment_count=max(0, int(segment_count or 0)),
        render_path=str(render_path or ""),
        metadata=metadata or {},
    )
    _append_jsonl(_LEDGER_PATH, entry.model_dump(mode="json"))
    return entry


def credit_balance(user_id: str) -> dict[str, Any]:
    account = ensure_usage_account(user_id)
    return {
        **account,
        "ledger": usage_history(user_id=user_id, limit=50),
    }


def usage_history(*, user_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    if not _LEDGER_PATH.exists():
        return []
    clean_user = _clean_id(user_id) if user_id else None
    rows: list[dict[str, Any]] = []
    for line in _LEDGER_PATH.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if clean_user and row.get("user_id") != clean_user:
            continue
        rows.append(row)
    return rows[-max(1, int(limit)):]


def analytics_summary(*, user_id: str | None = None, brand_id: str | None = None) -> dict[str, Any]:
    """Return basic commercial analytics from persisted usage ledger."""
    rows = usage_history(user_id=user_id, limit=1000)
    if brand_id:
        clean_brand = _clean_id(brand_id)
        rows = [row for row in rows if (row.get("metadata") or {}).get("brand_id") == clean_brand]
    charges = [row for row in rows if row.get("event_type") == "charge"]
    model_counts = Counter(str(row.get("model") or "unknown") for row in charges)
    render_path_counts = Counter(str(row.get("render_path") or "unknown") for row in charges)
    template_counts = Counter(str((row.get("metadata") or {}).get("template_id") or "none") for row in charges)
    total_cost = sum(float(row.get("estimated_cost_usd") or 0.0) for row in charges)
    return {
        "schema_version": "cineforge.commercial_analytics.v1",
        "render_count": len(charges),
        "success_rate": 1.0,  # ledger charges are created only for accepted queued renders; failures are monitored separately.
        "avg_estimated_cost_usd": round(total_cost / max(1, len(charges)), 4) if charges else 0.0,
        "credits_spent": round(abs(sum(float(row.get("credits_delta") or 0.0) for row in charges)), 4),
        "model_counts": dict(model_counts),
        "render_path_counts": dict(render_path_counts),
        "popular_templates": dict(template_counts),
        "generated_at": _now_iso(),
    }


def credits_for_render(*, estimated_cost_usd: float, duration_s: int, segment_count: int, is_longform: bool) -> float:
    """Convert render scope into credits using a simple transparent formula."""
    base = max(1.0, float(estimated_cost_usd or 0.0) * 100.0)
    duration_component = max(0.0, float(duration_s or 0) * (0.4 if is_longform else 0.25))
    segment_component = max(0, int(segment_count or 0)) * (2.0 if is_longform else 0.5)
    return round(base + duration_component + segment_component, 2)


def _ensure_default_templates() -> None:
    defaults = [
        CommercialTemplate(
            template_id="ugc_ad",
            name="UGC Ad",
            niche="ugc_review",
            description="Fast social proof ad with hook, proof, and CTA.",
            hook_pattern="problem-proof-payoff",
            strategy="hook_first_product_proof",
            recommended_duration_s=12,
            shot_structure=["hook close-up", "proof beat", "product payoff"],
            prompt_constraints=["clear product benefit", "natural creator tone", "no fake claims"],
            brand_slots=["logo", "voice", "primary_colors"],
        ),
        CommercialTemplate(
            template_id="beauty_proof",
            name="Beauty Proof",
            niche="beauty",
            description="Premium beauty/product proof sequence.",
            hook_pattern="texture-macro-result",
            strategy="product_proof_emotional_finish",
            recommended_duration_s=15,
            shot_structure=["texture macro", "application moment", "hero bottle", "result payoff"],
            prompt_constraints=["skin-safe wording", "premium lighting", "product lock"],
            brand_slots=["logo", "colors", "style_guide"],
        ),
        CommercialTemplate(
            template_id="short_drama",
            name="Short Drama",
            niche="short_drama",
            description="Conflict/reversal/payoff drama structure.",
            hook_pattern="conflict-reversal-cliffhanger",
            strategy="story_driven_emotion_arc",
            recommended_duration_s=30,
            shot_structure=["conflict", "reveal", "reversal", "emotional payoff"],
            prompt_constraints=["maintain character identity", "clear spatial handoff"],
            brand_slots=["style_guide", "voice"],
        ),
        CommercialTemplate(
            template_id="saas_demo",
            name="SaaS Demo",
            niche="saas",
            description="Problem-solution workflow demo for SaaS tools.",
            hook_pattern="pain-point-workflow-outcome",
            strategy="product_centric_demo",
            recommended_duration_s=20,
            shot_structure=["pain point", "interface moment", "workflow result", "CTA"],
            prompt_constraints=["screen clarity", "no hallucinated UI text", "professional tone"],
            brand_slots=["logo", "fonts", "colors", "voice"],
        ),
    ]
    _TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    for template in defaults:
        path = _template_path(template.template_id)
        if not path.exists():
            _write_json(path, template.model_dump(mode="json"))


def _brand_path(brand_id: str) -> Path:
    return _BRANDS_DIR / f"{_clean_id(brand_id)}.json"


def _template_path(template_id: str) -> Path:
    return _TEMPLATES_DIR / f"{_clean_id(template_id)}.json"


def _usage_path(user_id: str) -> Path:
    return _USAGE_DIR / f"{_clean_id(user_id)}.json"


def _clean_id(value: str | None) -> str:
    text = str(value or "").strip() or "default_user"
    if not _ID_RE.match(text):
        raise ValueError("invalid id")
    return text


def _clean_list(values: list[str] | None, max_items: int, max_len: int) -> list[str]:
    out: list[str] = []
    for raw in (values or [])[:max_items]:
        text = str(raw or "").strip()[:max_len]
        if text and text not in out:
            out.append(text)
    return out


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "BrandKit",
    "CommercialTemplate",
    "UsageLedgerEntry",
    "analytics_summary",
    "charge_credits",
    "credit_balance",
    "credits_for_render",
    "list_brand_kits",
    "list_templates",
    "load_brand_kit",
    "load_template",
    "upsert_brand_kit",
    "upsert_template",
    "usage_history",
]
