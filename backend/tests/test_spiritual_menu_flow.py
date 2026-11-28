import unittest
import sys
import types
from unittest.mock import AsyncMock, patch

from backend.services import spiritual_menu_flow as flow


class SpiritualMenuTitleRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_temple_topics_only_appear_for_gangasagar_and_rath_yatra(self):
        for event_id, should_include in (
            ("menu_kumbh", False),
            ("menu_gangasagar", True),
            ("menu_rath_yatra", True),
        ):
            with self.subTest(event_id=event_id):
                sender = type("Sender", (), {})()
                sender.send_list_menu = AsyncMock(return_value=True)
                with (
                    patch.object(flow, "_sender", return_value=sender),
                    patch.object(flow, "_set_active_event"),
                ):
                    await flow._send_event_topics("wa-test", event_id, tenant_id="spiritual")

                sections = sender.send_list_menu.await_args.args[4]
                row_ids = {row["id"] for section in sections for row in section["rows"]}
                event_slug = flow.EVENTS[event_id]["slug"]
                self.assertEqual(f"st_{event_slug}_temple_darshan" in row_ids, should_include)
                self.assertEqual(f"st_{event_slug}_temple_arti" in row_ids, should_include)
                if event_id == "menu_rath_yatra":
                    self.assertIn("st_rath_yatra_temple_darshan", row_ids)
                    self.assertIn("st_rath_yatra_temple_arti", row_ids)
                    self.assertNotIn("st_rath_yatra_bathing", row_ids)

    async def test_visible_topic_title_routes_to_event_answer(self):
        sender = type("Sender", (), {})()
        sender.send_text_message = AsyncMock(return_value=True)
        sender.send_button_message = AsyncMock(return_value=True)
        synthesize = AsyncMock(return_value="Grounded Gangasagar travel answer from tenant KB.")
        fake_faq_service = types.ModuleType("faq.service")
        fake_faq_service.synthesize_intent_answer = synthesize
        with (
            patch.object(flow, "is_spiritual_tenant", return_value=True),
            patch.object(flow, "_get_pending", return_value={}),
            patch.object(flow, "_get_active_event", return_value="gangasagar"),
            patch.object(flow, "_sender", return_value=sender),
            patch.dict(sys.modules, {"faq.service": fake_faq_service}),
        ):
            result = await flow.handle_spiritual_menu_action(
                "wa-test", "Travel Assistance", tenant_id="spiritual",
            )

        self.assertEqual(result["action"], "spiritual_event_topic")
        self.assertEqual(result["event"], "gangasagar")
        self.assertEqual(result["topic"], "travel")
        sender.send_text_message.assert_awaited_once()
        self.assertEqual(
            sender.send_text_message.await_args.args[1],
            "Grounded Gangasagar travel answer from tenant KB.",
        )
        sender.send_button_message.assert_awaited_once_with(
            "wa-test",
            "Choose what you'd like to do next:",
            [
                {"id": "st_gangasagar_bathing", "title": "Holy Bathing Info"},
                {"id": "st_gangasagar_stay", "title": "Accommodation"},
                {"id": "menu_gangasagar", "title": "Event Menu"},
            ],
            tenant_id="spiritual",
        )
        synthesize.assert_awaited_once_with(
            raw_content="",
            intent_name="Gangasagar Mela — Travel Assistance",
            user_query="Gangasagar Mela how to reach travel assistance timings transport ferry cruise train",
            tenant_id="spiritual",
        )

    async def test_temple_arti_answer_suggests_related_topic_buttons(self):
        sender = type("Sender", (), {})()
        sender.send_text_message = AsyncMock(return_value=True)
        sender.send_button_message = AsyncMock(return_value=True)
        synthesize = AsyncMock(return_value="Grounded Gangasagar darshan answer from tenant KB.")
        fake_faq_service = types.ModuleType("faq.service")
        fake_faq_service.synthesize_intent_answer = synthesize
        with (
            patch.object(flow, "is_spiritual_tenant", return_value=True),
            patch.object(flow, "_get_pending", return_value={}),
            patch.object(flow, "_get_active_event", return_value="gangasagar"),
            patch.object(flow, "_sender", return_value=sender),
            patch.dict(sys.modules, {"faq.service": fake_faq_service}),
        ):
            result = await flow.handle_spiritual_menu_action(
                "wa-test", "Temple Arti", tenant_id="spiritual",
            )

        self.assertEqual(result["action"], "spiritual_event_topic")
        self.assertEqual(result["topic"], "temple_arti")
        sender.send_button_message.assert_awaited_once()
        buttons = sender.send_button_message.await_args.args[2]
        self.assertEqual(
            buttons,
            [
                {"id": "st_gangasagar_temple_darshan", "title": "Temple Darshan"},
                {"id": "st_gangasagar_bathing", "title": "Holy Bathing Info"},
                {"id": "menu_gangasagar", "title": "Event Menu"},
            ],
        )

    async def test_rath_yatra_bathing_title_is_not_routed(self):
        self.assertIsNone(flow._parse_event_topic_title("Holy Bathing Info", "rath_yatra"))

    async def test_visible_emergency_title_opens_emergency_menu(self):
        sender = type("Sender", (), {})()
        sender.send_list_menu = AsyncMock(return_value=True)
        with (
            patch.object(flow, "is_spiritual_tenant", return_value=True),
            patch.object(flow, "_get_pending", return_value={}),
            patch.object(flow, "_get_active_event", return_value="kumbh"),
            patch.object(flow, "_sender", return_value=sender),
        ):
            result = await flow.handle_spiritual_menu_action(
                "wa-test", "Emergency Support", tenant_id="spiritual",
            )

        self.assertEqual(result["action"], "spiritual_emergency_menu")
        sender.send_list_menu.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
