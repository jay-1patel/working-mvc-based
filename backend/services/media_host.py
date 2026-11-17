"""Store WhatsApp media on this backend and return its configured public URL."""

from __future__ import annotations

import logging
import os
import re
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import quote

logger = logging.getLogger("media_host")

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}


def _is_image(filename: str, content_type: str = "") -> bool:
    return (content_type or "").lower().startswith("image/") or Path(filename or "").suffix.lower() in _IMAGE_EXTS


def _public_base_url() -> str:
    try:
        from routing.config import PUBLIC_BASE_URL

        return (PUBLIC_BASE_URL or "").strip().rstrip("/")
    except Exception:
        return (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")


def _upload_dir() -> str:
    """Return the same upload root mounted by ``backend/main.py``."""
    try:
        from routing.config import UPLOAD_DIR

        return os.path.abspath(UPLOAD_DIR)
    except Exception:
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.abspath(os.path.join(here, "..", "uploaded_files"))


def _safe_component(value: str, fallback: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(value or "")).strip("._")
    return value or fallback


def _public_upload_url(relative_path: str) -> Optional[str]:
    base = _public_base_url()
    if not base:
        return None
    encoded = "/".join(quote(part) for part in relative_path.replace("\\", "/").split("/") if part)
    return f"{base}/uploaded_files/{encoded}"


def host_via_public_base(content: bytes, filename: str, *, subdir: str = "media") -> Optional[str]:
    """Save bytes locally and return ``PUBLIC_BASE_URL/uploaded_files/...``."""
    if not content:
        return None
    if not _public_base_url():
        logger.error("media_host: PUBLIC_BASE_URL is not configured")
        return None

    safe_dir = _safe_component(subdir, "media")
    original = _safe_component(filename, "file.bin")
    stem = Path(original).stem[:80] or "file"
    suffix = Path(original).suffix[:12]
    stored_name = f"{stem}_{uuid.uuid4().hex}{suffix}"
    dest_dir = os.path.join(_upload_dir(), safe_dir)
    os.makedirs(dest_dir, exist_ok=True)
    with open(os.path.join(dest_dir, stored_name), "wb") as handle:
        handle.write(content)
    url = _public_upload_url(f"{safe_dir}/{stored_name}")
    logger.info("media_host: local -> %s", url)
    return url


def public_url_for_local_path(local_path: str) -> Optional[str]:
    """Map an existing file below ``UPLOAD_DIR`` to its backend URL."""
    if not local_path:
        return None
    root = os.path.realpath(_upload_dir())
    abs_path = os.path.realpath(local_path)
    try:
        if os.path.commonpath((root, abs_path)) != root:
            return None
        rel = os.path.relpath(abs_path, root)
    except ValueError:
        return None
    return _public_upload_url(rel)


def absolutize_upload_url(path_or_url: str) -> Optional[str]:
    """Turn ``/uploaded_files/...`` (or a bare relative path) into PUBLIC_BASE_URL."""
    if not path_or_url:
        return None
    value = str(path_or_url).strip()
    if value.startswith(("http://", "https://")):
        return value
    if value.startswith("/uploaded_files/"):
        base = _public_base_url()
        return f"{base}{value}" if base else value
    if value.startswith("uploaded_files/"):
        base = _public_base_url()
        return f"{base}/{value}" if base else f"/{value}"
    mapped = public_url_for_local_path(value)
    return mapped or value


def upload_public_media(content: bytes, filename: str, content_type: str = "", *, subdir: str = "media") -> Optional[str]:
    """Store media locally; no external image or document host is contacted."""
    return host_via_public_base(content, filename or "upload.bin", subdir=subdir)


def upload_public_image(content: bytes, filename: str, content_type: str = "") -> Optional[str]:
    """Store an image under the product-images upload directory."""
    name = filename or "image.png"
    if not _is_image(name, content_type):
        name = f"{Path(name).stem or 'image'}.png"
    return upload_public_media(content, name, content_type or "image/png", subdir="product_images")
