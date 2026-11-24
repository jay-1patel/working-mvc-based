"""Fill spiritual menu intent answers from uploaded FAQ + KB content.

Prefer KB section headings (e.g. \"Sacred History & Heritage\") over loose
keyword hits so menu taps like History never pull Do's/Don'ts or unrelated FAQ.
"""
from __future__ import annotations

import os
import re
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

from pymongo import MongoClient  # noqa: E402
from shared.tenancy import store as tenancy_store  # noqa: E402
from shared.tenancy.loader import reload_profile  # noqa: E402

TENANT_ID = "spiritual"

# Primary: match these heading patterns against KB chunks / markdown sections.
# Secondary keywords only used inside a matched section (or as weak fallback).
INTENT_SECTIONS = {
    "prasad_info": {
        "title": "Prasad",
        "headings": [r"prasad", r"prasadam", r"blessed food"],
        "keywords": ["prasad", "prasadam", "bhog"],
        "examples": ["prasad", "prasad timing", "prasad offerings"],
    },
    "arti_time": {
        "title": "Arti Time",
        "headings": [r"daily\s+aarti", r"aarti\s+schedule", r"arti\s+time", r"aarti"],
        "keywords": ["aarti", "arti", "mangala", "sandhya", "schedule"],
        "examples": ["arti time", "aarti timing", "when is arti"],
    },
    "how_to_reach": {
        "title": "How to Reach",
        "headings": [r"how\s+to\s+reach", r"directions?", r"location", r"getting\s+here"],
        "keywords": ["reach", "direction", "address", "location", "airport", "station"],
        "examples": ["how to reach", "directions", "location", "address"],
    },
    "where_to_stay": {
        "title": "Where to Stay",
        "headings": [r"where\s+to\s+stay", r"stay\s+options?", r"accommodation", r"lodging", r"dharamshala"],
        "keywords": ["stay", "lodge", "hotel", "dharamshala", "accommodation"],
        "examples": ["where to stay", "stay options", "lodging", "dharamshala"],
    },
    "advantage_info": {
        "title": "Advantage",
        "headings": [r"why\s+devotees\s+visit", r"advantage", r"benefits?\s+of", r"why\s+visit"],
        "keywords": ["advantage", "benefit", "seva", "blessing", "why visit"],
        "examples": ["advantage", "benefits", "why visit"],
    },
    "history_info": {
        "title": "History",
        "headings": [
            r"sacred\s+history",
            r"history\s*[&/]\s*heritage",
            r"history\s+and\s+heritage",
            r"^#?\s*history\b",
        ],
        "keywords": ["swayambhu", "lingam", "heritage", "merchant family", "mahashivratri"],
        # Avoid loose \"history\" alone — it matches school-trip FAQ / do's-and-don'ts.
        "examples": ["history", "heritage", "origin"],
    },
    "vehicle_type": {
        "title": "Vehicle Type",
        "headings": [r"parking\s*[&/]\s*vehicle", r"vehicle\s+guidance", r"parking", r"vehicle\s+type"],
        "keywords": ["vehicle", "parking", "two-wheeler", "car", "bus"],
        "examples": ["vehicle type", "parking", "car parking"],
    },
}


def _collect_kb_blobs(db) -> list[str]:
    """KB content + chunks only (section source of truth)."""
    texts: list[str] = []
    for row in db.knowledge_base.find({"tenant_id": TENANT_ID}):
        content = str(row.get("content") or "").strip()
        if content:
            texts.append(content)
        chunks = row.get("chunks_json")
        if isinstance(chunks, list):
            for chunk in chunks:
                c = str(chunk or "").strip()
                if c:
                    texts.append(c)
    return texts


def _collect_faq_blobs(db) -> list[str]:
    texts: list[str] = []
    for row in db.faq_dataset.find({"tenant_id": TENANT_ID}):
        content = str(row.get("content") or "").strip()
        if content:
            texts.append(content)
    return texts


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Return (heading, body) pairs from markdown / titled blocks."""
    # Split on markdown headings or ALL-CAPS / Title lines that look like sections.
    parts = re.split(r"(?m)^(#{1,3}\s+.+|[A-Z][A-Za-z0-9 &/'—\-]{8,80})$", text)
    if len(parts) == 1:
        return [("", text.strip())] if text.strip() else []

    out: list[tuple[str, str]] = []
    # parts[0] is preamble before first heading
    if parts[0].strip():
        out.append(("", parts[0].strip()))
    i = 1
    while i + 1 < len(parts):
        heading = re.sub(r"^#+\s*", "", parts[i]).strip()
        body = (parts[i + 1] or "").strip()
        if heading or body:
            out.append((heading, body))
        i += 2
    return out


def _heading_matches(heading: str, patterns: list[str]) -> bool:
    h = heading.strip()
    if not h:
        return False
    for pat in patterns:
        if re.search(pat, h, flags=re.I):
            return True
    return False


def _chunk_matches_heading(chunk: str, patterns: list[str]) -> bool:
    """True when the chunk opens with / is titled as the target section."""
    head = "\n".join(chunk.strip().splitlines()[:3])
    for pat in patterns:
        if re.search(pat, head, flags=re.I):
            return True
    return False


def _pick_section_text(kb_blobs: list[str], headings: list[str]) -> str:
    """Prefer whole KB chunks / markdown sections whose title matches."""
    # 1) Whole chunks that open with the section heading (best for PDF chunks).
    scored_chunks: list[tuple[int, str]] = []
    for blob in kb_blobs:
        if not _chunk_matches_heading(blob, headings):
            continue
        # Prefer chunks that look like the dedicated section (contain heading words densely).
        head = "\n".join(blob.strip().splitlines()[:2]).lower()
        score = 10
        if "sacred history" in head or "history & heritage" in head or "history and heritage" in head:
            score = 30
        scored_chunks.append((score, blob.strip()[:3500]))
    if scored_chunks:
        scored_chunks.sort(key=lambda x: (-x[0], -len(x[1])))
        return scored_chunks[0][1]

    # 2) Markdown / titled sections inside full document text.
    for blob in kb_blobs:
        for heading, body in _split_sections(blob):
            if _heading_matches(heading, headings) and len(body) >= 80:
                return f"{heading}\n\n{body}".strip()[:3500]
    return ""


def _pick_keyword_fallback(blobs: list[str], keywords: list[str], limit: int = 3) -> str:
    keys = [k.lower() for k in keywords]
    scored: list[tuple[int, str]] = []
    for blob in blobs:
        # Prefer paragraph blocks, not FAQ Q/A unless strong keyword density.
        for block in re.split(r"\n{2,}", blob):
            cleaned = block.strip()
            if len(cleaned) < 60:
                continue
            low = cleaned.lower()
            # Skip do's/don'ts / school-trip style noise for heritage intents.
            if cleaned.lstrip().lower().startswith("q:") and "history" in keys:
                if "school" in low or "group" in low:
                    continue
            score = sum(2 for k in keys if k in low)
            if score:
                scored.append((score, cleaned[:1200]))
    scored.sort(key=lambda x: (-x[0], -len(x[1])))
    seen = set()
    picked = []
    for _, block in scored:
        key = re.sub(r"\s+", " ", block.lower())[:120]
        if key in seen:
            continue
        seen.add(key)
        picked.append(block)
        if len(picked) >= limit:
            break
    return "\n\n".join(picked)


def _clean_answer_body(text: str) -> str:
    # Drop leading markdown heading markers for WhatsApp readability.
    text = re.sub(r"(?m)^#+\s*", "", text).strip()
    # Collapse excessive blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main() -> int:
    db = MongoClient(os.environ["MONGODB_URI"])[os.environ["MONGODB_DATABASE"]]
    kb_blobs = _collect_kb_blobs(db)
    faq_blobs = _collect_faq_blobs(db)
    print("kb blobs", len(kb_blobs), "faq blobs", len(faq_blobs))

    base = tenancy_store.get_current_payload(TENANT_ID) or {}
    intents = list(base.get("intents") or [])
    by_name = {
        str(i.get("name")): i
        for i in intents
        if isinstance(i, dict) and i.get("name")
    }

    updated = []
    for name, spec in INTENT_SECTIONS.items():
        body = _pick_section_text(kb_blobs, spec["headings"])
        source = "section"
        if not body:
            body = _pick_keyword_fallback(kb_blobs + faq_blobs, spec["keywords"])
            source = "keyword-fallback"
        if not body:
            print("NO DATA for", name)
            continue
        body = _clean_answer_body(body)
        answer = f"*{spec['title']}*\n\n{body}"
        payload = {
            "enabled": True,
            "examples": spec.get("examples") or spec["keywords"][:4],
            "keywords": spec["keywords"],
            "answer": answer,
        }
        if name in by_name:
            by_name[name].update(payload)
        else:
            intents.append({"name": name, **payload})
        updated.append(name)
        print("updated", name, "via", source, "chars", len(answer))
        print("  head:", re.sub(r"\s+", " ", body)[:120])

    draft = {**base, "intents": intents}
    version = tenancy_store.publish_version(
        TENANT_ID,
        draft,
        published_by="enrich-spiritual-intents",
    )
    profile = reload_profile(TENANT_ID)
    print("published", version, "updated", updated)
    for intent in profile.intents:
        if intent.name == "history_info":
            print("=== history_info preview ===")
            print((intent.answer or "")[:900])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
