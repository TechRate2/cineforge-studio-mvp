"""Media upload endpoint — wrap atlas_client.upload_media() để frontend upload local file.

POST /api/v1/upload-media
  multipart/form-data: file=<binary>
  → return { url: "https://static.atlascloud.ai/..." }
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from loguru import logger
import tempfile
from pathlib import Path

router = APIRouter()


@router.post("/upload-media")
async def upload_media(file: UploadFile = File(...)):
    """Upload file local → AtlasCloud → return public URL.

    Frontend dùng URL này làm reference cho image/video gen.
    """
    from vendors.atlascloud import atlas_client
    if atlas_client is None:
        raise HTTPException(500, detail="ATLASCLOUD_API_KEY chưa set")

    # Validate file type — AtlasCloud doc accepts image/video/audio
    if file.content_type and not file.content_type.startswith(("image/", "video/", "audio/")):
        raise HTTPException(400, detail=f"Unsupported content type: {file.content_type}")

    # Cap size 50MB (per AtlasCloud per-model schema, e.g. vidu Q3 allows 50MB)
    contents = await file.read()
    if len(contents) > 50 * 1024 * 1024:
        raise HTTPException(400, detail="File > 50MB, vui lòng resize trước")

    suffix = Path(file.filename or "upload.bin").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        url = atlas_client.upload_media(tmp_path)
        logger.info(f"Uploaded {file.filename} ({len(contents)} bytes) → {url}")
        return {"url": url, "filename": file.filename, "size_bytes": len(contents)}
    except Exception as e:
        logger.exception(f"Upload failed: {e}")
        raise HTTPException(502, detail=f"AtlasCloud upload failed: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)
