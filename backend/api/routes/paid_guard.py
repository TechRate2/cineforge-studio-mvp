"""Guards for endpoints that submit paid vendor jobs directly."""

from typing import Optional

from fastapi import HTTPException

from core.config import settings
from core.env_guard import is_configured_secret


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
    expected = settings.admin_api_key if is_configured_secret(settings.admin_api_key) else ""
    if not expected:
        raise_missing_vendor_env(
            ["ADMIN_API_KEY"],
            "Direct paid generation requires ADMIN_API_KEY. No vendor call was made.",
        )
    if x_admin_key != expected:
        raise HTTPException(403, "Unauthorized: direct paid generation requires X-Admin-Key")


def raise_missing_vendor_env(missing_env: list[str], message: str) -> None:
    """Fail closed before any vendor call when paid runtime env is absent."""
    raise HTTPException(
        424,
        detail={
            "code": "missing_env",
            "message": message,
            "missing_env": missing_env,
            "vendor_calls_performed": False,
        },
    )


__all__ = ["require_direct_paid_generation", "raise_missing_vendor_env"]
