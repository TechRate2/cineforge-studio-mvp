"""Phase 7A tests for Identity & Consistency Engine MVP."""
from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_identity_bible_builds_character_anchors_from_face_and_full_body_refs() -> None:
    """Character lock should identify face and full-body anchors when supplied."""
    from identity.consistency_scorer import ConsistencyScorer
    from identity.identity_bible import IdentityBibleBuilder
    from pipeline.contracts import AssetRef, InputContract, ReferenceRole
    from pipeline.input_analysis import InputAnalyzer

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create a 12s drama scene with the same woman character and emotional reveal.",
        duration_hint_s=12,
        assets=[
            AssetRef(kind="image", tag="@Image1", role=ReferenceRole.CHARACTER_ANCHOR, notes="woman face close-up portrait"),
            AssetRef(kind="image", tag="@Image2", role=ReferenceRole.CHARACTER_ANCHOR, notes="woman full-body outfit silhouette"),
        ],
    ))
    bible = IdentityBibleBuilder().build(analyzed)
    score = ConsistencyScorer().score(analyzed_input=analyzed, identity_bible=bible)

    assert bible.character.required is True
    assert bible.character.face_anchor_asset_id is not None
    assert bible.character.full_body_anchor_asset_id is not None
    assert "face close-up" in bible.character.stable_traits
    assert score.character_score >= 90
    assert score.overall_score >= 80


def test_identity_consistency_flags_missing_character_anchor_before_render() -> None:
    """Missing required identity anchors should lower consistency score deterministically."""
    from identity.consistency_scorer import ConsistencyScorer
    from identity.identity_bible import IdentityBibleBuilder
    from pipeline.contracts import InputContract
    from pipeline.input_analysis import InputAnalyzer

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create a 12s drama scene with the same woman character, emotional reveal, and consistent clothing.",
        duration_hint_s=12,
    ))
    bible = IdentityBibleBuilder().build(analyzed)
    score = ConsistencyScorer().score(analyzed_input=analyzed, identity_bible=bible)

    assert bible.character.required is True
    assert bible.character.risk_level == "high"
    assert "missing_character_anchor" in bible.character.warnings
    assert score.overall_score < 70
    assert "missing_character_anchor" in score.risk_flags

    policy = ConsistencyScorer().evaluate_policy(score)
    assert policy.action == "requires_review"
    assert "missing_required_consistency_anchor" in policy.reason_ids


def test_identity_bible_skips_invalid_assets_without_asset_id() -> None:
    """Invalid reference rows should not create empty identity anchors."""
    from identity.identity_bible import IdentityBibleBuilder
    from pipeline.contracts import InputContract
    from pipeline.input_analysis import InputAnalyzer

    analyzed = InputAnalyzer().analyze(InputContract(
        user_idea="Create a 12s product ad with the same product bottle.",
        duration_hint_s=12,
    ))
    analyzed = analyzed.model_copy(update={
        "metadata": {
            **analyzed.metadata,
            "assets": [
                {
                    "kind": "image",
                    "tag": "@Image1",
                    "role": "product_hero",
                    "notes": "product bottle packaging label",
                }
            ],
        }
    })

    bible = IdentityBibleBuilder().build(analyzed)

    assert bible.anchors == []
    assert "invalid_reference_asset_missing_asset_id" in bible.warnings
    assert bible.metadata["invalid_anchor_count"] == 1


def test_reference_policy_exposes_identity_anchor_requirements_and_sufficiency_score() -> None:
    """ReferencePolicy should support Phase 7A without owning the full bible logic."""
    from pipeline.contracts import AssetRef, ReferenceRole
    from seedance.reference_policy import ReferencePolicy

    policy = ReferencePolicy()
    requirements = policy.build_identity_anchor_requirements(
        needs_character_lock=True,
        needs_product_lock=True,
    )
    score = policy.score_reference_sufficiency(
        assets=[
            AssetRef(kind="image", tag="@Image1", role=ReferenceRole.CHARACTER_ANCHOR, notes="face close-up portrait"),
        ],
        needs_character_lock=True,
        needs_product_lock=True,
    )

    assert ReferenceRole.CHARACTER_ANCHOR.value in requirements["required_roles"]
    assert ReferenceRole.PRODUCT_HERO.value in requirements["required_roles"]
    assert score["score"] < 100
    assert "phase7a.reference.missing_product_identity_bible_anchor" in score["issue_rule_ids"]
