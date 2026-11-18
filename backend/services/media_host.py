"""Store WhatsApp media on this backend and return PUBLIC_BASE_URL links.

PDFs and photos both use the same Cloudflare (or other public HTTPS) origin
from ``routing/.env`` → ``PUBLIC_BASE_URL``. No third-party host is contacted.
When that env value changes, restart the backend; outbound sends rebase
``/uploaded_files/...`` paths onto the new origin automatically.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlparse

logger = logging.getLogger("media_host")

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}
_REBASE_PREFIXES = (
    "/uploaded_files/",
    "/media/serve/",
    "/api/uploads/",
    "/api/logos/",
    "/crawl_images/",
)


def _is_image(filename: str, content_type: str = "") -> bool:
    return (content_type or "").lower().startswith("image/") or Path(filename or "").suffix.lower() in _IMAGE_EXTS


def _public_base_url() -> str:
    """Read the public origin from env (.env → PUBLIC_BASE_URL only)."""
    live = (os.getenv("PUBLIC_BASE_URL") or os.getenv("IMAGE_BASE_URL") or "").strip().rstrip("/")
    if live:
        return live
    try:
        from routing.config import PUBLIC_BASE_URL

        return (PUBLIC_BASE_URL or "").strip().rstrip("/")
    except Exception:
        return ""


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


def rebase_public_url(path_or_url: str) -> Optional[str]:
    """Map a media path/URL onto the current ``PUBLIC_BASE_URL``.

    Absolute links that still point at an old LAN/tunnel host but keep a
    backend media path (``/uploaded_files/...`` etc.) are rewritten so a
    Cloudflare URL change in ``.env`` applies without re-uploading files.
    """
    if not path_or_url:
        return None
    value = str(path_or_url).strip()
    base = _public_base_url()
    if not base:
        return value

    if value.startswith(base + "/") or value == base:
        return value

    path = value
    query = ""
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        path = parsed.path or ""
        query = f"?{parsed.query}" if parsed.query else ""
    elif not value.startswith("/"):
        mapped = public_url_for_local_path(value)
        return mapped or value

    for prefix in _REBASE_PREFIXES:
        if path.startswith(prefix):
            return f"{base}{path}{query}"
    return value


def host_via_public_base(content: bytes, filename: str, *, subdir: str = "media") -> Optional[str]:
    """Save bytes locally and return ``PUBLIC_BASE_URL/uploaded_files/...``."""
    if not content:
        return None
    if not _public_base_url():
        logger.error("media_host: PUBLIC_BASE_URL is not configured in routing/.env")
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
    """Turn a local upload path (or old absolute media URL) into PUBLIC_BASE_URL."""
    return rebase_public_url(path_or_url)


def upload_public_media(content: bytes, filename: str, content_type: str = "", *, subdir: str = "media") -> Optional[str]:
    """Store media locally; PDF and photo URLs both use PUBLIC_BASE_URL."""
    return host_via_public_base(content, filename or "upload.bin", subdir=subdir)


def upload_public_image(content: bytes, filename: str, content_type: str = "") -> Optional[str]:
    """Store an image under the product-images upload directory."""
    name = filename or "image.png"
    if not _is_image(name, content_type):
        name = f"{Path(name).stem or 'image'}.png"
    return upload_public_media(content, name, content_type or "image/png", subdir="product_images")
