"""Contract tests for the consolidated dashboard API."""

import unittest
from unittest.mock import patch

from routes import admin as admin_routes


class DashboardOverviewTests(unittest.TestCase):
    def test_only_consolidated_dashboard_route_is_registered(self):
        methods_by_path = {
            route.path: set(route.methods or set())
            for route in admin_routes.router.routes
        }
        self.assertEqual(
            methods_by_path.get("/api/admin/dashboard/overview"), {"POST"}
        )
        for old_path in (
            "/api/admin/dashboard/stats",
            "/api/admin/analytics/overview",
            "/api/admin/analytics/response-time",
            "/api/admin/analytics/frequent-questions",
        ):
            self.assertNotIn(old_path, methods_by_path)

    @patch.object(admin_routes, "analytics_frequent_questions")
    @patch.object(admin_routes, "analytics_response_time")
    @patch.object(admin_routes, "analytics_overview")
    @patch.object(admin_routes, "load_dashboard_stats")
    @patch.object(admin_routes, "use_mongodb", return_value=False)
    @patch.object(admin_routes, "list_products")
    @patch.object(admin_routes, "list_admin_files")
    def test_tenant_admin_receives_one_merged_tenant_scoped_response(
        self,
        list_files,
        list_products,
        _use_mongodb,
        load_stats,
        analytics_overview,
        response_time,
        frequent_questions,
    ):
        list_files.return_value = [
            {"module": "kb"},
            {"module": "faq"},
        ]
        list_products.return_value = [{"id": 1}]
        load_stats.return_value = {"total_orders": 2, "top_questions": []}
        analytics_overview.return_value = {
            "days": 7,
            "total_messages": 12,
            "route_breakdown": [],
        }
        response_time.return_value = {"days": 7, "data": [{"date": "2026-11-17"}]}
        frequent_questions.return_value = {
            "days": 7,
            "total_unique": 1,
            "questions": [{"query": "Hello", "count": 2}],
        }

        result = admin_routes.dashboard_overview(
            days=7,
            limit=8,
            current_admin={"role": "admin", "tenant_id": "c"},
        )

        list_files.assert_called_once_with(tenant_id="c")
        list_products.assert_called_once_with(limit=10000, tenant_id="c")
        load_stats.assert_called_once_with(
            kb_count=1,
            faq_count=1,
            product_count=1,
            tenant_id="c",
        )
        analytics_overview.assert_called_once_with(days=7, tenant_id="c")
        response_time.assert_called_once_with(days=7, tenant_id="c")
        frequent_questions.assert_called_once_with(days=7, limit=8, tenant_id="c")
        self.assertEqual(result["total_orders"], 2)
        self.assertEqual(result["total_messages"], 12)
        self.assertEqual(result["response_time"], [{"date": "2026-11-17"}])
        self.assertEqual(result["frequent_questions"], [{"query": "Hello", "count": 2}])
        self.assertEqual(result["total_unique_questions"], 1)


if __name__ == "__main__":
    unittest.main()
