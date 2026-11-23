"""Integration-style tests for multi-tenant routing (B1).

Focuses on code-paths we can validate without heavy mocking:
  - orchestrator always honors Active Test Tenant from the admin console
  - products.py delegates to central resolver chain
  - the conditional expressions used across modules
"""

import os
import sys
import unittest

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)


def _source(rel: str) -> str:
    return open(os.path.join(PROJECT_ROOT, rel), encoding="utf-8").read()


class TestOrchestratorHonorsActiveTestTenant:
    """Console Active Test Tenant must win over a poller phone-bound hint."""

    def test_allow_test_override_always_true(self):
        source = _source("backend/services/orchestrator.py")
        assert "allow_test_override=True" in source
        assert "allow_test_override=not bool(tenant_id)" not in source


class TestWebhookSetCorrectAllowOverride:
    """Verify routing/webhook uses correct conditional."""

    def test_allows_active_test_override(self):
        source = _source("backend/app/services/whatsapp/webhook.py")
        assert "allow_test_override=True" in source
        assert "allow_test_override=(tenant_id is None)" not in source


class TestProductsDelegatesToResolver:
    """products must NOT read get_active_test_tenant() directly."""

    def test_no_direct_get_active_test_call(self):
        """If this fails, products is reading the DB setting directly again."""
        source = _source("backend/db/products.py")
        # Must NOT have an import or call — a mention in a docstring is OK
        assert "from .settings import get_active_test_tenant" not in source
        assert "get_active_test_tenant()" not in source

    def test_calls_resolve_default_tenant(self):
        source = _source("backend/db/products.py")
        assert "resolve_default_tenant" in source


class TestProductIdsRespectsExplicitTenant:
    """Even simple lookups respect the passed-in tenant."""

    def test_makemytrip_resolves(self):
        from backend.db.products import _resolve_tenant_ids
        ids = _resolve_tenant_ids("makemytrip")
        assert "makemytrip" in ids
