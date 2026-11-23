#!/usr/bin/env python3
"""Seed script to populate audit_logs with sample data (MongoDB only)."""

import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def generate_timestamp(days_ago=0, hours_ago=0, minutes_ago=0):
    now = datetime.now(timezone.utc)
    delta = timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
    return (now - delta).isoformat()


def generate_sample_data():
    actors = ["admin1", "admin2", "System", "Bot", "Automation"]
    actions = [
        "login", "logout", "message_sent", "message_received", "campaign_started",
        "campaign_stopped", "handover_toggled", "settings_updated", "system_event",
    ]
    categories = ["Authentication", "Messaging", "Campaigns", "System", "Users"]
    statuses = ["success", "failed", "pending"]

    sample_description_templates = [
        "{} logged in from IP {}",
        "{} sent message to {} recipient(s)",
        "{} received message from user {}",
        "{} started campaign '{}'",
        "{} stopped campaign '{}'",
        "{} toggled handover to {}",
        "{} updated {} settings",
        "System event: {}",
        "User {} was created by {}",
        "User {} was updated by {}",
    ]

    ip_addresses = ["192.168.1.1", "192.168.1.2", "192.168.1.3", "10.0.0.1", "10.0.0.2"]
    user_names = ["john_doe", "jane_smith", "bob_wilson", "alice_brown", "charlie_davis"]
    campaign_names = [
        "Summer Sale", "Winter Collection", "New Arrivals", "Flash Sale", "Holiday Special",
    ]
    settings_types = ["theme", "notifications", "permissions", "profile", "security"]

    events = []

    for i in range(100):
        days_ago = random.randint(0, 30)
        hours_ago = random.randint(0, 23)
        minutes_ago = random.randint(0, 59)

        timestamp = generate_timestamp(days_ago, hours_ago, minutes_ago)
        actor = random.choice(actors)
        action = random.choice(actions)
        category = random.choice(categories)
        status = random.choice(statuses)

        template = random.choice(sample_description_templates)

        if action == "login":
            description = template.format(actor, random.choice(ip_addresses))
        elif action == "logout":
            description = template.format(actor)
        elif action == "message_sent":
            description = template.format(actor, random.randint(1, 100))
        elif action == "message_received":
            description = template.format(actor, random.choice(user_names))
        elif action == "campaign_started":
            description = template.format(actor, random.choice(campaign_names))
        elif action == "campaign_stopped":
            description = template.format(actor, random.choice(campaign_names))
        elif action == "handover_toggled":
            toggled_to = random.choice(["ON", "OFF"])
            description = template.format(actor, toggled_to)
        elif action == "settings_updated":
            description = template.format(actor, random.choice(settings_types))
        else:
            description = template.format("System", f"Daily cleanup {i}")

        if status == "failed" and action not in ("login", "logout"):
            description += " - Failed due to invalid input"

        metadata = {
            "ip_address": random.choice(ip_addresses) if action in ("login", "logout") else None,
            "user_agent": (
                f"Mozilla/5.0 (Browser v{random.randint(1, 100)})"
                if action in ("login", "message_sent")
                else None
            ),
            "entity_id": str(random.randint(1, 1000)),
            "additional_info": f"Sample metadata for event {i}",
        }
        metadata = {k: v for k, v in metadata.items() if v is not None}

        events.append({
            "created_at": timestamp,
            "actor": actor,
            "action": action,
            "category": category,
            "status": status,
            "description": description,
            "metadata": json.dumps(metadata),
        })

    return events


def seed_audit_logs():
    try:
        from db.mongo import Repository

        repo = Repository("audit_logs")
        repo.delete_many({})
        print("Cleared existing data from audit_logs")

        events = generate_sample_data()
        for event in events:
            repo.insert(event)

        print(f"Successfully inserted {len(events)} sample audit log events")
        return True
    except Exception as e:
        print(f"Error seeding audit_logs: {e}")
        return False


def main():
    print("Seeding audit_logs collection with sample data...")
    success = seed_audit_logs()
    if success:
        print("Seeding completed successfully.")
    else:
        print("Seeding failed")
    return success


if __name__ == "__main__":
    main()