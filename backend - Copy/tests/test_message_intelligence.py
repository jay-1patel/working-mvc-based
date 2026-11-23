"""UC-01..UC-05 message intelligence — taxonomy-driven, feature-gated."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class MessageIntelligenceUnitTests(unittest.TestCase):
    """Pure classifier helpers — no DB."""

    def test_sentiment_and_topics_against_automotive_taxonomy(self):
        from shared.tenancy.defaults import get_vertical_defaults
        from shared.tenancy.schemas import IntelligenceSpec, Features, TenantProfile
        from backend.services import message_intelligence as mi

        layer = get_vertical_defaults("automotive")
        intel = IntelligenceSpec(**(layer.get("intelligence") or {}))
        feats = Features(**(layer.get("features") or {}))
        profile = TenantProfile(
            tenant_id="auto-test",
            vertical="automotive",
            features=feats,
            intelligence=intel,
        )

        with mock.patch(
            "shared.tenancy.loader.get_tenant_profile", return_value=profile
        ):
            result = mi.analyze_message(
                "My battery keeps dying and this is a serious complaint",
                tenant_id="auto-test",
                wa_id="919999000001",
                persist=False,
            )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.sentiment, "negative")
        self.assertEqual(result.message_type, "complaint")
        self.assertIn("battery", result.topics)
        self.assertFalse(result.safety_hit)

    def test_safety_brake_failure_escalates(self):
        from shared.tenancy.defaults import get_vertical_defaults
        from shared.tenancy.schemas import IntelligenceSpec, Features, TenantProfile
        from backend.services import message_intelligence as mi

        layer = get_vertical_defaults("automotive")
        profile = TenantProfile(
            tenant_id="auto-test",
            vertical="automotive",
            features=Features(**(layer.get("features") or {})),
            intelligence=IntelligenceSpec(**(layer.get("intelligence") or {})),
        )
        with mock.patch(
            "shared.tenancy.loader.get_tenant_profile", return_value=profile
        ):
            result = mi.analyze_message(
                "Help — my brakes failed on the highway, I have no brakes",
                tenant_id="auto-test",
                wa_id="919999000002",
                persist=False,
            )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.safety_hit)
        self.assertTrue(result.escalate)
        self.assertIn("braking_failure", result.safety_labels)

    def test_flags_off_returns_none(self):
        from shared.tenancy.schemas import Features, TenantProfile
        from backend.services import message_intelligence as mi

        profile = TenantProfile(
            tenant_id="plain",
            vertical="generic",
            features=Features(),  # all intelligence flags default False
        )
        with mock.patch(
            "shared.tenancy.loader.get_tenant_profile", return_value=profile
        ):
            result = mi.analyze_message(
                "battery problem complaint",
                tenant_id="plain",
                wa_id="919999000003",
                persist=False,
            )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
