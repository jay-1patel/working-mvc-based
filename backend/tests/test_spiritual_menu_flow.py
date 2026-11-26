import unittest
from unittest.mock import AsyncMock, patch

from backend.services import spiritual_menu_flow as flow


class SpiritualMenuTitleRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_visible_topic_title_routes_to_event_answer(self):
        sender = type("Sender", (), {})()
        sender.send_button_message = AsyncMock(return_value=True)
        with (
            patch.object(flow, "is_spiritual_tenant", return_value=True),
            patch.object(flow, "_get_pending", return_value={}),
            patch.object(flow, "_get_active_event", return_value="gangasagar"),
            patch.object(flow, "_sender", return_value=sender),
        ):
            result = await flow.handle_spiritual_menu_action(
                "wa-test", "Travel Assistance", tenant_id="spiritual",
            )

        self.assertEqual(result["action"], "spiritual_event_topic")
        self.assertEqual(result["event"], "gangasagar")
        self.assertEqual(result["topic"], "travel")
        sender.send_button_message.assert_awaited_once()

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
