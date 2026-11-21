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


def is_encoded_send2_username(username: str) -> bool:
    """True when ``username`` is already the canonical Send2 Base64 form."""
    try:
        decode_send2_username(username)
        return True
    except ValueError:
        return False


def normalize_login_username(username: str) -> str:
    """Require a plain username for login / session auth.

    Callers must send decoded names like ``test_support_``. Already-encoded
    Send2 Base64 values are rejected so credentials cannot be pasted as Base64.
    """
    value = str(username or "").strip()
    if not value:
        raise ValueError("username is required")
    if is_encoded_send2_username(value):
        raise ValueError("username must be plain text, not Base64")
    return value


def decode_stored_username(username: str | None) -> str:
    """Decode a DB ``admins.username`` value to the plain form for API/UI.

    Stored rows are usually Base64; plain local rows pass through unchanged.
    """
    value = str(username or "").strip()
    if not value:
        return ""
    try:
        return decode_send2_username(value)
    except ValueError:
        return value


def admin_username_candidates(username: str) -> list[str]:
    """DB lookup keys for ``admins.username`` (Base64 only).

    Plain login input is encoded once; encoded login input is rejected by
    ``normalize_login_username``.
    """
    plain = normalize_login_username(username)
    return [encode_send2_username(plain)]
