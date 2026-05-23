"""Cloudflare R2 storage client — upload final MP4 → public URL.

R2 is S3-compatible, so boto3 with a custom endpoint URL works. We use lazy
import so the dependency is only required when R2 is actually configured —
local dev without R2 keys keeps working via `file://` URLs.

Settings (from core/config.py):
    r2_account_id        — your Cloudflare account ID
    r2_access_key_id     — R2 API token access key
    r2_secret_access_key — R2 API token secret
    r2_bucket_name       — bucket name (default: ugc-vietnam-output)
    r2_public_url        — public custom domain (e.g. https://cdn.example.com)
                           if empty, falls back to https://<account>.r2.cloudflarestorage.com/<bucket>/<key>

Public access:
    For public URL serving, bucket must have public access enabled OR be
    fronted by a Cloudflare Worker / custom domain.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional, Union

from loguru import logger

from core.config import settings


def is_configured() -> bool:
    """True when all required R2 settings are populated."""
    return bool(
        settings.r2_account_id
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
        and settings.r2_bucket_name
    )


def _get_client():
    """Lazy boto3 client. Raises RuntimeError if R2 not configured or boto3 missing."""
    if not is_configured():
        raise RuntimeError("R2 not configured — set r2_account_id / r2_access_key_id / r2_secret_access_key")
    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "boto3 not installed — `pip install boto3` to enable R2 uploads"
        ) from e

    endpoint = f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
    )


def _public_url_for(key: str) -> str:
    """Build the public-facing URL for an uploaded object."""
    if settings.r2_public_url:
        base = settings.r2_public_url.rstrip("/")
        return f"{base}/{key}"
    # Default Cloudflare R2 dev URL (works if public bucket / dev mode)
    return (
        f"https://{settings.r2_account_id}.r2.cloudflarestorage.com/"
        f"{settings.r2_bucket_name}/{key}"
    )


def upload_file_sync(
    local_path: Union[str, Path],
    key: str,
    content_type: str = "video/mp4",
    cache_control: str = "public, max-age=31536000, immutable",
) -> str:
    """Sync upload — returns public URL on success.

    Caller (async worker) should wrap via `asyncio.to_thread()`.
    """
    local = Path(local_path)
    if not local.exists():
        raise FileNotFoundError(f"R2 upload source not found: {local}")

    client = _get_client()
    extra: dict = {
        "ContentType": content_type,
        "CacheControl": cache_control,
    }
    logger.info(
        f"[R2] uploading {local.name} ({local.stat().st_size / 1024:.0f}KB) → "
        f"{settings.r2_bucket_name}/{key}"
    )
    client.upload_file(
        Filename=str(local),
        Bucket=settings.r2_bucket_name,
        Key=key,
        ExtraArgs=extra,
    )
    url = _public_url_for(key)
    logger.info(f"[R2] uploaded → {url}")
    return url


async def upload_file(
    local_path: Union[str, Path],
    key: str,
    content_type: str = "video/mp4",
) -> str:
    """Async wrapper around `upload_file_sync`."""
    return await asyncio.to_thread(
        upload_file_sync, local_path, key, content_type,
    )


async def upload_with_fallback(
    local_path: Union[str, Path],
    key: str,
    content_type: str = "video/mp4",
) -> str:
    """Upload to R2 if configured, else return `file://` URL for local dev.

    This is what `video_worker.render_plan()` should call — it gracefully
    degrades when R2 env vars are missing (so contributors can develop without
    Cloudflare credentials).
    """
    if not is_configured():
        local = Path(local_path).resolve()
        logger.warning(
            f"[R2] not configured — falling back to local file:// URL "
            f"(set r2_account_id + r2_access_key_id + r2_secret_access_key to enable)"
        )
        return f"file://{local.as_posix()}"
    try:
        return await upload_file(local_path, key, content_type)
    except Exception as e:
        # Don't fail the whole render just because upload failed — return file://
        # so the user still has a path to the local clip.
        logger.exception(f"[R2] upload failed — falling back to file://: {e}")
        local = Path(local_path).resolve()
        return f"file://{local.as_posix()}"
