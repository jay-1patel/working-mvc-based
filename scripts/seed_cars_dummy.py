"""Seed visible dummy rows for tenant `c` (cars admin session)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta

DB = r"C:\Users\admin\Desktop\whatsapp-chatbot\mvc-based-code-main\faq.db"
TENANT = "c"
NOW = datetime.utcnow()


def ts(minutes_ago: int = 0) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    chats = [
        {
            "wa_id": "919512777899",
            "name": "Riya Shah",
            "handover": 1,
            "resolved_at": None,
            "state": "HUMAN_HANDOVER",
            "messages": [
                ("Hi, I need help with a test drive", "Sure — which model?", 25),
                ("City Hybrid please", "Got it. Connecting you to an agent.", 20),
                ("Is someone there?", None, 5),
            ],
        },
        {
            "wa_id": "919876543210",
            "name": "Amit Patel",
            "handover": 1,
            "resolved_at": None,
            "state": "HUMAN_HANDOVER",
            "messages": [
                ("Price of Elevate?", "Starting from 11.5L ex-showroom.", 40),
                ("Can I get a quote today?", "Yes, an agent will share it.", 15),
            ],
        },
        {
            "wa_id": "918888777666",
            "name": "Neha Joshi",
            "handover": 0,
            "resolved_at": None,
            "state": "B2C_MAIN_MENU",
            "messages": [
                ("Show service packages", "Periodic / Body / Express available.", 55),
                ("Book periodic service", "Please share preferred date.", 50),
            ],
        },
        {
            "wa_id": "917700998877",
            "name": "Kabir Mehta",
            "handover": 1,
            "resolved_at": None,
            "state": "HUMAN_HANDOVER",
            "messages": [
                ("Insurance renewal help", "Sure, sharing with an agent.", 12),
                ("Need policy soft copy", None, 8),
            ],
        },
    ]

    for chat in chats:
        wa = chat["wa_id"]
        conn.execute(
            """
            INSERT INTO user_states (
              tenant_id, wa_id, state, context_json, lang, version,
              human_handover, handover_resolved_at, status, updated_at
            ) VALUES (?, ?, ?, '{}', 'en', 1, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, wa_id) DO UPDATE SET
              state = excluded.state,
              human_handover = excluded.human_handover,
              handover_resolved_at = excluded.handover_resolved_at,
              status = excluded.status,
              updated_at = excluded.updated_at
            """,
            (
                TENANT,
                wa,
                chat["state"],
                chat["handover"],
                chat["resolved_at"],
                "human" if chat["handover"] else "bot",
                ts(1),
            ),
        )

        # Keep older real history; only wipe prior seed rows for this wa.
        conn.execute(
            "DELETE FROM chat_history WHERE tenant_id = ? AND wa_id = ? AND route = 'dummy'",
            (TENANT, wa),
        )
        for msg, resp, mins in chat["messages"]:
            conn.execute(
                """
                INSERT INTO chat_history (wa_id, sender_name, message, response, route, created_at, tenant_id)
                VALUES (?, ?, ?, ?, 'dummy', ?, ?)
                """,
                (wa, chat["name"], msg, resp, ts(mins), TENANT),
            )

        conn.execute(
            """
            INSERT INTO customers (
              tenant_id, wa_id, name, phone, email, city, state, company, language,
              message_count, first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'en', ?, ?, ?)
            ON CONFLICT(tenant_id, wa_id) DO UPDATE SET
              name = excluded.name,
              phone = excluded.phone,
              email = excluded.email,
              city = excluded.city,
              company = excluded.company,
              message_count = excluded.message_count,
              last_seen = excluded.last_seen
            """,
            (
                TENANT,
                wa,
                chat["name"],
                wa,
                f"{chat['name'].split()[0].lower()}@example.com",
                "Ahmedabad",
                "Gujarat",
                "MetroDrive lead",
                len(chat["messages"]) + 3,
                ts(120),
                ts(2),
            ),
        )

    # Assign open chats to cars agent.
    for wa in ("919512777899", "919876543210", "917700998877"):
        conn.execute(
            """
            INSERT INTO conversation_assignments (tenant_id, wa_id, agent_id, assigned_at)
            VALUES (?, ?, 'cars', ?)
            ON CONFLICT(tenant_id, wa_id) DO UPDATE SET
              agent_id = excluded.agent_id,
              assigned_at = excluded.assigned_at
            """,
            (TENANT, wa, ts(3)),
        )
    conn.execute(
        """
        INSERT INTO agent_status (agent_id, status, updated_at)
        VALUES ('cars', 'online', ?)
        ON CONFLICT(agent_id) DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at
        """,
        (ts(0),),
    )

    tickets = [
        ("TKT-DUMMY-001", "919512777899", "Service delay", "Waiting 3 days for periodic service slot", "open", "high"),
        ("TKT-DUMMY-002", "919876543210", "Wrong quote", "Quoted price does not match brochure", "in_progress", "normal"),
        ("TKT-DUMMY-003", "918888777666", "App issue", "Cannot upload RC for insurance", "resolved", "low"),
        ("TKT-DUMMY-004", "917700998877", "Insurance soft copy", "Customer needs policy PDF on WhatsApp", "open", "high"),
    ]
    for ticket_id, wa, subject, desc, status, priority in tickets:
        conn.execute(
            """
            INSERT INTO complaints (
              ticket_id, wa_id, complaint_type, description, status, created_at,
              priority, assigned_to, updated_at, subject, tenant_id
            ) VALUES (?, ?, 'Other', ?, ?, ?, ?, 'cars', ?, ?, ?)
            ON CONFLICT(ticket_id) DO UPDATE SET
              status = excluded.status,
              description = excluded.description,
              priority = excluded.priority,
              updated_at = excluded.updated_at,
              tenant_id = excluded.tenant_id,
              subject = excluded.subject
            """,
            (ticket_id, wa, desc, status, ts(30), priority, ts(10), subject, TENANT),
        )

    orders = [
        ("ORD-DUMMY-1001", "919512777899", "Riya Shah", 125000.0, "placed", "pending"),
        ("ORD-DUMMY-1002", "919876543210", "Amit Patel", 89999.0, "confirmed", "paid"),
        ("ORD-DUMMY-1003", "918888777666", "Neha Joshi", 4500.0, "delivered", "paid"),
        ("ORD-DUMMY-1004", "917700998877", "Kabir Mehta", 22000.0, "processing", "paid"),
    ]
    for order_number, wa, name, total, status, pay in orders:
        items = json.dumps([{"name": "Dummy accessory / service", "qty": 1, "price": total}])
        conn.execute(
            """
            INSERT INTO orders (
              order_number, wa_id, items, total_amount, status, payment_status,
              created_at, customer_name, customer_mobile, order_type, tenant_id, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'product', ?, 'dummy')
            ON CONFLICT(order_number) DO UPDATE SET
              status = excluded.status,
              payment_status = excluded.payment_status,
              total_amount = excluded.total_amount,
              tenant_id = excluded.tenant_id
            """,
            (order_number, wa, items, total, status, pay, ts(45), name, wa, TENANT),
        )

    conn.execute(
        """
        INSERT INTO distributors (
          wa_id, tenant_id, name, phone, email, region, tier, city, notes, created_at, updated_at
        ) VALUES (?, ?, 'Dummy Motors LLP', ?, 'partner@example.com', 'West', 'gold', 'Ahmedabad', 'Seed partner', ?, ?)
        ON CONFLICT(wa_id) DO UPDATE SET
          name = excluded.name,
          tenant_id = excluded.tenant_id,
          notes = excluded.notes,
          updated_at = excluded.updated_at
        """,
        ("917700112233", TENANT, "917700112233", ts(90), ts(5)),
    )
    conn.execute(
        """
        INSERT INTO distributors (
          wa_id, tenant_id, name, phone, email, region, tier, city, notes, created_at, updated_at
        ) VALUES (?, ?, 'City Auto Hub', ?, 'hub@example.com', 'West', 'silver', 'Surat', 'Seed partner 2', ?, ?)
        ON CONFLICT(wa_id) DO UPDATE SET
          name = excluded.name,
          tenant_id = excluded.tenant_id,
          notes = excluded.notes,
          updated_at = excluded.updated_at
        """,
        ("917711223344", TENANT, "917711223344", ts(80), ts(6)),
    )

    callbacks = [
        ("cb-dummy-1", "919512777899", "scheduled", 60, 75),
        ("cb-dummy-2", "919876543210", "completed", 180, 195),
        ("cb-dummy-3", "917700998877", "pending", 30, 45),
    ]
    for cb_id, wa, status, start_mins, end_mins in callbacks:
        data = json.dumps({"reason": "dummy seed callback", "preferred_slot": "morning"})
        conn.execute(
            """
            INSERT INTO callbacks (
              id, tenant_id, wa_id, data, status, scheduled_start_time, scheduled_end_time,
              meet_link, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              status = excluded.status,
              scheduled_start_time = excluded.scheduled_start_time,
              scheduled_end_time = excluded.scheduled_end_time,
              updated_at = excluded.updated_at
            """,
            (
                cb_id,
                TENANT,
                wa,
                data,
                status,
                ts(-start_mins) if status == "scheduled" else ts(start_mins),
                ts(-end_mins) if status == "scheduled" else ts(end_mins),
                f"https://meet.example.com/{cb_id}",
                ts(100),
                ts(4),
            ),
        )

    # Extra standalone customer with no open handover (directory coverage).
    conn.execute(
        """
        INSERT INTO customers (
          tenant_id, wa_id, name, phone, email, city, state, company, language,
          message_count, first_seen, last_seen
        ) VALUES (?, '919900112233', 'Sana Khan', '919900112233', 'sana@example.com',
                  'Vadodara', 'Gujarat', 'Walk-in lead', 'en', 1, ?, ?)
        ON CONFLICT(tenant_id, wa_id) DO UPDATE SET
          name = excluded.name,
          last_seen = excluded.last_seen
        """,
        (TENANT, ts(200), ts(20)),
    )

    leads = [
        ("919512777899", "Riya Shah", "new", "whatsapp", "test_drive"),
        ("919876543210", "Amit Patel", "contacted", "whatsapp", "quote"),
        ("918888777666", "Neha Joshi", "qualified", "website", "service"),
        ("919900112233", "Sana Khan", "new", "walk_in", "insurance"),
    ]
    # Idempotent: wipe prior dummy leads for tenant then reinsert.
    conn.execute("DELETE FROM leads WHERE tenant_id = ? AND source LIKE 'dummy%'", (TENANT,))
    for wa, name, status, source, flow in leads:
        conn.execute(
            """
            INSERT INTO leads (
              tenant_id, wa_id, user_name, phone, email, collected, status, assignee, source, flow, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, '{}', ?, 'cars', ?, ?, ?, ?)
            """,
            (
                TENANT,
                wa,
                name,
                wa,
                f"{name.split()[0].lower()}@example.com",
                status,
                f"dummy:{source}",
                flow,
                ts(70),
                ts(15),
            ),
        )

    conn.execute("DELETE FROM unanswered_queries WHERE tenant_id = ? AND reason = 'dummy'", (TENANT,))
    for wa, query, conf in [
        ("919512777899", "Do you sell electric scooters?", 0.22),
        ("919876543210", "Can I trade in a Toyota?", 0.31),
        ("917700998877", "Night service available?", 0.18),
    ]:
        conn.execute(
            """
            INSERT INTO unanswered_queries (
              tenant_id, wa_id, query, reason, confidence_score, created_at, resolved
            ) VALUES (?, ?, ?, 'dummy', ?, ?, 0)
            """,
            (TENANT, wa, query, conf, ts(35)),
        )

    conn.execute(
        """
        INSERT INTO segments (tenant_id, name, audience_type, criteria_json, created_at, updated_at)
        VALUES (?, 'Dummy West Gold Partners', 'distributors', '{"tier":["gold"],"region":["West"]}', ?, ?)
        ON CONFLICT(tenant_id, name) DO UPDATE SET
          criteria_json = excluded.criteria_json,
          updated_at = excluded.updated_at
        """,
        (TENANT, ts(100), ts(10)),
    )
    conn.execute(
        """
        INSERT INTO segments (tenant_id, name, audience_type, criteria_json, created_at, updated_at)
        VALUES (?, 'Dummy Hot Leads', 'customers', '{"city":["Ahmedabad","Surat"]}', ?, ?)
        ON CONFLICT(tenant_id, name) DO UPDATE SET
          criteria_json = excluded.criteria_json,
          updated_at = excluded.updated_at
        """,
        (TENANT, ts(90), ts(9)),
    )

    # Campaigns have no natural unique key besides id — wipe prior dummy names then insert.
    conn.execute(
        "DELETE FROM campaigns WHERE tenant_id = ? AND name LIKE 'Dummy %'",
        (TENANT,),
    )
    conn.execute(
        """
        INSERT INTO campaigns (
          tenant_id, name, status, campaign_type, audience_type, message_template,
          target_count, sent, delivered, read_count, replied, failed, created_at, updated_at
        ) VALUES
          (?, 'Dummy Festive Offer', 'draft', 'promotional', 'all',
           'Hi {{name}}, festive offers on Elevate & City are live.', 120, 0, 0, 0, 0, 0, ?, ?),
          (?, 'Dummy Service Reminder', 'completed', 'transactional', 'customers',
           'Hi {{name}}, your service is due this week.', 85, 80, 76, 40, 12, 4, ?, ?)
        """,
        (TENANT, ts(60), ts(60), TENANT, ts(200), ts(150)),
    )

    # Ensure at least one active product for tenant c if products are tenant-scoped.
    product_cols = {r[1] for r in conn.execute("PRAGMA table_info(products)")}
    if "tenant_id" in product_cols:
        existing = conn.execute(
            "SELECT COUNT(*) FROM products WHERE tenant_id = ?", (TENANT,)
        ).fetchone()[0]
        if existing == 0:
            conn.execute(
                """
                INSERT INTO products (
                  tenant_id, name, slug, category, description, short_description,
                  price, mrp, unit, is_active, sort_order
                ) VALUES
                  (?, 'Dummy City Hybrid', 'dummy-city-hybrid', 'cars',
                   'Seeded midsize sedan', 'City Hybrid demo', '1499000', '1599000', 'unit', 1, 1),
                  (?, 'Dummy Elevate', 'dummy-elevate', 'cars',
                   'Seeded compact SUV', 'Elevate demo', '1199000', '1299000', 'unit', 1, 2)
                """,
                (TENANT, TENANT),
            )

    conn.commit()

    open_inbox = conn.execute(
        """
        SELECT us.wa_id, us.human_handover, us.handover_resolved_at,
               (SELECT COUNT(*) FROM chat_history ch
                WHERE ch.tenant_id = us.tenant_id AND ch.wa_id = us.wa_id) AS msgs
        FROM user_states us
        WHERE us.tenant_id = ?
          AND us.human_handover = 1
          AND us.handover_resolved_at IS NULL
        """,
        (TENANT,),
    ).fetchall()
    print("seeded tenant", TENANT)
    print("open handovers", [dict(r) for r in open_inbox])
    for label, sql in [
        ("customers", "SELECT COUNT(*) FROM customers WHERE tenant_id=?"),
        ("complaints", "SELECT COUNT(*) FROM complaints WHERE tenant_id=?"),
        ("orders", "SELECT COUNT(*) FROM orders WHERE tenant_id=?"),
        ("distributors", "SELECT COUNT(*) FROM distributors WHERE tenant_id=?"),
        ("callbacks", "SELECT COUNT(*) FROM callbacks WHERE tenant_id=?"),
        ("assignments", "SELECT COUNT(*) FROM conversation_assignments WHERE tenant_id=?"),
        ("leads", "SELECT COUNT(*) FROM leads WHERE tenant_id=?"),
        ("unanswered", "SELECT COUNT(*) FROM unanswered_queries WHERE tenant_id=?"),
        ("segments", "SELECT COUNT(*) FROM segments WHERE tenant_id=?"),
        ("campaigns", "SELECT COUNT(*) FROM campaigns WHERE tenant_id=?"),
        ("products", "SELECT COUNT(*) FROM products WHERE tenant_id=?"),
    ]:
        print(label, conn.execute(sql, (TENANT,)).fetchone()[0])
    conn.close()


if __name__ == "__main__":
    main()
