"""Canonical DB datetime stamps: ``DD-MM-YYYY HH:mm`` strings (no BSON Date).

Stamps are **local wall-clock** values. Never treat a stamp string as UTC and
convert it again — that shifts Activity log times (e.g. +5:30) and makes
every row show as \"just now\".
"""
from __future__ import annotations

import re
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

# Already-canonical local stamps must pass through unchanged.
_STAMP_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{4})[ T](\d{2}):(\d{2})(?::\d{2})?$")


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
    # Idempotent: stamp strings are already local wall-clock.
    match = _STAMP_RE.match(text)
    if match:
        dd, mm, yyyy, hh, minute = match.groups()
        return f"{dd}-{mm}-{yyyy} {hh}:{minute}"
    parsed = parse_stamp(text)
    if parsed is not None:
        local = parsed.astimezone().replace(tzinfo=None) if parsed.tzinfo else parsed
        return local.strftime(STAMP_FORMAT)
    return text


def parse_stamp(value: Any) -> Optional[datetime]:
    """Parse a stamp / ISO / legacy string into an aware UTC datetime.

    ``DD-MM-YYYY HH:mm`` stamps are local wall-clock: interpret them in the
    host local timezone, then convert to UTC. ISO strings with ``Z``/offsets
    keep their embedded zone.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc)
    text = str(value).strip()
    if not text:
        return None

    stamp_match = _STAMP_RE.match(text)
    if stamp_match:
        dd, mm, yyyy, hh, minute = stamp_match.groups()
        seconds = 0
        if len(text) >= 19 and text[16] == ":":
            try:
                seconds = int(text[17:19])
            except ValueError:
                seconds = 0
        naive = datetime(
            int(yyyy), int(mm), int(dd), int(hh), int(minute), seconds,
        )
        # Attach the host's local zone, then normalize to UTC.
        local_tz = datetime.now().astimezone().tzinfo or timezone.utc
        return naive.replace(tzinfo=local_tz).astimezone(timezone.utc)

    for fmt in _PARSE_FORMATS:
        if fmt in (STAMP_FORMAT, "%d-%m-%Y %H:%M:%S"):
            continue  # handled above
        try:
            sample = text[:26].replace("Z", "")
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
