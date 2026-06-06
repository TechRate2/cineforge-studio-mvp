from agent.reference_intelligence import ReferenceIntelligenceService
from pipeline.contracts import AssetRef, ReferenceRole


def test_reference_intelligence_flags_missing_required_product_role() -> None:
    service = ReferenceIntelligenceService()

    report = service.analyze(
        assets=[
            AssetRef(
                asset_id="asset_style",
                kind="image",
                url="https://cdn.example.com/style.png",
                role=ReferenceRole.STYLE_REFERENCE,
                role_locked=True,
                role_confidence=0.9,
            )
        ],
        needs_product_lock=True,
    )

    assert report.status == "needs_review"
    assert ReferenceRole.PRODUCT_HERO.value in report.missing_required_roles
    assert any("missing_required_reference_role:product_hero" in warning for warning in report.warnings)


def test_reference_intelligence_blocks_media_asset_without_url() -> None:
    service = ReferenceIntelligenceService()

    report = service.analyze(
        assets=[
            AssetRef(
                asset_id="asset_product",
                kind="image",
                url="",
                role=ReferenceRole.PRODUCT_HERO,
                role_locked=True,
                role_confidence=0.95,
            )
        ],
        needs_product_lock=True,
    )

    assert report.status == "blocked"
    assert report.insights[0].readiness == "blocked"
    assert "missing_asset_url" in report.insights[0].warnings


def test_reference_intelligence_marks_locked_product_reference_ready() -> None:
    service = ReferenceIntelligenceService()

    report = service.analyze(
        assets=[
            AssetRef(
                asset_id="asset_product",
                kind="image",
                url="https://cdn.example.com/product.png",
                role=ReferenceRole.PRODUCT_HERO,
                role_locked=True,
                role_confidence=0.95,
            )
        ],
        needs_product_lock=True,
    )

    assert report.status == "ready"
    assert report.insights[0].readiness == "ready"
    assert report.insights[0].best_use.startswith("Keep product")
