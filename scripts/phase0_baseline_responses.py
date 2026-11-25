#!/usr/bin/env python3
"""Phase 0 — response baseline via the panel test-simulator endpoint.

Builds >=30 questions per active tenant (FAQs, KB topics, products/prices,
contact details, every WhatsApp menu path), runs them through
POST /api/test-simulator, and writes baseline_responses.json.

Source attribution:
  - Menu turns: interactive row/button ids from the captured reply.
  - FAQ/KB turns: the same build_grounded_context() the live FAQ path uses
    (matched FAQ metadata + knowledge doc ids). The simulator HTTP response
    does not expose retrieval meta; we resolve it in-process with the same
    query + tenant so Phase 4 can compare sources.

Usage:
  python scripts/phase0_baseline_responses.py
  python scripts/phase0_baseline_responses.py --out baseline_responses.json
  python scripts/phase0_baseline_responses.py --out after_responses.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(REPO_ROOT / "routing" / ".env")

BASE_URL = os.environ.get("BASELINE_API_URL", "http://127.0.0.1:9000").rstrip("/")
AUTH_USER = os.environ.get("BASELINE_AUTH_USER", "Customercare")
AUTH_SESSION = os.environ.get(
    "BASELINE_AUTH_SESSION", "3042_1794914340_c8f3a72d9e6b"
)
MIN_QUESTIONS = 30

PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-()]{8,}\d)")
PRICE_RE = re.compile(
    r"(?:Rs\.?\s*|INR\s*|₹\s*)[\d,]+(?:\.\d+)?(?:\s*(?:lakh|L|cr|Crore))?",
    re.I,
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def _mongo():
    from pymongo import MongoClient

    uri = os.environ["MONGODB_URI"]
    dbn = os.environ.get("MONGODB_DATABASE", "tmpdbtest")
    return MongoClient(uri, serverSelectionTimeoutMS=8000)[dbn]


def _auth_payload() -> Dict[str, str]:
    return {"username": AUTH_USER, "session_id": AUTH_SESSION}


def api_post(path: str, body: Dict[str, Any], timeout: int = 300) -> Dict[str, Any]:
    payload = {**body, **_auth_payload()}
    last_exc: Exception | None = None
    for attempt in range(1, 6):
        try:
            r = requests.post(
                f"{BASE_URL}{path}",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code} {path}: {r.text[:500]}")
            return r.json()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            last_exc = exc
            wait = min(30, 2 * attempt)
            print(f"    retry {attempt}/5 after {type(exc).__name__}; sleep {wait}s", flush=True)
            time.sleep(wait)
    assert last_exc is not None
    raise last_exc


def reset_user(wa_id: str, tenant_id: str) -> None:
    api_post(
        "/api/test-simulator/reset",
        {"wa_id": wa_id, "tenant_id": tenant_id, "user_type": "b2c"},
        timeout=60,
    )


def simulate(wa_id: str, message: str, tenant_id: str) -> Dict[str, Any]:
    return api_post(
        "/api/test-simulator",
        {
            "wa_id": wa_id,
            "message": message,
            "user_type": "b2c",
            "tenant_id": tenant_id,
        },
        timeout=300,
    )


def extract_facts(text: str) -> Dict[str, List[str]]:
    phones = sorted(set(re.sub(r"\s+", " ", p).strip() for p in PHONE_RE.findall(text or "")))
    prices = sorted(set(p.strip() for p in PRICE_RE.findall(text or "")))
    emails = sorted(set(e.lower() for e in EMAIL_RE.findall(text or "")))
    return {"phones": phones, "prices": prices, "emails": emails}


def flatten_response_text(result: Dict[str, Any]) -> str:
    parts: List[str] = []
    for msg in result.get("whatsapp") or result.get("messages") or []:
        if not isinstance(msg, dict):
            continue
        for key in ("text", "body", "header", "footer"):
            val = msg.get(key)
            if val:
                parts.append(str(val))
        for btn in msg.get("buttons") or []:
            if isinstance(btn, dict):
                title = (btn.get("reply") or {}).get("title") or btn.get("title")
                bid = (btn.get("reply") or {}).get("id") or btn.get("id")
                if title or bid:
                    parts.append(f"{bid}:{title}")
        for sec in msg.get("sections") or []:
            for row in (sec or {}).get("rows") or []:
                parts.append(f"{row.get('id')}:{row.get('title')}")
    return "\n".join(parts)


def menu_ids_from_response(result: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for msg in result.get("whatsapp") or result.get("messages") or []:
        if not isinstance(msg, dict):
            continue
        for btn in msg.get("buttons") or []:
            if isinstance(btn, dict):
                bid = (btn.get("reply") or {}).get("id") or btn.get("id")
                if bid:
                    ids.append(str(bid))
        for sec in msg.get("sections") or []:
            for row in (sec or {}).get("rows") or []:
                if row.get("id"):
                    ids.append(str(row["id"]))
    return ids


def load_tenant_profile(tenant_id: str) -> Dict[str, Any]:
    from shared.tenancy import loader

    p = loader.get_tenant_profile(tenant_id)
    return p.model_dump() if hasattr(p, "model_dump") else p.dict()


async def resolve_retrieval_source(query: str, tenant_id: str) -> Dict[str, Any]:
    from backend.services.unified_retrieval import build_grounded_context

    _ctx, meta = await build_grounded_context(query, tenant_id, k=5)
    faq_meta = meta.get("faq_best_metadata") or {}
    faq_ids: List[Any] = []
    faq_files: List[str] = []
    kb_ids: List[Any] = []
    for hit in meta.get("source_hits") or []:
        m = hit.get("metadata") or {}
        src = hit.get("source")
        if src == "tenant_faq":
            if m.get("id") is not None:
                faq_ids.append(m.get("id"))
            elif m.get("chunk_id") is not None:
                faq_ids.append(m.get("chunk_id"))
            sf = m.get("source_file")
            if sf:
                faq_files.append(str(sf))
        elif src == "tenant_kb":
            if m.get("doc_id") is not None:
                kb_ids.append(m.get("doc_id"))
    if faq_meta.get("id") is not None and faq_meta.get("id") not in faq_ids:
        faq_ids.insert(0, faq_meta.get("id"))
    if faq_meta.get("source_file") and str(faq_meta["source_file"]) not in faq_files:
        faq_files.insert(0, str(faq_meta["source_file"]))

    kind = "unknown"
    sources = meta.get("sources") or []
    if "tenant_faq" in sources and "tenant_kb" in sources:
        kind = "mixed"
    elif "tenant_faq" in sources:
        kind = "faq"
    elif "tenant_kb" in sources:
        kind = "kb"
    elif "tenant_profile" in sources:
        kind = "profile"

    return {
        "kind": kind,
        "faq_ids": faq_ids,
        "faq_source_files": faq_files,
        "knowledge_doc_ids": kb_ids,
        "sources": sources,
        "faq_best_score": meta.get("faq_best_score"),
        "kb_best_score": meta.get("kb_best_score"),
        "faq_best_metadata": {
            k: faq_meta.get(k)
            for k in ("id", "source_file", "module", "media_url", "media_type")
            if faq_meta.get(k) is not None
        },
    }


def build_question_bank(tenant_id: str, db) -> List[Dict[str, Any]]:
    """At least MIN_QUESTIONS covering FAQs, KB, products, prices, contact, menus."""
    questions: List[Dict[str, Any]] = []
    profile = load_tenant_profile(tenant_id)
    brand = profile.get("brand") or {}
    menu = profile.get("menu") or {}
    menu_buttons = list(menu.get("buttons") or [])
    menu_key = menu.get("key") or "kb_main"

    # 1) Greeting / main menu
    questions.append(
        {
            "category": "menu",
            "message": "hi",
            "expect": "main_menu",
            "menu_key": menu_key,
        }
    )

    # 2) Every WhatsApp menu path (tap each button after greeting)
    for btn in menu_buttons:
        bid = btn.get("id")
        if not bid:
            continue
        questions.append(
            {
                "category": "menu",
                "message": str(bid),
                "sequence": ["hi", str(bid)],
                "expect": "menu_path",
                "menu_id": str(bid),
                "menu_key": menu_key,
                "menu_title": btn.get("title"),
            }
        )

    # 3) Contact / brand details from profile
    contact_qs = [
        ("What is your phone number?", "contact"),
        ("What is your support email?", "contact"),
        ("What is your website?", "contact"),
        ("What are your business hours?", "contact"),
        ("Where is your showroom address?", "contact"),
        (f"Tell me about {brand.get('name') or tenant_id}", "contact"),
        ("Who are you?", "contact"),
    ]
    for msg, cat in contact_qs:
        questions.append({"category": cat, "message": msg})

    # 4) FAQ questions extracted from faq_dataset
    faq_qs: List[Tuple[str, Any]] = []
    for row in db.faq_dataset.find({"tenant_id": tenant_id}, {"id": 1, "content": 1}):
        content = row.get("content") or ""
        for m in re.finditer(r"Q\d+\.\s*(.+?)(?:\n|$)", content):
            q = m.group(1).strip()
            if len(q) > 10:
                faq_qs.append((q, row.get("id")))
    # Prefer price / product / service diversity
    picked = []
    for needle in (
        "price",
        "offer",
        "variant",
        "service",
        "warranty",
        "finance",
        "insurance",
        "test drive",
        "discount",
        "cheapest",
    ):
        for q, fid in faq_qs:
            if needle in q.lower() and q not in [p[0] for p in picked]:
                picked.append((q, fid))
                break
    for q, fid in faq_qs:
        if len(picked) >= 12:
            break
        if q not in [p[0] for p in picked]:
            picked.append((q, fid))
    for q, fid in picked[:12]:
        questions.append(
            {
                "category": "faq",
                "message": q,
                "hint_faq_id": fid,
            }
        )

    # 5) Knowledge-base topic questions (from doc titles / first heading)
    for row in db.knowledge_base.find(
        {"tenant_id": tenant_id}, {"id": 1, "source": 1, "title": 1, "content": 1}
    ):
        title = (row.get("title") or row.get("source") or "").replace(".pdf", "").replace("_", " ")
        content = row.get("content") or ""
        heading = None
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("#"):
                heading = line.lstrip("#").strip()
                break
        topic = heading or title
        if not topic or topic.lower().startswith("knowledge gap"):
            continue
        questions.append(
            {
                "category": "kb",
                "message": f"Tell me about {topic}",
                "hint_kb_id": row.get("id"),
            }
        )
        if sum(1 for q in questions if q["category"] == "kb") >= 6:
            break

    # 6) Products / prices / services
    for prod in db.products.find({"tenant_id": tenant_id}, {"name": 1, "category": 1, "price": 1, "base_price": 1}).limit(
        40
    ):
        name = (prod.get("name") or "").strip()
        if not name:
            continue
        cat = (prod.get("category") or "").lower()
        if "price" in name.lower() or cat in ("vehicles", "sedan", "suv") or "car" in name.lower():
            questions.append(
                {
                    "category": "price",
                    "message": f"What is the price of the {name}?",
                    "product_name": name,
                }
            )
        else:
            questions.append(
                {
                    "category": "product",
                    "message": f"Tell me about {name}",
                    "product_name": name,
                }
            )
        prod_count = sum(1 for q in questions if q["category"] in ("product", "price"))
        if prod_count >= 10:
            break

    # Pad with stable generic / intent questions to reach MIN_QUESTIONS
    fillers = [
        ("Show me your cars", "product"),
        ("I want a brochure", "menu"),
        ("Book a test drive", "menu"),
        ("I need finance options", "menu"),
        ("Talk to sales", "menu"),
        ("I have a complaint", "menu"),
        ("Do you have SUVs?", "product"),
        ("Do you offer car loan assistance?", "product"),
        ("What services do you provide?", "product"),
        ("Is there a periodic service package?", "product"),
        ("Can I exchange my old car?", "product"),
        ("What insurance options do you have?", "product"),
        ("How do I book an appointment?", "contact"),
        ("Good morning", "menu"),
        ("hello", "menu"),
        ("menu", "menu"),
        ("help", "menu"),
        ("What brands do you sell?", "product"),
        ("Do you have used cars?", "product"),
        ("What is roadside assistance?", "kb"),
    ]
    existing = {q["message"].lower() for q in questions}
    for msg, cat in fillers:
        if len(questions) >= MIN_QUESTIONS:
            break
        if msg.lower() in existing:
            continue
        questions.append({"category": cat, "message": msg})
        existing.add(msg.lower())

    # Ensure minimum
    i = 0
    while len(questions) < MIN_QUESTIONS:
        i += 1
        questions.append(
            {
                "category": "menu",
                "message": "hi" if i % 2 else "menu",
                "pad": True,
            }
        )

    # Stable ids
    for idx, q in enumerate(questions, 1):
        q["id"] = f"{tenant_id}-{idx:03d}"
    return questions


def run_one(tenant_id: str, q: Dict[str, Any]) -> Dict[str, Any]:
    wa_id = f"baseline-{tenant_id}-{q['id']}-{uuid.uuid4().hex[:8]}"
    sequence = q.get("sequence") or [q["message"]]
    t0 = time.time()
    last: Dict[str, Any] = {}
    try:
        reset_user(wa_id, tenant_id)
        for step in sequence:
            last = simulate(wa_id, step, tenant_id)
        elapsed = round(time.time() - t0, 2)
        text = flatten_response_text(last)
        facts = extract_facts(text)
        menu_ids = menu_ids_from_response(last)

        source: Dict[str, Any]
        if q.get("category") == "menu" or q.get("menu_id"):
            source = {
                "kind": "menu",
                "menu_key": q.get("menu_key"),
                "menu_id": q.get("menu_id") or (sequence[-1] if len(sequence) > 1 else None),
                "shown_ids": menu_ids,
            }
        else:
            try:
                source = asyncio.run(resolve_retrieval_source(q["message"], tenant_id))
            except Exception as exc:
                source = {"kind": "error", "error": f"{type(exc).__name__}: {exc}"}
            # If the reply itself is a menu, record that too
            if menu_ids and source.get("kind") in ("unknown", "error"):
                source = {
                    "kind": "menu",
                    "menu_key": q.get("menu_key"),
                    "shown_ids": menu_ids,
                    "note": "reply was interactive menu",
                }

        return {
            "id": q["id"],
            "tenant_id": tenant_id,
            "category": q.get("category"),
            "message": q["message"],
            "sequence": sequence,
            "ok": True,
            "elapsed_sec": elapsed,
            "new_state": last.get("new_state"),
            "status": last.get("status"),
            "whatsapp": last.get("whatsapp") or [],
            "messages": last.get("messages") or [],
            "response_text": text,
            "facts": facts,
            "source": source,
            "hint_faq_id": q.get("hint_faq_id"),
            "hint_kb_id": q.get("hint_kb_id"),
            "product_name": q.get("product_name"),
        }
    except Exception as exc:
        return {
            "id": q["id"],
            "tenant_id": tenant_id,
            "category": q.get("category"),
            "message": q["message"],
            "sequence": sequence,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "facts": {"phones": [], "prices": [], "emails": []},
            "source": {"kind": "error", "error": str(exc)},
            "response_text": "",
            "whatsapp": [],
            "messages": [],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "baseline_responses.json"),
        help="Output JSON path",
    )
    parser.add_argument("--tenants", nargs="*", default=None, help="Subset of tenant ids")
    parser.add_argument("--limit-per-tenant", type=int, default=0, help="Debug cap")
    args = parser.parse_args()

    # Verify auth
    login = api_post("/api/auth/login", {})
    print(f"AUTH ok role={login.get('role')} user={login.get('username')}")

    db = _mongo()
    from shared.tenancy import store

    tenant_ids = args.tenants or [t["id"] for t in store.list_tenants()]
    print(f"TENANTS: {tenant_ids}")

    report: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_base": BASE_URL,
        "auth_user": AUTH_USER,
        "min_questions": MIN_QUESTIONS,
        "tenants": {},
        "bank_sizes": {},
    }

    for tid in tenant_ids:
        print(f"\n=== Building bank for {tid} ===")
        bank = build_question_bank(tid, db)
        if args.limit_per_tenant:
            bank = bank[: args.limit_per_tenant]
        print(f"  questions: {len(bank)}")
        results = []
        for i, q in enumerate(bank, 1):
            print(f"  [{i}/{len(bank)}] {q['category']}: {q['message'][:70]!r} ...", flush=True)
            row = run_one(tid, q)
            status = "OK" if row.get("ok") else f"FAIL {row.get('error')}"
            print(
                f"       -> {status} state={row.get('new_state')} "
                f"source={((row.get('source') or {}).get('kind'))} "
                f"{row.get('elapsed_sec')}s"
            )
            results.append(row)
        report["tenants"][tid] = {
            "question_count": len(results),
            "ok_count": sum(1 for r in results if r.get("ok")),
            "questions": results,
        }
        report["bank_sizes"][tid] = len(results)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
    print(f"\nWrote {out_path}")
    print("Bank sizes:", json.dumps(report["bank_sizes"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
