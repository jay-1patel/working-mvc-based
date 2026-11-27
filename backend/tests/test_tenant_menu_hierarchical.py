import os
import sys
import unittest
from unittest.mock import patch, AsyncMock, MagicMock

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.tenancy.schemas import MenuButton


class TenantMenuHierarchicalTests(unittest.TestCase):
    def test_menu_button_accepts_new_hierarchical_fields(self):
        btn = MenuButton(
            id="temple_darshan",
            title="Temple Darshan",
            parent_id="gangasagar",
            action_type="knowledge",
            action_ref=None,
            answer=None,
            source_refs=["faq:1", "kb:2"],
        )
        self.assertEqual(btn.parent_id, "gangasagar")
        self.assertEqual(btn.action_type, "knowledge")
        self.assertEqual(btn.source_refs, ["faq:1", "kb:2"])

    def test_menu_button_defaults_are_backward_compatible(self):
        btn = MenuButton(id="services", title="Our Services")
        self.assertIsNone(btn.parent_id)
        self.assertEqual(btn.action_type, "knowledge")
        self.assertIsNone(btn.action_ref)
        self.assertIsNone(btn.answer)
        self.assertEqual(btn.source_refs, [])

    def test_menu_button_accepts_children_via_parent_id(self):
        parent = MenuButton(id="gangasagar", title="Gangasagar Mela")
        child = MenuButton(id="darshan", title="Temple Darshan", parent_id="gangasagar")
        self.assertEqual(child.parent_id, parent.id)

    def test_action_type_validation(self):
        for action in ["knowledge", "intent", "flow", "emergency", "text", "external"]:
            btn = MenuButton(id=f"test_{action}", title="Test", action_type=action)
            self.assertEqual(btn.action_type, action)

    def test_source_refs_defaults_empty(self):
        btn = MenuButton(id="test", title="Test")
        self.assertEqual(btn.source_refs, [])

    def test_answer_field_stores_static_text(self):
        btn = MenuButton(id="greeting", title="Greeting", action_type="text", answer="Welcome!")
        self.assertEqual(btn.answer, "Welcome!")
        self.assertEqual(btn.action_type, "text")


class TenantMenuFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_handle_tenant_menu_action_returns_none_for_no_nodes(self):
        from backend.services import tenant_menu_flow as flow
        with patch.object(flow, "_load_nodes", return_value=[]):
            result = await flow.handle_tenant_menu_action("wa-test", "menu", tenant_id="test")
        self.assertIsNone(result)

    async def test_handle_tenant_menu_action_renders_root(self):
        from backend.services import tenant_menu_flow as flow
        nodes = [
            {"id": "services", "title": "Services", "parent_id": None, "enabled": True, "sort_order": 0},
            {"id": "contact", "title": "Contact", "parent_id": None, "enabled": True, "sort_order": 1},
        ]
        sender = type("Sender", (), {})()
        sender.send_list_menu = AsyncMock(return_value=True)
        sender.send_button_message = AsyncMock(return_value=True)
        sender.send_text_message = AsyncMock(return_value=True)
        with (
            patch.object(flow, "_load_nodes", return_value=nodes),
            patch.object(flow, "_sender", return_value=sender),
            patch.object(flow, "_set_current_node"),
        ):
            result = await flow.handle_tenant_menu_action("wa-test", "menu", tenant_id="test")
        self.assertEqual(result["action"], "tenant_menu_root")
        sender.send_button_message.assert_awaited_once()

    async def test_handle_tenant_menu_action_renders_branch(self):
        from backend.services import tenant_menu_flow as flow
        nodes = [
            {"id": "services", "title": "Services", "parent_id": None, "enabled": True, "sort_order": 0},
            {"id": "web", "title": "Web Dev", "parent_id": "services", "enabled": True, "sort_order": 0},
            {"id": "mobile", "title": "Mobile Dev", "parent_id": "services", "enabled": True, "sort_order": 1},
        ]
        sender = type("Sender", (), {})()
        sender.send_list_menu = AsyncMock(return_value=True)
        sender.send_button_message = AsyncMock(return_value=True)
        sender.send_text_message = AsyncMock(return_value=True)
        with (
            patch.object(flow, "_load_nodes", return_value=nodes),
            patch.object(flow, "_sender", return_value=sender),
            patch.object(flow, "_set_current_node"),
        ):
            result = await flow.handle_tenant_menu_action("wa-test", "tm_services", tenant_id="test")
        self.assertEqual(result["action"], "tenant_menu_branch")
        self.assertEqual(result["node"], "services")
        sender.send_button_message.assert_awaited_once()

    async def test_handle_tenant_menu_action_handles_back(self):
        from backend.services import tenant_menu_flow as flow
        nodes = [
            {"id": "services", "title": "Services", "parent_id": None, "enabled": True, "sort_order": 0},
            {"id": "web", "title": "Web Dev", "parent_id": "services", "enabled": True, "sort_order": 0},
        ]
        sender = type("Sender", (), {})()
        sender.send_list_menu = AsyncMock(return_value=True)
        sender.send_button_message = AsyncMock(return_value=True)
        sender.send_text_message = AsyncMock(return_value=True)
        with (
            patch.object(flow, "_load_nodes", return_value=nodes),
            patch.object(flow, "_sender", return_value=sender),
            patch.object(flow, "_get_current_node", return_value="services"),
            patch.object(flow, "_set_current_node"),
        ):
            result = await flow.handle_tenant_menu_action("wa-test", "tm_back", tenant_id="test")
        self.assertEqual(result["action"], "tenant_menu_back")
        sender.send_button_message.assert_awaited_once()

    async def test_handle_tenant_menu_action_handles_main_menu(self):
        from backend.services import tenant_menu_flow as flow
        nodes = [
            {"id": "services", "title": "Services", "parent_id": None, "enabled": True, "sort_order": 0},
        ]
        sender = type("Sender", (), {})()
        sender.send_list_menu = AsyncMock(return_value=True)
        sender.send_button_message = AsyncMock(return_value=True)
        sender.send_text_message = AsyncMock(return_value=True)
        with (
            patch.object(flow, "_load_nodes", return_value=nodes),
            patch.object(flow, "_sender", return_value=sender),
            patch.object(flow, "_set_current_node"),
        ):
            result = await flow.handle_tenant_menu_action("wa-test", "main_menu", tenant_id="test")
        self.assertEqual(result["action"], "tenant_menu_root")
        sender.send_button_message.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()