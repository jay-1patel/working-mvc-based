"""Contract checks for the panel's flat body-only POST API."""

import unittest
from collections import Counter

from routes import conversations, crawl, onboarding_kits, tenant_files, tenant_operations, tenants
from routes.auth import BODY_TENANT_POST_PATHS, READ_ONLY_POST_PATHS, is_tenant_data_write


EXPECTED = {
    "/api/admin/tenants/conversations/detail",
    "/api/admin/tenants/chat/thread",
    "/api/admin/tenants/chat-history",
    "/api/admin/tenants/inbox",
    "/api/admin/tenants/inbox/handover",
    "/api/admin/tenants/inbox/assign",
    "/api/admin/tenants/inbox/resolve",
    "/api/admin/tenants/inbox/reply",
    "/api/admin/tenants/inbox/attach",
    "/api/admin/tenants/agents",
    "/api/admin/tenants/complaints",
    "/api/admin/tenants/complaints/update",
    "/api/admin/tenants/complaints/reply",
    "/api/admin/tenants/complaints/delete",
    "/api/admin/tenants/customers",
    "/api/admin/tenants/customers/export",
    "/api/admin/tenants/resolved",
    "/api/admin/tenants/crawl",
    "/api/admin/tenants/crawl-runs",
    "/api/admin/tenants/crawl-runs/staged",
    "/api/admin/tenants/crawl-runs/export",
    "/api/admin/tenants/crawl-runs/approve",
    "/api/admin/tenants/crawl-runs/reject",
    "/api/admin/tenants/files",
    "/api/admin/tenants/files/upload",
    "/api/admin/tenants/files/bifurcate-existing",
    "/api/admin/tenants/files/preview",
    "/api/admin/tenants/files/download",
    "/api/admin/tenants/files/delete",
    "/api/admin/tenants/knowledge-gaps",
    "/api/admin/tenants/knowledge-gaps/resolve",
    "/api/admin/tenants/knowledge-gaps/create-faq",
    "/api/admin/onboarding-kits/list",
}


class PanelBodyPostContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        routers = (
            conversations.flat_router,
            tenant_operations.flat_router,
            tenant_files.flat_router,
            tenants.router,
            crawl.router,
            onboarding_kits.router,
        )
        cls.routes = [route for router in routers for route in router.routes]

    def test_all_32_routes_are_registered_once_as_post(self):
        registrations = [
            (method, route.path)
            for route in self.routes
            for method in (route.methods or set())
            if route.path in EXPECTED
        ]
        # /api/admin/onboarding-kits/list is the extra flat POST beyond the
        # original 32 tenant-body routes.
        self.assertEqual(len(EXPECTED), 33)
        self.assertEqual({path for _, path in registrations}, EXPECTED)
        self.assertTrue(all(method == "POST" for method, _ in registrations))
        self.assertFalse([item for item, count in Counter(registrations).items() if count > 1])

    def test_every_tenant_post_uses_session_tenant_context(self):
        self.assertEqual(BODY_TENANT_POST_PATHS, EXPECTED - {"/api/admin/onboarding-kits/list"})

    def test_flat_request_models_have_no_tenant_id(self):
        models = (
            conversations.ConversationDetailRequest(wa_id="w"),
            conversations.InboxListRequest(),
            conversations.InboxResolveRequest(wa_id="w"),
            tenant_operations.CustomersListRequest(),
            tenant_operations.CustomersExportRequest(),
            crawl.CrawlExportRequest(run_id=1),
            tenant_files.FilesBifurcateRequest(),
            tenant_files.KnowledgeGapsRequest(),
            tenants.ResolvedProfileRequest(),
        )
        for model in models:
            data = model.model_dump() if hasattr(model, "model_dump") else model.dict()
            self.assertNotIn("tenant_id", data)

    def test_read_posts_are_not_classified_as_mutations(self):
        for path in READ_ONLY_POST_PATHS:
            self.assertFalse(is_tenant_data_write("POST", path), path)
        self.assertTrue(is_tenant_data_write("POST", "/api/admin/tenants/inbox/reply"))
        self.assertTrue(is_tenant_data_write("POST", "/api/admin/tenants/files/delete"))

    def test_documented_defaults(self):
        self.assertEqual(conversations.ConversationDetailRequest(wa_id="w").limit, 300)
        self.assertFalse(conversations.InboxListRequest().include_resolved)
        self.assertTrue(conversations.InboxResolveRequest(wa_id="w").reply)
        self.assertEqual(tenant_operations.CustomersListRequest().q, "")
        self.assertEqual(tenant_operations.CustomersListRequest().limit, 200)
        self.assertEqual(tenant_operations.CustomersExportRequest().format, "csv")
        self.assertEqual(crawl.CrawlExportRequest(run_id=1).format, "json")
        self.assertFalse(tenant_files.FilesBifurcateRequest().auto_publish)
        self.assertFalse(tenant_files.KnowledgeGapsRequest().resolved)
        self.assertEqual(tenant_files.KnowledgeGapsRequest().limit, 50)
        kit_body = onboarding_kits.OnboardingKitsListRequest()
        self.assertEqual(kit_body.model_dump() if hasattr(kit_body, "model_dump") else kit_body.dict(), {})


if __name__ == "__main__":
    unittest.main()
