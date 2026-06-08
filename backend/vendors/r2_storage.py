"""Cloudflare R2 / S3-compatible storage helpers.

The legacy helpers return a URL string for existing render code. The production
helpers return a structured upload result with object key, bucket, public URL
and presigned URL so long-form final assembly can hand clients a time-limited
download URL instead of serving local files from the API server.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Union

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from core.config import settings
from core.env_guard import missing_secret_names

R2AccessMode = Literal["auto", "public", "private"]


class R2UploadResult(BaseModel):
    """Structured result for one uploaded R2/S3 object."""

    model_config = ConfigDict(extra="forbid")

    bucket: str
    key: str
    content_type: str
    size_bytes: int
    storage_type: str = "private"
    access_strategy: str = "private_presigned"
    delivery_url: str | None = None
    cdn_url: str | None = None
    is_public: bool = False
    public_url: str | None = None
    presigned_url: str | None = None
    presigned_expires_s: int | None = None
    presigned_expires_at: str | None = None
    refresh_supported: bool = False
    attempts: int = Field(1, ge=1)


def is_configured() -> bool:
    """Return true when all required R2/S3 credentials are available."""
    return not missing_secret_names(_required_r2_settings())


def endpoint_url() -> str:
    """Return the configured S3 endpoint URL for R2."""
    if settings.r2_endpoint_url:
        return settings.r2_endpoint_url.rstrip("/")
    return f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"


def _get_client() -> Any:
    """Create a boto3 S3 client for Cloudflare R2."""
    if not is_configured():
        raise RuntimeError(
            "R2 not configured; set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
            "R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME."
        )
    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
    except ImportError as exc:
        raise RuntimeError("boto3/botocore are required for R2 uploads") from exc

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url(),
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
    )


def public_url_for(key: str) -> str | None:
    """Return configured public URL when the bucket has a CDN/public domain."""
    if not settings.r2_public_url:
        return None
    return f"{settings.r2_public_url.rstrip('/')}/{key.lstrip('/')}"


def normalize_access_mode(value: str | None) -> R2AccessMode:
    """Normalize final video storage access mode from config or caller input."""
    mode = str(value or "auto").strip().lower()
    if mode in {"public", "private", "auto"}:
        return mode  # type: ignore[return-value]
    logger.warning("[R2] unknown access mode; falling back to auto", extra={"access_mode": value})
    return "auto"


def generate_presigned_url_sync(
    key: str,
    *,
    expires_s: int | None = None,
    client: Any | None = None,
) -> str:
    """Generate a time-limited GET URL for an uploaded object."""
    s3 = client or _get_client()
    ttl = int(expires_s or settings.r2_presigned_url_expires_s or 3600)
    return str(
        s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.r2_bucket_name, "Key": key},
            ExpiresIn=ttl,
        )
    )


def upload_file_result_sync(
    local_path: Union[str, Path],
    key: str,
    *,
    content_type: str = "video/mp4",
    cache_control: str = "public, max-age=31536000, immutable",
    max_attempts: int | None = None,
    presign: bool = True,
    presigned_expires_s: int | None = None,
    access_mode: str | None = None,
    client: Any | None = None,
) -> R2UploadResult:
    """Upload a local file to R2/S3 with bounded retry and optional presign."""
    local = Path(local_path)
    if not local.exists():
        raise FileNotFoundError(f"R2 upload source not found: {local}")
    s3 = client or _get_client()
    attempts = max(1, int(max_attempts or settings.r2_upload_max_attempts or 3))
    last_error: Exception | None = None
    object_key = key.strip().lstrip("/")
    mode = normalize_access_mode(access_mode)
    configured_public_url = public_url_for(object_key)
    if mode == "public" and not configured_public_url:
        raise RuntimeError("R2 public access mode requires R2_PUBLIC_URL or a public CDN domain.")
    for attempt in range(1, attempts + 1):
        try:
            logger.info(
                "[R2] uploading final object",
                extra={
                    "bucket": settings.r2_bucket_name,
                    "key": object_key,
                    "attempt": attempt,
                    "size_bytes": local.stat().st_size,
                },
            )
            s3.upload_file(
                Filename=str(local),
                Bucket=settings.r2_bucket_name,
                Key=object_key,
                ExtraArgs={
                    "ContentType": content_type,
                    "CacheControl": cache_control,
                },
            )
            is_public = bool(configured_public_url and mode != "private")
            ttl = int(presigned_expires_s or settings.r2_presigned_url_expires_s or 3600)
            presigned_url = (
                generate_presigned_url_sync(object_key, expires_s=ttl, client=s3)
                if presign
                else None
            )
            expires_at = _expires_at(ttl) if presigned_url else None
            delivery_url = configured_public_url if is_public else presigned_url
            access_strategy = "public_cdn" if is_public else ("private_presigned" if presigned_url else "private_object")
            result = R2UploadResult(
                bucket=settings.r2_bucket_name,
                key=object_key,
                content_type=content_type,
                size_bytes=local.stat().st_size,
                storage_type="public" if is_public else "private",
                access_strategy=access_strategy,
                delivery_url=delivery_url,
                cdn_url=configured_public_url,
                is_public=is_public,
                public_url=configured_public_url,
                presigned_url=presigned_url,
                presigned_expires_s=ttl if presign else None,
                presigned_expires_at=expires_at,
                refresh_supported=bool((not is_public) and presign and settings.r2_presigned_refresh_enabled),
                attempts=attempt,
            )
            logger.info(
                "[R2] upload completed",
                extra={
                    "bucket": result.bucket,
                    "key": result.key,
                    "attempts": result.attempts,
                    "access_strategy": result.access_strategy,
                    "is_public": result.is_public,
                    "has_presigned_url": bool(result.presigned_url),
                },
            )
            return result
        except Exception as exc:
            last_error = exc
            logger.warning(
                "[R2] upload attempt failed",
                extra={
                    "bucket": settings.r2_bucket_name,
                    "key": object_key,
                    "attempt": attempt,
                    "max_attempts": attempts,
                    "error": str(exc)[:300],
                },
            )
            if attempt < attempts:
                time.sleep(min(2 ** (attempt - 1), 8))
    raise RuntimeError(f"R2 upload failed after {attempts} attempts: {last_error}") from last_error


async def upload_file_result(
    local_path: Union[str, Path],
    key: str,
    *,
    content_type: str = "video/mp4",
    cache_control: str = "public, max-age=31536000, immutable",
    max_attempts: int | None = None,
    presign: bool = True,
    presigned_expires_s: int | None = None,
    access_mode: str | None = None,
) -> R2UploadResult:
    """Async wrapper for structured R2 upload result."""
    return await asyncio.to_thread(
        upload_file_result_sync,
        local_path,
        key,
        content_type=content_type,
        cache_control=cache_control,
        max_attempts=max_attempts,
        presign=presign,
        presigned_expires_s=presigned_expires_s,
        access_mode=access_mode,
    )


def refresh_presigned_url_sync(
    key: str,
    *,
    expires_s: int | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Return a refreshed private download URL for an existing object key."""
    ttl = int(expires_s or settings.r2_final_video_presigned_expires_s or settings.r2_presigned_url_expires_s or 3600)
    url = generate_presigned_url_sync(key, expires_s=ttl, client=client)
    return {
        "storage_presigned_url": url,
        "storage_presigned_expires_s": ttl,
        "storage_presigned_expires_at": _expires_at(ttl),
        "refresh_supported": bool(settings.r2_presigned_refresh_enabled),
    }


def delete_object_sync(key: str, *, client: Any | None = None) -> bool:
    """Best-effort deletion helper for cleanup workflows."""
    object_key = key.strip().lstrip("/")
    s3 = client or _get_client()
    s3.delete_object(Bucket=settings.r2_bucket_name, Key=object_key)
    logger.info("[R2] object deleted", extra={"bucket": settings.r2_bucket_name, "key": object_key})
    return True


def upload_file_sync(
    local_path: Union[str, Path],
    key: str,
    content_type: str = "video/mp4",
    cache_control: str = "public, max-age=31536000, immutable",
) -> str:
    """Legacy sync upload returning a URL string."""
    result = upload_file_result_sync(
        local_path,
        key,
        content_type=content_type,
        cache_control=cache_control,
        presign=True,
    )
    return result.delivery_url or result.presigned_url or result.public_url or ""


async def upload_file(
    local_path: Union[str, Path],
    key: str,
    content_type: str = "video/mp4",
) -> str:
    """Legacy async upload returning a URL string."""
    return await asyncio.to_thread(upload_file_sync, local_path, key, content_type)


async def upload_with_fallback(
    local_path: Union[str, Path],
    key: str,
    content_type: str = "video/mp4",
) -> str:
    """Upload to R2, with local file fallback only when explicitly enabled.

    Older render paths call this legacy helper, but it must not fabricate a
    storage URL. Missing or failed R2 now raises by default. Local `file://`
    fallback is available only for explicit development smoke work through
    `ALLOW_R2_LOCAL_FALLBACK=true` and `APP_ENV=development`.
    """
    if not is_configured():
        missing = missing_secret_names(_required_r2_settings())
        if _allow_local_fallback():
            local = Path(local_path).resolve()
            logger.warning("[R2] not configured; explicit dev fallback returning local file URL")
            return f"file://{local.as_posix()}"
        local = Path(local_path).resolve()
        raise RuntimeError(
            "R2 not configured; missing "
            + ", ".join(missing)
            + f". Refusing local storage fallback for {local.name}."
        )
    try:
        return await upload_file(local_path, key, content_type)
    except Exception as exc:
        if _allow_local_fallback():
            logger.exception(f"[R2] upload failed; explicit dev fallback returning local file URL: {exc}")
            local = Path(local_path).resolve()
            return f"file://{local.as_posix()}"
        raise


__all__ = [
    "R2UploadResult",
    "delete_object_sync",
    "endpoint_url",
    "generate_presigned_url_sync",
    "is_configured",
    "public_url_for",
    "refresh_presigned_url_sync",
    "upload_file",
    "upload_file_result",
    "upload_file_result_sync",
    "upload_file_sync",
    "upload_with_fallback",
]


def _expires_at(ttl_s: int) -> str:
    """Return an ISO timestamp for a presigned URL expiry."""
    return (datetime.now(timezone.utc) + timedelta(seconds=max(0, int(ttl_s)))).isoformat()


def _required_r2_settings() -> list[tuple[str, str]]:
    return [
        ("R2_ACCOUNT_ID", settings.r2_account_id),
        ("R2_ACCESS_KEY_ID", settings.r2_access_key_id),
        ("R2_SECRET_ACCESS_KEY", settings.r2_secret_access_key),
        ("R2_BUCKET_NAME", settings.r2_bucket_name),
    ]


def _allow_local_fallback() -> bool:
    return bool(
        settings.allow_r2_local_fallback
        and str(settings.app_env or "").strip().lower() == "development"
    )
