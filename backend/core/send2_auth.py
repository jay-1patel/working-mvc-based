"""Authentication value normalization for the Send2Digital handoff."""

import base64
import hmac


def encode_send2_username(plain_username: str) -> str:
    """Return the canonical Base64 form Send2Digital stores for a username."""
    value = str(plain_username or "").strip()
    if not value:
        raise ValueError("username is required")
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def decode_send2_username(encoded_username: str) -> str:
    """Return the canonical UTF-8 username from Send2Digital Base64."""
    value = str(encoded_username or "").strip()
    if not value:
        raise ValueError("username is required")
    try:
        decoded_bytes = base64.b64decode(value, validate=True)
        decoded = decoded_bytes.decode("utf-8").strip()
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid encoded username") from exc
    if not decoded:
        raise ValueError("invalid encoded username")

    # Only accept the canonical representation so two encodings cannot refer
    # to the same local admin identity.
    canonical = encode_send2_username(decoded)
    if not hmac.compare_digest(canonical, value):
        raise ValueError("invalid encoded username")
    return decoded


def normalize_login_username(username: str) -> str:
    """Accept a plain username, or legacy Base64, and return the plain form.

    Login callers should send decoded names like ``test_support_``. If an
    already-encoded Send2 value is supplied, decode it once for lookup.
    """
    value = str(username or "").strip()
    if not value:
        raise ValueError("username is required")
    try:
        return decode_send2_username(value)
    except ValueError:
        return value


def admin_username_candidates(username: str) -> list[str]:
    """Ordered username keys to try against ``admins.username``.

    Send2 rows are often stored Base64-encoded; local admins keep the plain
    name. Try encoded first, then plain, without duplicates.
    """
    plain = normalize_login_username(username)
    encoded = encode_send2_username(plain)
    out: list[str] = []
    for candidate in (encoded, plain):
        if candidate and candidate not in out:
            out.append(candidate)
    return out
