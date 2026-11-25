"""Seed spiritual event facility pins into Mongo ``event_facilities``.

Idempotent: skips rows that already match tenant+event+type+name.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

env_path = ROOT / "routing" / ".env"
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, val = line.partition("=")
    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

os.environ.setdefault("DATABASE_BACKEND", "mongodb")

from db.event_facilities import create_event_facility, list_event_facilities  # noqa: E402
from db.mongo import get_database, initialize_indexes, REGISTRY  # noqa: E402

TENANT_ID = "spiritual"

SEED: list[dict] = []


def _add(event: str, typ: str, name: str, address: str, lat: float, lng: float, message: str, sort_order: int = 0):
    SEED.append({
        "tenant_id": TENANT_ID,
        "event": event,
        "type": typ,
        "name": name,
        "address": address,
        "latitude": lat,
        "longitude": lng,
        "message": message,
        "is_active": 1,
        "sort_order": sort_order,
    })


def _build_seed() -> None:
    # Gangasagar
    _add("gangasagar", "medical", "Gangasagar Medical Camp A", "Near Kapil Muni Temple", 21.6525, 88.0752,
         "🚨 *Nearest Medical Camp — Gangasagar*\n\nIf life-threatening, call emergency services first.\nPin shared above.", 0)
    _add("gangasagar", "medical", "Gangasagar Medical Camp B", "Near Snan Ghat approach", 21.6508, 88.0735,
         "🚨 *Nearest Medical Camp — Gangasagar*\n\nIf life-threatening, call emergency services first.\nPin shared above.", 1)
    _add("gangasagar", "police", "Gangasagar Police / Control", "Mela control room", 21.6530, 88.0760,
         "👮 *Police / Helpdesk — Gangasagar*\n\nControl booth pin shared above.", 0)
    _add("gangasagar", "police", "Gangasagar Police Booth South", "South approach booth", 21.6495, 88.0740,
         "👮 *Police / Helpdesk — Gangasagar*\n\nBooth pin shared above.", 1)
    _add("gangasagar", "ambulance", "Gangasagar Ambulance A", "Ambulance stand near temple", 21.6518, 88.0745,
         "🚑 *Ambulance Point — Gangasagar*\n\nAmbulance stand pin shared above.", 0)
    _add("gangasagar", "ambulance", "Gangasagar Ambulance B", "Jetty-side ambulance point", 21.6488, 88.0728,
         "🚑 *Ambulance Point — Gangasagar*\n\nAmbulance stand pin shared above.", 1)
    _add("gangasagar", "women", "Women & Child Helpdesk A", "Main helpdesk", 21.6522, 88.0758,
         "👩 *Women / Child Helpdesk — Gangasagar*\n\nHelpdesk pin shared above.", 0)
    _add("gangasagar", "women", "Women & Child Helpdesk B", "Ghat-side helpdesk", 21.6510, 88.0748,
         "👩 *Women / Child Helpdesk — Gangasagar*\n\nHelpdesk pin shared above.", 1)
    _add("gangasagar", "reunion", "Lost & Found / Reunion Centre", "Family reunion centre", 21.6528, 88.0755,
         "🧭 *Reunion Centre — Gangasagar*\n\nOfficial reunion centre pin shared above.", 0)
    _add("gangasagar", "lost_counter", "Lost & Found Counter", "Lost-found counter", 21.6526, 88.0753,
         "🧳 *Lost & Found Counter — Gangasagar*\n\nCounter pin shared above.", 0)

    # Kumbh
    _add("kumbh", "medical", "Kumbh Medical Camp A", "Near Sangam", 25.4295, 81.8848,
         "🚨 *Nearest Medical Camp — Kumbh*\n\nIf life-threatening, call emergency services first.\nPin shared above.", 0)
    _add("kumbh", "medical", "Kumbh Medical Camp B", "Sector medical camp", 25.4278, 81.8825,
         "🚨 *Nearest Medical Camp — Kumbh*\n\nIf life-threatening, call emergency services first.\nPin shared above.", 1)
    _add("kumbh", "police", "Kumbh Police Control", "Mela police control room", 25.4300, 81.8855,
         "👮 *Police / Helpdesk — Kumbh*\n\nControl room pin shared above.", 0)
    _add("kumbh", "police", "Kumbh Police Booth", "Ghat-side police booth", 25.4282, 81.8838,
         "👮 *Police / Helpdesk — Kumbh*\n\nBooth pin shared above.", 1)
    _add("kumbh", "ambulance", "Kumbh Ambulance A", "Sangam ambulance stand", 25.4290, 81.8840,
         "🚑 *Ambulance Point — Kumbh*\n\nAmbulance stand pin shared above.", 0)
    _add("kumbh", "ambulance", "Kumbh Ambulance B", "Sector ambulance point", 25.4270, 81.8820,
         "🚑 *Ambulance Point — Kumbh*\n\nAmbulance stand pin shared above.", 1)
    _add("kumbh", "women", "Women & Child Helpdesk A", "Main helpdesk", 25.4298, 81.8852,
         "👩 *Women / Child Helpdesk — Kumbh*\n\nHelpdesk pin shared above.", 0)
    _add("kumbh", "women", "Women & Child Helpdesk B", "Sector helpdesk", 25.4285, 81.8835,
         "👩 *Women / Child Helpdesk — Kumbh*\n\nHelpdesk pin shared above.", 1)
    _add("kumbh", "reunion", "Lost & Found / Reunion Centre", "Family reunion centre", 25.4302, 81.8850,
         "🧭 *Reunion Centre — Kumbh*\n\nOfficial reunion centre pin shared above.", 0)
    _add("kumbh", "lost_counter", "Lost & Found Counter", "Lost-found counter", 25.4301, 81.8849,
         "🧳 *Lost & Found Counter — Kumbh*\n\nCounter pin shared above.", 0)

    # Rath Yatra
    _add("rath_yatra", "medical", "Puri Medical / First Aid A", "Near Jagannath Temple", 19.8047, 85.8180,
         "🚨 *Nearest Medical Help — Rath Yatra*\n\nIf life-threatening, call emergency services first.\nPin shared above.", 0)
    _add("rath_yatra", "medical", "Puri Medical / First Aid B", "Near Gundicha / Bada Danda north", 19.8120, 85.8310,
         "🚨 *Nearest Medical Help — Rath Yatra*\n\nIf life-threatening, call emergency services first.\nPin shared above.", 1)
    _add("rath_yatra", "police", "Puri Police / Yatra Helpdesk A", "Near Bada Danda", 19.8052, 85.8185,
         "👮 *Police / Helpdesk — Rath Yatra*\n\nHelpdesk pin shared above.", 0)
    _add("rath_yatra", "police", "Puri Police Booth B", "Near railway approach", 19.8078, 85.8375,
         "👮 *Police / Helpdesk — Rath Yatra*\n\nBooth pin shared above.", 1)
    _add("rath_yatra", "ambulance", "Puri Ambulance A", "Temple approach ambulance", 19.8040, 85.8175,
         "🚑 *Ambulance Point — Rath Yatra*\n\nAmbulance point pin shared above.", 0)
    _add("rath_yatra", "ambulance", "Puri Ambulance B", "Beach-road ambulance point", 19.7985, 85.8255,
         "🚑 *Ambulance Point — Rath Yatra*\n\nAmbulance point pin shared above.", 1)
    _add("rath_yatra", "women", "Women & Child Helpdesk A", "Temple-side helpdesk", 19.8049, 85.8182,
         "👩 *Women / Child Helpdesk — Rath Yatra*\n\nHelpdesk pin shared above.", 0)
    _add("rath_yatra", "women", "Women & Child Helpdesk B", "Bada Danda helpdesk", 19.8085, 85.8240,
         "👩 *Women / Child Helpdesk — Rath Yatra*\n\nHelpdesk pin shared above.", 1)
    _add("rath_yatra", "reunion", "Lost & Found / Reunion Centre", "Family reunion centre, Puri", 19.8055, 85.8190,
         "🧭 *Reunion Centre — Rath Yatra*\n\nOfficial reunion centre pin shared above.", 0)
    _add("rath_yatra", "lost_counter", "Lost & Found Counter", "Lost-found counter, Puri", 19.8054, 85.8188,
         "🧳 *Lost & Found Counter — Rath Yatra*\n\nCounter pin shared above.", 0)


def main() -> int:
    _build_seed()
    # Ensure collection + indexes exist for the new schema table.
    db = get_database()
    initialize_indexes(db)
    print("schema tables include event_facilities:", "event_facilities" in REGISTRY["tables"])

    existing = list_event_facilities(TENANT_ID, active_only=False)
    existing_keys = {
        (str(r.get("event")), str(r.get("type")), str(r.get("name")))
        for r in existing
    }
    created = 0
    skipped = 0
    for row in SEED:
        key = (row["event"], row["type"], row["name"])
        if key in existing_keys:
            skipped += 1
            continue
        create_event_facility(row)
        created += 1
    print(f"seeded tenant={TENANT_ID} created={created} skipped={skipped} total_seed={len(SEED)}")
    live = list_event_facilities(TENANT_ID, active_only=True)
    print(f"active facilities now: {len(live)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
