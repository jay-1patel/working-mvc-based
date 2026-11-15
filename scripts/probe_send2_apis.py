"""Probe every send2.digital API used by the chatbot.

Safe reads first (poll). Outbound sends go to TEST_WA (default: last Active Test
menu recipient or a number you pass via --to).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "routing"))

from dotenv import load_dotenv

load_dotenv(REPO / "routing" / ".env")

from routing.config import (  # noqa: E402
    SEND2_USERNAME,
    SEND2_PASSWORD,
    SEND2_NUMBER,
    SEND2_SESSION_MSG_URL,
    SEND2_INCOMING_URL,
    SEND2_INCOMING_ENTRY_URL,
    SEND2_LIST_MENU_URL,
    SEND2_QUICK_BUTTON_URL,
    SEND2_MEDIA_URL,
    SEND2_TEMPLATE_URL,
)

TIMEOUT = 30.0


def _ok(status: int, body: str) -> bool:
    if status == 200:
        return True
    # Some Send2 report endpoints return 200 with plain text; treat auth failures
    # as hard fails.
    low = (body or "").lower()
    if any(x in low for x in ("unauthorized", "invalid credential", "auth fail", "login failed")):
        return False
    return False


def probe(name: str, method: str, url: str, accept_statuses=None, **kwargs) -> dict:
    started = time.time()
    accept = set(accept_statuses or [200])
    try:
        with httpx.Client(trust_env=False, timeout=TIMEOUT) as client:
            resp = client.request(method, url, **kwargs)
        elapsed_ms = int((time.time() - started) * 1000)
        body = resp.text[:400]
        ok = resp.status_code in accept and not any(
            x in (body or "").lower()
            for x in ("unauthorized", "invalid credential", "auth fail", "login failed")
        )
        result = {
            "name": name,
            "url": url,
            "method": method,
            "status": resp.status_code,
            "elapsed_ms": elapsed_ms,
            "ok": ok,
            "body": body.replace("\n", " "),
        }
    except Exception as exc:
        result = {
            "name": name,
            "url": url,
            "method": method,
            "status": None,
            "elapsed_ms": int((time.time() - started) * 1000),
            "ok": False,
            "body": f"EXCEPTION: {exc}",
        }
    flag = "PASS" if result["ok"] else "FAIL"
    print(f"[{flag}] {name} | HTTP {result['status']} | {result['elapsed_ms']}ms")
    print(f"       {result['body'][:220]}")
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--to",
        default="917575847722",
        help="WhatsApp number for outbound send probes (digits with country code)",
    )
    ap.add_argument(
        "--skip-send",
        action="store_true",
        help="Only probe poll/auth endpoints; do not send WhatsApp messages",
    )
    args = ap.parse_args()
    to = "".join(ch for ch in args.to if ch.isdigit())

    print("=== Send2 config ===")
    print(f"username     = {SEND2_USERNAME!r}")
    print(f"business no  = {SEND2_NUMBER!r}")
    print(f"probe to     = {to}")
    print(f"poller URL   = {SEND2_INCOMING_URL}")
    print(f"send URL     = {SEND2_SESSION_MSG_URL}")
    print()

    results = []

    # 1) Host reachability
    results.append(
        probe(
            "DNS / health (api.send2.digital)",
            "GET",
            "https://api.send2.digital/",
            accept_statuses=list(range(200, 500)),
        )
    )

    # 2) Incoming poll (read-only)
    now = datetime.now()
    poll_payload = {
        "user_name": SEND2_USERNAME,
        "password": SEND2_PASSWORD,
        "from_date": (now - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S"),
        "to_date": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
    r = probe("POLL incoming-report", "POST", SEND2_INCOMING_URL, json=poll_payload)
    if r["status"] == 200:
        r["ok"] = True
        body = r.get("body") or ""
        if "No Data Found" in body:
            print("       poll window empty (No Data Found) — auth OK")
        else:
            try:
                messages = json.loads(body)
                count = len(messages) if isinstance(messages, list) else 1
                print(f"       poll returned data (items≈{count})")
            except Exception:
                print("       poll returned non-JSON body but HTTP 200")
    results.append(r)

    # 3) Incoming entry (platform log — does not send WhatsApp)
    entry_payload = {
        "username": SEND2_USERNAME,
        "password": SEND2_PASSWORD,
        "number": to,
        "msg_type": "text",
        "msg": f"[API CHECK] incoming-entry probe {now.strftime('%H:%M:%S')}",
        "time": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
    r = probe(
        "INCOMING ENTRY AI_chatbot_API_incomingentry",
        "POST",
        SEND2_INCOMING_ENTRY_URL,
        json=entry_payload,
    )
    results.append(r)

    # 4) Media endpoint auth (expect 404 for fake id — proves route + auth path)
    media_url = f"{(SEND2_MEDIA_URL or '').rstrip('/')}/probe-nonexistent-id"
    r = probe(
        "MEDIA download path",
        "GET",
        media_url,
        auth=(SEND2_USERNAME, SEND2_PASSWORD),
        accept_statuses=[200, 400, 404],
    )
    if r["ok"]:
        print("       endpoint reachable (404/400 on fake id is expected)")
    results.append(r)

    # 5) Template create endpoint reachability without creating a real template:
    # send incomplete payload; auth-accepted INVALID PARAMETER / validation error = OK.
    tmpl_payload = {
        "user_name": SEND2_USERNAME,
        "password": SEND2_PASSWORD,
        "language": "en",
        "template_name": f"__probe_do_not_create_{int(time.time())}",
        "category": "UTILITY",
        "subcategory": "custom",
        "header_type": "text",
        "message_body": "",  # intentionally invalid
    }
    r = probe(
        "TEMPLATE create (validation-only)",
        "POST",
        SEND2_TEMPLATE_URL,
        json=tmpl_payload,
        accept_statuses=[200, 400, 409, 422],
    )
    if r["ok"]:
        print("       endpoint reachable (validation/error response is OK for probe)")
    results.append(r)

    if not args.skip_send:
        stamp = datetime.now().strftime("%H:%M:%S")

        # 6) Session text send
        send_payload = {
            "user_name": SEND2_USERNAME,
            "password": SEND2_PASSWORD,
            "contact_no": to,
            "message_type": "text",
            "message": (
                f"[API CHECK {stamp}] Honda demo Send2 text probe — "
                f"session-msg-send OK if you see this."
            ),
        }
        r = probe(
            "SEND session-msg-send (text)",
            "POST",
            SEND2_SESSION_MSG_URL,
            json=send_payload,
        )
        results.append(r)

        # 7) Quick buttons
        btn_payload = {
            "username": SEND2_USERNAME,
            "password": SEND2_PASSWORD,
            "number": to,
            "headertype": "text",
            "headertext": "API Check",
            "bodytext": f"[API CHECK {stamp}] Quick-button probe",
            "footertext": "Honda demo",
            "total_buttons": 2,
            "buttons": [
                {"type": "reply", "reply": {"id": "probe_ok", "title": "Looks Good"}},
                {"type": "reply", "reply": {"id": "probe_help", "title": "Need Help"}},
            ],
        }
        r = probe(
            "SEND session_msg_quickbtn",
            "POST",
            SEND2_QUICK_BUTTON_URL,
            json=btn_payload,
        )
        results.append(r)

        # 8) List menu
        list_payload = {
            "username": SEND2_USERNAME,
            "password": SEND2_PASSWORD,
            "number": to,
            "headertext": "API Check",
            "bodytext": f"[API CHECK {stamp}] List-menu probe — pick one",
            "footertext": "Honda demo",
            "buttontext": "Open Menu",
            "total_number_section": 1,
            "total_rows": 2,
            "sections": [
                {
                    "title": "Checks",
                    "rows": [
                        {
                            "id": "probe_cars",
                            "title": "Browse Cars",
                            "description": "Demo inventory",
                        },
                        {
                            "id": "probe_drive",
                            "title": "Test Drive",
                            "description": "Book a slot",
                        },
                    ],
                }
            ],
        }
        r = probe(
            "SEND list_messages",
            "POST",
            SEND2_LIST_MENU_URL,
            json=list_payload,
        )
        results.append(r)
    else:
        print("\n(--skip-send) skipped outbound WhatsApp probes")

    print("\n=== SUMMARY ===")
    passed = sum(1 for x in results if x["ok"])
    failed = [x for x in results if not x["ok"]]
    print(f"{passed}/{len(results)} probes passed")
    if failed:
        print("FAILED:")
        for x in failed:
            print(f"  - {x['name']}: HTTP {x['status']} | {x['body'][:160]}")
        return 1
    print("All probed Send2 APIs look reachable/authenticated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
