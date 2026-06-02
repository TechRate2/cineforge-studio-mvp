"""Guards for endpoints that submit paid vendor jobs directly."""

from typing import Optional

from fastapi import HTTPException

from core.config import settings


def require_direct_paid_generation(x_admin_key: Optional[str]) -> None:
    """Block direct paid generation unless explicitly enabled for operators.

    Normal SaaS users should go through the autonomous approval/render flow.
    These direct endpoints bypass the Agent and are kept as internal tools.
    """
    if not settings.allow_direct_paid_generation:
        raise HTTPException(
            403,
            "Direct paid generation is disabled. Use the approved autonomous render flow or set ALLOW_DIRECT_PAID_GENERATION=true for operator tools.",
        )
    expected = settings.admin_api_key
    if not expected:
        raise HTTPException(403, "Set ADMIN_API_KEY before enabling direct paid generation")
    if x_admin_key != expected:
        raise HTTPException(403, "Unauthorized: direct paid generation requires X-Admin-Key")
