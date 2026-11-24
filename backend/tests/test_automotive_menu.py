"""Verify the automotive WhatsApp menu has the 6 dealer rows and each routes correctly."""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.tenancy.defaults import DEFAULT_FLOWS, get_vertical_defaults  # noqa: E402
from shared.tenancy.schemas import TenantProfile  # noqa: E402

EXPECTED = [
    ("menu_models", "Our Cars"),
    ("menu_brochure", "Brochure"),
    ("menu_test_drive", "Test Drive"),
    ("menu_onroad_price", "On-Road Price"),
    ("menu_human", "Talk to Sales"),
    ("menu_customer_care", "Customer Care"),
]


def _automotive_profile(**overrides) -> TenantProfile:
    layer = get_vertical_defaults("automotive")
    data = {
        "tenant_id": "auto-menu-test",
        "vertical": "automotive",
        "display_name": "Auto Brand",
        "features": layer["features"],
        "vocabulary": layer["vocabulary"],
        "menu": layer["menu"],
        "intents": layer["intents"],
        "flows": DEFAULT_FLOWS,
        "brand": {
            "name": "MetroDrive Autos",
            "support_phone": "+91 98250 22011",
            "support_email": "service@metrodriveautos.com",
            "website": "https://metrodriveautos.example",
        },
    }
    data.update(overrides)
    return TenantProfile(**data)


class AutomotiveMenuShapeTests(unittest.TestCase):
    def test_exactly_six_default_buttons(self):
        buttons = get_vertical_defaults("automotive")["menu"]["buttons"]
        self.assertEqual([(b["id"], b["title"]) for b in buttons], EXPECTED)

    def test_visible_buttons_match_when_features_on(self):
        profile = _automotive_profile()
        visible = [(b.id, b.title) for b in profile.menu.visible_buttons(profile.features)]
        self.assertEqual(visible, EXPECTED)


class AutomotiveMenuRoutingTests(unittest.TestCase):
    def setUp(self):
        self.profile = _automotive_profile()

    def test_our_cars_is_offerings_browse(self):
        from services import offerings_flow

        btn = next(b for b in self.profile.menu.buttons if b.id == "menu_models")
        self.assertTrue(offerings_flow._is_offerings_menu_button(btn))
        with mock.patch.object(
            offerings_flow,
            "_offerings_button_keys",
            return_value={"menu_models", "our cars", "Our Cars"},
        ):
            self.assertTrue(
                offerings_flow.is_offerings_request("auto-menu-test", "Our Cars", "menu_models")
            )
            self.assertTrue(
                offerings_flow.is_offerings_request("auto-menu-test", "Our Cars")
            )

    def test_brochure_is_brochure_ask_not_offerings(self):
        from services import brochure_service, offerings_flow

        btn = next(b for b in self.profile.menu.buttons if b.id == "menu_brochure")
        self.assertFalse(offerings_flow._is_offerings_menu_button(btn))
        with mock.patch.object(
            brochure_service,
            "_brochure_button_keys",
            return_value={"menu_brochure", "brochure", "Brochure"},
        ):
            self.assertTrue(
                brochure_service.is_brochure_ask(
                    text="Brochure", button_id="menu_brochure", tenant_id="auto-menu-test"
                )
            )

    def test_book_test_drive_starts_callback_flow(self):
        from services import flow_runner

        with mock.patch.object(flow_runner, "_profile", return_value=self.profile):
            self.assertEqual(
                flow_runner.flow_for_button("wa", "menu_test_drive", tenant_id="auto-menu-test"),
                "book_callback",
            )
            self.assertEqual(
                flow_runner.flow_for_button("wa", "Test Drive", tenant_id="auto-menu-test"),
                "book_callback",
            )
            self.assertEqual(
                flow_runner.flow_for_text("wa", "book a test drive", tenant_id="auto-menu-test"),
                "book_callback",
            )

    def test_get_onroad_price_starts_quote_flow(self):
        from services import flow_runner

        with mock.patch.object(flow_runner, "_profile", return_value=self.profile):
            self.assertEqual(
                flow_runner.flow_for_button("wa", "menu_onroad_price", tenant_id="auto-menu-test"),
                "get_quote",
            )
            self.assertEqual(
                flow_runner.flow_for_button("wa", "On-Road Price", tenant_id="auto-menu-test"),
                "get_quote",
            )
            self.assertEqual(
                flow_runner.flow_for_text("wa", "get on-road price", tenant_id="auto-menu-test"),
                "get_quote",
            )

    def test_talk_to_sales_starts_human_handover(self):
        from services import flow_runner

        with mock.patch.object(flow_runner, "_profile", return_value=self.profile):
            self.assertEqual(
                flow_runner.flow_for_button("wa", "menu_human", tenant_id="auto-menu-test"),
                "human_handover",
            )
            self.assertEqual(
                flow_runner.flow_for_button("wa", "Talk to Sales", tenant_id="auto-menu-test"),
                "human_handover",
            )
            self.assertEqual(
                flow_runner.flow_for_text("wa", "talk to sales", tenant_id="auto-menu-test"),
                "human_handover",
            )

    def test_customer_care_returns_contact_block(self):
        from services import intent_answers

        with mock.patch.object(intent_answers, "_profile", return_value=self.profile):
            by_id = intent_answers.answer_for_button(
                "wa", "menu_customer_care", tenant_id="auto-menu-test"
            )
            by_title = intent_answers.answer_for_menu_title(
                "wa", "Customer Care", tenant_id="auto-menu-test"
            )
        self.assertIsNotNone(by_id)
        self.assertIn("98250 22011", by_id)
        self.assertIn("Customer care", by_id)
        self.assertEqual(by_id, by_title)

    def test_quote_feature_enabled_for_onroad_price(self):
        self.assertTrue(self.profile.feature_on("quote"))
        self.assertTrue(self.profile.feature_on("callback"))
        self.assertTrue(self.profile.feature_on("human_handover"))
        self.assertTrue(self.profile.feature_on("brochure_pdf"))
        self.assertTrue(self.profile.feature_on("offerings"))


if __name__ == "__main__":
    unittest.main()
