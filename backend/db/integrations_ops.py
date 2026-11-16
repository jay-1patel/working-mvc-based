"""Tenant integrations, payments, shipments — dual SQLite / Mongo."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from .core import get_db_context, use_mongodb


def _parse_credentials(row: dict) -> dict:
    try:
        return json.loads(row.get("credentials_json") or "{}")
    except Exception:
        return {}


def get_tenant_integration(tenant_id: str, provider: str) -> Optional[dict]:
    prov = provider.lower().strip()
    if use_mongodb():
        from .mongo import Repository

        row = Repository("tenant_integrations").find_one(
            {"tenant_id": tenant_id, "provider": prov},
        )
        if not row:
            row = Repository("tenant_integrations").find_one(
                {"tenant_id": tenant_id, "provider": {"$regex": f"^{prov}$", "$options": "i"}},
            )
        if not row:
            return None
        d = dict(row)
        d["credentials"] = row.get("credentials") if isinstance(row.get("credentials"), dict) else _parse_credentials(d)
        return d

    with get_db_context() as conn:
        row = conn.execute(
            """SELECT * FROM tenant_integrations WHERE tenant_id = ? AND LOWER(provider) = LOWER(?)""",
            (tenant_id, prov),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["credentials"] = _parse_credentials(d)
        return d


def list_tenant_integrations(tenant_id: str) -> list[dict]:
    if use_mongodb():
        from .mongo import Repository

        return [dict(r) for r in Repository("tenant_integrations").find(
            {"tenant_id": tenant_id}, sort=[("provider", 1)],
        )]

    with get_db_context() as conn:
        rows = conn.execute(
            """SELECT id, tenant_id, provider, api_type, environment, is_active,
                      credentials_json, webhook_secret, status, last_tested_at, last_error,
                      created_at, updated_at
               FROM tenant_integrations WHERE tenant_id = ? ORDER BY provider ASC""",
            (tenant_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def upsert_tenant_integration(
    tenant_id: str,
    provider: str,
    *,
    api_type: str,
    environment: str,
    is_active: bool,
    credentials_json: str,
    webhook_secret: str,
) -> None:
    prov = provider.lower().strip()
    now = datetime.now(timezone.utc).isoformat()
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("tenant_integrations")
        existing = repo.find_one({"tenant_id": tenant_id, "provider": prov})
        payload = {
            "tenant_id": tenant_id,
            "provider": prov,
            "api_type": api_type,
            "environment": environment,
            "is_active": 1 if is_active else 0,
            "credentials_json": credentials_json,
            "credentials": json.loads(credentials_json or "{}"),
            "webhook_secret": webhook_secret,
            "status": "configured",
            "updated_at": now,
        }
        if existing:
            repo.update({"id": existing["id"]}, payload)
        else:
            payload["created_at"] = now
            repo.insert(payload)
        return

    with get_db_context() as conn:
        conn.execute(
            """INSERT INTO tenant_integrations
               (tenant_id, provider, api_type, environment, is_active, credentials_json, webhook_secret, status, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'configured', ?)
               ON CONFLICT(tenant_id, provider) DO UPDATE SET
                   api_type = excluded.api_type,
                   environment = excluded.environment,
                   is_active = excluded.is_active,
                   credentials_json = excluded.credentials_json,
                   webhook_secret = excluded.webhook_secret,
                   status = 'configured',
                   updated_at = excluded.updated_at""",
            (
                tenant_id,
                prov,
                api_type,
                environment,
                1 if is_active else 0,
                credentials_json,
                webhook_secret,
                now,
            ),
        )


def update_integration_test_status(
    tenant_id: str,
    provider: str,
    *,
    status: str,
    last_error: str,
) -> None:
    prov = provider.lower().strip()
    now = datetime.now(timezone.utc).isoformat()
    if use_mongodb():
        from .mongo import Repository

        repo = Repository("tenant_integrations")
        row = repo.find_one({"tenant_id": tenant_id, "provider": prov})
        if row:
            repo.update({"id": row["id"]}, {
                "status": status,
                "last_tested_at": now,
                "last_error": last_error,
                "updated_at": now,
            })
        return

    with get_db_context() as conn:
        conn.execute(
            """UPDATE tenant_integrations
               SET status = ?, last_tested_at = ?, last_error = ?, updated_at = ?
               WHERE tenant_id = ? AND LOWER(provider) = LOWER(?)""",
            (status, now, last_error, now, tenant_id, prov),
        )


def pick_active_integration(tenant_id: str, api_type: str) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository

        rows = Repository("tenant_integrations").find(
            {"tenant_id": tenant_id, "api_type": api_type, "is_active": {"$in": [1, True]}},
            sort=[("status", 1)],
        )
        if not rows:
            rows = [r for r in Repository("tenant_integrations").find_all({"tenant_id": tenant_id, "api_type": api_type}) if r.get("is_active")]
        if not rows:
            return None
        rows.sort(key=lambda r: 0 if r.get("status") == "verified" else 1)
        row = rows[0]
        d = dict(row)
        d["credentials"] = row.get("credentials") if isinstance(row.get("credentials"), dict) else _parse_credentials(d)
        return d

    with get_db_context() as conn:
        row = conn.execute(
            """SELECT provider, credentials_json FROM tenant_integrations
               WHERE tenant_id = ? AND api_type = ? AND is_active = 1
               ORDER BY CASE WHEN status = 'verified' THEN 1 ELSE 2 END ASC LIMIT 1""",
            (tenant_id, api_type),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["credentials"] = _parse_credentials(d)
        return d


def insert_tenant_payment(row: dict) -> None:
    if use_mongodb():
        from .mongo import Repository

        Repository("tenant_payments").insert(row)
        return
    with get_db_context() as conn:
        conn.execute(
            """INSERT INTO tenant_payments
               (tenant_id, order_id, provider, amount, currency, payment_id, session_id, payment_url, status, raw_response)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'created', ?)""",
            (
                row["tenant_id"],
                row["order_id"],
                row["provider"],
                row["amount"],
                row["currency"],
                row["payment_id"],
                row.get("session_id"),
                row["payment_url"],
                row["raw_response"],
            ),
        )


def insert_tenant_shipment(row: dict) -> None:
    if use_mongodb():
        from .mongo import Repository

        Repository("tenant_shipments").insert(row)
        return
    with get_db_context() as conn:
        conn.execute(
            """INSERT INTO tenant_shipments
               (tenant_id, order_id, provider, awb_number, tracking_url, status, origin_pincode, destination_pincode, customer_name, customer_phone, raw_response)
               VALUES (?, ?, ?, ?, ?, 'booked', ?, ?, ?, ?, ?)""",
            (
                row["tenant_id"],
                row["order_id"],
                row["provider"],
                row["awb_number"],
                row["tracking_url"],
                row["origin_pincode"],
                row["destination_pincode"],
                row["customer_name"],
                row["customer_phone"],
                row["raw_response"],
            ),
        )


def get_tenant_shipment(tenant_id: str, awb: str) -> Optional[dict]:
    if use_mongodb():
        from .mongo import Repository

        row = Repository("tenant_shipments").find_one({"tenant_id": tenant_id, "awb_number": awb})
        return dict(row) if row else None
    with get_db_context() as conn:
        row = conn.execute(
            """SELECT * FROM tenant_shipments WHERE tenant_id = ? AND awb_number = ?""",
            (tenant_id, awb),
        ).fetchone()
        return dict(row) if row else None