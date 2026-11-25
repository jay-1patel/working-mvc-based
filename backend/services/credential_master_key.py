"""Platform-wide CREDENTIAL_MASTER_KEY for the Send2 credential vault.

One 256-bit key for the whole platform. Never auto-generated at startup —
a new key cannot decrypt data sealed with a previous key.
"""

from __future__ import annotations

import base64
import logging
import os
import sys

logger = logging.getLogger("credential_master_key")

ENV_NAME = "CREDENTIAL_MASTER_KEY"
KEY_BYTES = 32
GENERATE_HINT = (
    'python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"'
)


class CredentialMasterKeyError(RuntimeError):
    """Raised when CREDENTIAL_MASTER_KEY is missing or invalid."""


def _is_dev_environment() -> bool:
    env = (
        os.getenv("APP_ENV")
        or os.getenv("ENVIRONMENT")
        or os.getenv("ENV")
        or "development"
    ).strip().lower()
    return env in {"dev", "development", "local", "test", "testing"}


def _decode_master_key(raw: str) -> bytes:
    try:
        key = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise CredentialMasterKeyError(
            f"{ENV_NAME} is not valid base64"
        ) from exc
    if len(key) != KEY_BYTES:
        raise CredentialMasterKeyError(
            f"{ENV_NAME} must decode to exactly {KEY_BYTES} bytes "
            f"(got {len(key)})"
        )
    return key


def load_credential_master_key() -> bytes:
    """Return the 32-byte master key or raise CredentialMasterKeyError.

    Never logs or returns the key material as text.
    """
    raw = (os.environ.get(ENV_NAME) or "").strip()
    if not raw:
        raise CredentialMasterKeyError(f"{ENV_NAME} is missing")
    return _decode_master_key(raw)


def require_credential_master_key_at_startup() -> bytes:
    """Fail loudly during backend startup if the master key is unusable.

    In a local/dev environment with a missing key, prints the exact one-line
    generation command (never a real key value) and stops the process.
    """
    try:
        return load_credential_master_key()
    except CredentialMasterKeyError as exc:
        message = str(exc)
        if ENV_NAME in message and "missing" in message and _is_dev_environment():
            # Print only the operator command — never a generated key value.
            print(
                f"{ENV_NAME} is missing. Generate one on the server with:\n"
                f"{GENERATE_HINT}",
                file=sys.stderr,
            )
            raise SystemExit(1) from exc
        logger.error("CREDENTIAL_MASTER_KEY_INVALID | reason=%s", message)
        raise SystemExit(f"Startup aborted: {message}") from exc
