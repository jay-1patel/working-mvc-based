"""Regression tests for callback tenant safety and channel selection."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
for path in (BACKEND_DIR, PROJECT_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

from backend.services.callback_policy import choose_callback_mode
from backend.services.google_meet_service import generate_google_meet_link
from backend.services.token_storage import _open, _seal
from shared.tenancy import resolver


def _profile(**policy):
    return SimpleNamespace(
        features=SimpleNamespace(callback=True, book_appointment=True, human_handover=True),
        callback_policy=SimpleNamespace(
            mode=policy.get("mode", "auto"),
            allowed_modes=policy.get("allowed_modes", ["phone", "google_calendar", "booking_url", "human"]),
            booking_url=policy.get("booking_url", ""),
            instructions=policy.get("instructions", ""),
            require_consent=True,
        ),
    )


class CallbackSecurityPolicyTests(unittest.TestCase):
    def test_explicit_phone_instruction_beats_video_request(self):
        with patch("backend.services.callback_policy.get_tenant_profile", return_value=_profile(instructions="Phone only")):
            result = choose_callback_mode("tenant-a", "Please arrange a Google Meet")
        self.assertEqual(result.mode, "phone")

    def test_video_request_requires_tenant_google_token(self):
        with (
            patch("backend.services.callback_policy.get_tenant_profile", return_value=_profile()),
            patch("backend.services.callback_policy.get_token", return_value=None),
        ):
            result = choose_callback_mode("tenant-a", "I want a Google Meet")
        self.assertEqual(result.mode, "phone")

    def test_production_disables_test_override(self):
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=False):
            self.assertFalse(resolver._test_override_enabled())

    def test_synthetic_meet_links_are_rejected(self):
        with self.assertRaises(RuntimeError):
            generate_google_meet_link()

    def test_google_tokens_are_encrypted_at_rest(self):
        from cryptography.fernet import Fernet

        with patch.dict(os.environ, {"GOOGLE_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode()}, clear=False):
            sealed = _seal("refresh-secret")
            self.assertNotIn("refresh-secret", sealed)
            self.assertEqual(_open(sealed), "refresh-secret")


if __name__ == "__main__":
    unittest.main()

