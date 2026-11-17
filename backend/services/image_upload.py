"""Local image hosting for WhatsApp media.

This helper used to live in `routes/chat.py`, which forced services
(`services/auto_bifurcator.py`) to import from a route module — a
backwards dependency. It now lives in the services layer; `routes/chat.py`
re-exports it for backwards compatibility.
"""
import logging

logger = logging.getLogger("image_upload")


def _upload_to_imghippo(content: bytes, filename: str) -> str | None:
    """Backward-compatible name: store media on this backend."""
    try:
        from services.media_host import upload_public_media
    except ImportError:
        from backend.services.media_host import upload_public_media
    return upload_public_media(content, filename)
