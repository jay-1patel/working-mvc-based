"""Central error reporter (Phase 1): must log, persist, and never raise.

Adapted from the database branch's test_error_reporter.py to the Phase-1
signature report_error(provider, api, error, tenant_id=, request_id=, detail=).
"""

import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
for path in (BACKEND_DIR, PROJECT_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)


class ErrorReporterTests(unittest.TestCase):
    def setUp(self):
        import mongomock
        import services.error_reporter as er
        self.er = er
        self.database = mongomock.MongoClient(tz_aware=True).test_errors
        self._patch = patch.object(er, '_get_database', return_value=self.database)
        self._patch.start()


    def tearDown(self):
        self._patch.stop()


    def test_report_error_logs_api_error_tag(self):
        with self.assertLogs("error_reporter", level="ERROR") as cm:
            self.er.report_error(
                "send2",
                "POST /webhook/send",
                "boom",
                detail="body",
                http_status=502,
                tenant_id="demo",
                request_id="req_ab12cd34",
            )
        self.assertTrue(
            any("API_ERROR" in line and "send2" in line and "req_ab12cd34" in line
                for line in cm.output)
        )

    def test_report_error_persists_row(self):
        self.er.report_error(
            "api",
            "POST /classify",
            ValueError("bad json"),
            tenant_id="prestige",
            request_id="req_0000ffff",
        )
        rows = self.er.list_recent_errors(limit=10)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["provider"], "api")
        self.assertEqual(row["api"], "POST /classify")
        self.assertEqual(row["tenant_id"], "prestige")
        self.assertEqual(row["request_id"], "req_0000ffff")
        self.assertEqual(row["http_status"], 500)
        self.assertIn("bad json", row["message"])
        self.assertIn("ValueError", row["detail"])
        # get_error round-trip + provider filter
        self.assertEqual(self.er.get_error(row["id"])["id"], row["id"])
        self.assertEqual(len(self.er.list_recent_errors(provider="api")), 1)
        self.assertEqual(len(self.er.list_recent_errors(provider="send2")), 0)
        self.assertIsNone(self.er.get_error(99999))

    def test_report_error_never_raises_when_db_broken(self):
        def boom_ctx():
            raise RuntimeError("db gone")

        with patch.object(self.er, "_get_database", boom_ctx):
            with self.assertLogs("error_reporter", level="ERROR") as cm:
                # Must not raise even though persistence fails.
                self.er.report_error("api", "GET /x", "kaput", request_id="req_1")
        self.assertTrue(any("API_ERROR" in line for line in cm.output))

    def test_alerts_off_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ERROR_ALERTS_ENABLED", None)
            os.environ.pop("ALERT_WEBHOOK_URL", None)
            self.assertFalse(self.er._alerts_enabled())


    def test_credentials_are_redacted_before_persistence(self):
        self.er.report_error('send2', 'POST https://example.test/send?api_key=private',
                             'password=hunter2 Authorization: Bearer abc.secret.value',
                             detail='{"token": "private-token", "otp": "123456"}')
        row = self.er.list_recent_errors()[0]
        for secret in ('hunter2', 'abc.secret.value', 'private-token', '123456', 'api_key=private'):
            self.assertNotIn(secret, str(row))
        self.assertTrue(row['request_id'].startswith('evt_'))

    def test_filtered_search_and_pagination_reach_older_errors(self):
        for index in range(4):
            self.er.report_error('api', 'GET /catalog', f'failure {index}',
                                 tenant_id='acme', request_id=f'req_{index}', http_status=500)
        self.er.report_error('browser', 'React render', 'other tenant', tenant_id='other')
        rows = self.er.list_recent_errors(limit=2, offset=2, tenant_id='acme', http_status=500)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]['message'], 'failure 0')
        self.assertEqual(self.er.count_errors(tenant_id='acme', http_status=500), 4)
        self.assertEqual(len(self.er.list_recent_errors(search='req_1')), 1)
        self.assertEqual(self.er.list_recent_errors(search='%'), [])
        self.assertEqual(self.er.list_recent_errors(since='2999-01-01'), [])

    def test_logged_background_failure_inherits_trace_context(self):
        import logging
        from core.context import request_api_var, request_id_var, error_tenant_var
        tokens = (request_api_var.set('POST /api/tenants/acme/upload'),
                  request_id_var.set('req_shared'), error_tenant_var.set('acme'))
        handler = self.er.PersistentErrorHandler()
        log = logging.getLogger('test.background')
        log.addHandler(handler)
        try:
            try:
                raise ValueError('index rebuild failed')
            except ValueError:
                log.exception('Could not rebuild index')
            rows = self.er.list_recent_errors()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['request_id'], 'req_shared')
            self.assertEqual(rows[0]['tenant_id'], 'acme')
            self.assertIn('ValueError', rows[0]['detail'])
        finally:
            log.removeHandler(handler)
            request_api_var.reset(tokens[0]); request_id_var.reset(tokens[1]); error_tenant_var.reset(tokens[2])

    def test_provider_warning_is_visible_without_a_traceback(self):
        import logging
        log = logging.getLogger('test.provider')
        handler = self.er.PersistentErrorHandler()
        log.addHandler(handler)
        try:
            log.warning('Incoming report returned non-200: %s', 502)
            row = self.er.list_recent_errors()[0]
            self.assertEqual(row['severity'], 'warning')
            self.assertIn('502', row['message'])
        finally:
            log.removeHandler(handler)

    def test_every_failed_response_is_recorded_once_with_request_id(self):
        from fastapi import FastAPI, HTTPException
        from fastapi.exceptions import RequestValidationError
        from fastapi.responses import JSONResponse
        from fastapi.testclient import TestClient
        from starlette.exceptions import HTTPException as StarletteHTTPException
        from pydantic import BaseModel
        from core.middleware import request_id_middleware, http_exception_handler, validation_exception_handler
        app = FastAPI()
        app.middleware('http')(request_id_middleware)
        app.add_exception_handler(StarletteHTTPException, http_exception_handler)
        app.add_exception_handler(RequestValidationError, validation_exception_handler)
        @app.get('/api/tenants/acme/denied')
        def denied(): raise HTTPException(403, 'Permission denied')
        @app.get('/api/tenants/acme/crash')
        def crash(): raise RuntimeError('broken service')
        @app.get('/api/tenants/acme/provider')
        def provider(): return JSONResponse({'detail': 'unavailable'}, status_code=502)
        class Payload(BaseModel):
            quantity: int
        @app.post('/api/tenants/acme/validate')
        def validate(body: Payload): return {'ok': True}
        client = TestClient(app, raise_server_exceptions=False)
        responses = [client.get('/api/tenants/acme/denied'),
                     client.get('/api/tenants/acme/crash'),
                     client.get('/api/tenants/acme/provider'),
                     client.post('/api/tenants/acme/validate', json={'quantity': 'secret-value'})]
        rows = self.er.list_recent_errors()
        self.assertEqual(len(rows), 4)
        self.assertEqual({r['http_status'] for r in rows}, {403, 422, 500, 502})
        for response in responses:
            self.assertTrue(response.headers.get('X-Request-Id'))
            self.assertEqual(len([r for r in rows if r['request_id'] == response.headers['X-Request-Id']]), 1)
        self.assertNotIn('secret-value', str(rows))

    def test_browser_delivery_is_not_acknowledged_if_storage_fails(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from routes.auth import get_current_admin
        from routes.api_errors import router
        app = FastAPI(); app.include_router(router)
        app.dependency_overrides[get_current_admin] = lambda: {'role': 'admin', 'tenant_id': 'acme', 'username': 'storage-test'}
        with patch.object(self.er, '_persist', return_value=False):
            response = TestClient(app).post('/api/client-errors', json={'message': 'Network failure'})
        self.assertEqual(response.status_code, 503)

    def test_browser_reports_cannot_choose_another_tenant(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from routes.auth import get_current_admin
        from routes.api_errors import router
        app = FastAPI(); app.include_router(router)
        app.dependency_overrides[get_current_admin] = lambda: {'role': 'sub_admin', 'tenant_id': 'acme', 'username': 'tester'}
        response = TestClient(app).post('/api/client-errors', json={
            'message': 'Render failed', 'tenant_id': 'other', 'page': '/admin?token=private',
            'request_id': 'client_12345678-abcd',
        })
        self.assertEqual(response.status_code, 202, response.text)
        row = self.er.list_recent_errors()[0]
        self.assertEqual(row['tenant_id'], 'acme')
        self.assertEqual(row['request_id'], 'client_12345678-abcd')
        self.assertNotIn('private', row['detail'])


class ApiErrorsRouteTests(unittest.TestCase):
    def test_errors_route_requires_auth(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from routes.api_errors import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)
        res = client.post("/api/admin/errors")
        self.assertEqual(res.status_code, 401)


if __name__ == "__main__":
    unittest.main()
