"""Restore visible demo chats for the ``cars`` admin in MongoDB.

The script preserves real chat history. It only replaces rows previously
created by this script (``route=dummy_restore``), reopens the four demo
conversation states, and refreshes their inbox timestamps.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

# Importing routing.config loads backend/routing/.env.
import routing.config  # noqa: F401, E402
from db.mongo import Repository, get_database  # noqa: E402


TENANT_ID = "c"
AGENT_ID = "cars"
ROUTE = "dummy_restore"

CHATS = (
    {
        "wa_id": "919512777899",
        "name": "Riya Shah",
        "human_handover": 1,
        "messages": (
            ("Hi, I need help booking a test drive.", "Sure - which model would you like to test drive?"),
            ("City Hybrid, please.", "I am connecting you with our sales team."),
            ("Is an agent available now?", ""),
        ),
    },
    {
        "wa_id": "919876543210",
        "name": "Amit Patel",
        "human_handover": 1,
        "messages": (
            ("What is the current price of the Elevate?", "It starts at approximately INR 11.5 lakh ex-showroom."),
            ("Please send me a quotation today.", ""),
        ),
    },
    {
        "wa_id": "918888777666",
        "name": "Neha Joshi",
        "human_handover": 0,
        "messages": (
            ("Show me the available service packages.", "Periodic, body repair, and express service are available."),
            ("I want to book periodic service.", "Please share your preferred date."),
        ),
    },
    {
        "wa_id": "917700998877",
        "name": "Kabir Mehta",
        "human_handover": 1,
        "messages": (
            ("I need help with my insurance renewal.", "I am connecting you with an agent."),
            ("I also need a soft copy of the policy.", ""),
        ),
    },
)


def main() -> None:
    db = get_database()
    admin = db.admins.find_one({"username": AGENT_ID}, {"tenant_id": 1})
    if not admin or admin.get("tenant_id") != TENANT_ID:
        raise RuntimeError("cars admin is not assigned to tenant c")

    now = datetime.now(timezone.utc)
    history = Repository("chat_history", database=db)
    restored_messages = 0

    for chat_index, chat in enumerate(CHATS):
        wa_id = chat["wa_id"]
        human_handover = chat["human_handover"]

        # Idempotent cleanup: never touch real or older seed history.
        db.chat_history.delete_many(
            {"tenant_id": TENANT_ID, "wa_id": wa_id, "route": ROUTE}
        )

        db.user_states.update_one(
            {"tenant_id": TENANT_ID, "wa_id": wa_id},
            {
                "$set": {
                    "state": "HUMAN_HANDOVER" if human_handover else "B2C_MAIN_MENU",
                    "human_handover": human_handover,
                    "handover_resolved_at": None,
                    "status": "human" if human_handover else "bot",
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "context_json": {},
                    "lang": "en",
                    "version": 1,
                },
            },
            upsert=True,
        )

        for message_index, (message, response) in enumerate(chat["messages"]):
            minutes_ago = (len(CHATS) - chat_index) * 3 + len(chat["messages"]) - message_index
            history.insert(
                {
                    "wa_id": wa_id,
                    "sender_name": chat["name"],
                    "message": message,
                    "response": response,
                    "route": ROUTE,
                    "created_at": now - timedelta(minutes=minutes_ago),
                    "tenant_id": TENANT_ID,
                }
            )
            restored_messages += 1

        if human_handover:
            db.conversation_assignments.update_one(
                {"tenant_id": TENANT_ID, "wa_id": wa_id},
                {
                    "$set": {"agent_id": AGENT_ID, "assigned_at": now},
                    "$setOnInsert": {"tenant_id": TENANT_ID, "wa_id": wa_id},
                },
                upsert=True,
            )

    open_count = db.user_states.count_documents(
        {
            "tenant_id": TENANT_ID,
            "wa_id": {"$in": [chat["wa_id"] for chat in CHATS]},
            "handover_resolved_at": None,
        }
    )
    print(
        f"Restored {restored_messages} dummy messages across {open_count} open "
        f"conversations for tenant {TENANT_ID}."
    )


if __name__ == "__main__":
    main()
