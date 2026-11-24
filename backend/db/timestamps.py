"""Canonical DB datetime stamps: ``DD-MM-YYYY HH:mm`` strings (no BSON Date)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

STAMP_FORMAT = "%d-%m-%Y %H:%M"

_PARSE_FORMATS = (
    STAMP_FORMAT,
    "%d-%m-%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%d %H:%M",
)


def now_stamp() -> str:
    """Current local wall-clock time in the DB stamp format."""
    return datetime.now().strftime(STAMP_FORMAT)


def to_stamp(value: Any) -> Optional[str]:
    """Normalize a datetime or common string into ``DD-MM-YYYY HH:mm``."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        local = value.astimezone().replace(tzinfo=None) if value.tzinfo else value
        return local.strftime(STAMP_FORMAT)
    text = str(value).strip()
    if not text:
        return None
    parsed = parse_stamp(text)
    if parsed is not None:
        local = parsed.astimezone().replace(tzinfo=None) if parsed.tzinfo else parsed
        return local.strftime(STAMP_FORMAT)
    return text


def parse_stamp(value: Any) -> Optional[datetime]:
    """Parse a stamp / ISO / legacy string into an aware UTC datetime."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    for fmt in _PARSE_FORMATS:
        try:
            sample = text[:26].replace("Z", "")
            # strptime needs exact length for some formats; trim to format width.
            width = len(datetime(2000, 1, 1).strftime(fmt))
            parsed = datetime.strptime(sample[:width], fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
    except ValueError:
        return None
