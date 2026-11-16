"""Authentication value normalization for the Send2Digital handoff."""

import base64
import hmac


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
    canonical = base64.b64encode(decoded.encode("utf-8")).decode("ascii")
    if not hmac.compare_digest(canonical, value):
        raise ValueError("invalid encoded username")
    return decoded
