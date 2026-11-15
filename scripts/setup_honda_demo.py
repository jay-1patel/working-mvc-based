"""Prepare the Honda automobile demo tenant: profile, cars, FAQs, publish, activate."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from routing.config import DB_PATH, EMBEDDING_MODEL_PATH  # noqa: E402
from shared.tenancy import cache, loader, store  # noqa: E402
from shared.tenancy.paths import ensure_client_dir  # noqa: E402

TENANT_ID = "honda"
CONFIG_PATH = REPO / "clients" / "honda" / "config.json"
KB_SRC = REPO / "clients" / "honda" / "knowledge"
KB_DST = REPO / "data" / "tenants" / "honda" / "knowledge"

CARS = [
    {
        "name": "Honda Amaze S MT",
        "slug": "honda-amaze-s-mt",
        "category": "Sedan",
        "short_description": "Petrol · Manual · Compact city sedan",
        "price": "₹7.20 Lakh* ex-showroom (indicative)",
        "description": (
            "Honda Amaze S MT is a compact sedan built for city driving with easy "
            "manoeuvrability, strong mileage, and low ownership cost. Ideal first car."
        ),
        "attrs": {
            "fuel": "Petrol",
            "transmission": "Manual",
            "body": "Sedan",
            "seating": "5",
            "highlight": "City mileage champion",
        },
        "short_label": "Compact Sedan",
    },
    {
        "name": "Honda Amaze VX CVT",
        "slug": "honda-amaze-vx-cvt",
        "category": "Sedan",
        "short_description": "Petrol · CVT · Feature-loaded Amaze",
        "price": "₹9.10 Lakh* ex-showroom (indicative)",
        "description": (
            "Top-spec Amaze with CVT convenience and richer features for comfort-focused "
            "city and highway commuting."
        ),
        "attrs": {
            "fuel": "Petrol",
            "transmission": "CVT",
            "body": "Sedan",
            "seating": "5",
            "highlight": "Automatic convenience",
        },
        "short_label": "Compact Sedan AT",
    },
    {
        "name": "Honda City VX MT",
        "slug": "honda-city-vx-mt",
        "category": "Sedan",
        "short_description": "Petrol · Manual · Premium mid-size sedan",
        "price": "₹13.50 Lakh* ex-showroom (indicative)",
        "description": (
            "Honda City VX MT balances premium cabin space, refined drive, and strong "
            "brand resale. A favourite family sedan."
        ),
        "attrs": {
            "fuel": "Petrol",
            "transmission": "Manual",
            "body": "Sedan",
            "seating": "5",
            "highlight": "Premium family sedan",
        },
        "short_label": "Premium Sedan",
    },
    {
        "name": "Honda City ZX CVT",
        "slug": "honda-city-zx-cvt",
        "category": "Sedan",
        "short_description": "Petrol · CVT · Top-end City",
        "price": "₹16.20 Lakh* ex-showroom (indicative)",
        "description": (
            "Flagship City variant with CVT and top features for buyers wanting maximum "
            "comfort and tech in a sedan."
        ),
        "attrs": {
            "fuel": "Petrol",
            "transmission": "CVT",
            "body": "Sedan",
            "seating": "5",
            "highlight": "Top-spec sedan",
        },
        "short_label": "Flagship Sedan",
    },
    {
        "name": "Honda Elevate V MT",
        "slug": "honda-elevate-v-mt",
        "category": "SUV",
        "short_description": "Petrol · Manual · Mid-size family SUV",
        "price": "₹12.80 Lakh* ex-showroom (indicative)",
        "description": (
            "Honda Elevate V MT offers SUV stance, cabin space, and practical boot for "
            "families who want weekend versatility."
        ),
        "attrs": {
            "fuel": "Petrol",
            "transmission": "Manual",
            "body": "SUV",
            "seating": "5",
            "highlight": "Family SUV value",
        },
        "short_label": "Family SUV",
    },
    {
        "name": "Honda Elevate ZX CVT",
        "slug": "honda-elevate-zx-cvt",
        "category": "SUV",
        "short_description": "Petrol · CVT · Top Elevate SUV",
        "price": "₹16.50 Lakh* ex-showroom (indicative)",
        "description": (
            "Top Elevate with CVT and premium features — the demo hero for SUV shoppers."
        ),
        "attrs": {
            "fuel": "Petrol",
            "transmission": "CVT",
            "body": "SUV",
            "seating": "5",
            "highlight": "Hero SUV for demos",
        },
        "short_label": "Flagship SUV",
    },
    {
        "name": "Honda WR-V VX MT",
        "slug": "honda-wrv-vx-mt",
        "category": "Crossover",
        "short_description": "Petrol · Manual · Compact crossover",
        "price": "₹10.50 Lakh* ex-showroom (indicative)",
        "description": (
            "WR-V brings tall-boy convenience and utility in a compact, city-friendly size."
        ),
        "attrs": {
            "fuel": "Petrol",
            "transmission": "Manual",
            "body": "Crossover",
            "seating": "5",
            "highlight": "Compact crossover",
        },
        "short_label": "Compact Crossover",
    },
]


def _copy_knowledge() -> None:
    KB_DST.mkdir(parents=True, exist_ok=True)
    for src in sorted(KB_SRC.glob("*.md")):
        shutil.copy2(src, KB_DST / src.name)
    print(f"knowledge copied -> {KB_DST}")


def _ensure_tenant() -> None:
    ensure_client_dir(TENANT_ID)
    store.ensure_tenant(
        TENANT_ID,
        slug=TENANT_ID,
        vertical="generic",
        display_name="Honda Cars",
        waba_phone_id="",
    )
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE tenants SET display_name = ?, domain = ?, mobile_number = ?, "
        "vertical = ?, status = 'active', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (
            "Honda Cars",
            "https://www.honda.com/",
            "919876543210",
            "generic",
            TENANT_ID,
        ),
    )
    conn.commit()
    conn.close()
    print("tenant ensured:", TENANT_ID)


def _seed_products() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE tenant_id = ?", (TENANT_ID,))
    for i, car in enumerate(CARS):
        cur.execute(
            """
            INSERT INTO products (
                name, slug, category, description, short_description,
                price, mrp, unit, moq, media_url, media_type, ingredients,
                sort_order, variants_json, stock_quantity, nutritional_facts,
                bulk_discount_tiers, attrs_json, short_label, detail_url,
                tenant_id, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            """,
            (
                car["name"],
                car["slug"],
                car["category"],
                car["description"],
                car["short_description"],
                car["price"],
                "",
                "unit",
                "1",
                "",
                "image",
                "[]",
                i,
                "[]",
                5,
                None,
                "[]",
                json.dumps(car["attrs"]),
                car["short_label"],
                "https://www.honda.com/",
                TENANT_ID,
            ),
        )
    conn.commit()
    conn.close()
    print(f"seeded {len(CARS)} cars")


def _chunk_markdown(path: Path) -> list[tuple[str, str, str]]:
    text = path.read_text(encoding="utf-8")
    rows: list[tuple[str, str, str]] = []

    # Explicit FAQ Q/A pairs
    for m in re.finditer(
        r"### Q:\s*(.*?)\n\*\*A:\*\*\s*(.*?)(?=\n### Q:|\n## |\Z)",
        text,
        flags=re.S,
    ):
        q, a = m.group(1).strip(), m.group(2).strip()
        a = re.sub(r"\*\(Category:.*?\)\*", "", a).strip()
        rows.append((path.name, f"Question: {q}\nAnswer: {a}", "faq"))

    sections = [s.strip() for s in re.split(r"\n(?=## )", text) if s.strip()]
    for sec in sections:
        if sec.startswith("### Q:"):
            continue
        if len(sec) > 1500:
            for para in [p.strip() for p in sec.split("\n\n") if len(p.strip()) > 40]:
                rows.append((path.name, para, "kb"))
        else:
            rows.append((path.name, sec, "kb"))
    return rows


def _seed_faq_kb() -> None:
    from sentence_transformers import SentenceTransformer

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM faq_dataset WHERE tenant_id = ?", (TENANT_ID,))
    cur.execute("DELETE FROM knowledge_base WHERE tenant_id = ?", (TENANT_ID,))

    chunk_rows: list[tuple[str, str, str]] = []
    for path in sorted(KB_SRC.glob("*.md")):
        chunk_rows.extend(_chunk_markdown(path))

    print(f"embedding {len(chunk_rows)} chunks with {EMBEDDING_MODEL_PATH} ...")
    model = SentenceTransformer(EMBEDDING_MODEL_PATH)
    texts = [r[1] for r in chunk_rows]
    embeddings = model.encode(
        texts, batch_size=32, show_progress_bar=True, convert_to_numpy=True
    )
    embeddings = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10)

    for (src, content, module), emb in zip(chunk_rows, embeddings):
        cur.execute(
            """
            INSERT INTO faq_dataset (
                source_file, content_type, content, page_number,
                embedding, media_url, media_type, module, tenant_id, created_at
            ) VALUES (?, 'text', ?, 1, ?, NULL, NULL, ?, ?, CURRENT_TIMESTAMP)
            """,
            (src, content, emb.astype(np.float32).tobytes(), module, TENANT_ID),
        )

    # Also store full docs in knowledge_base for KB RAG surfaces
    for path in sorted(KB_SRC.glob("*.md")):
        body = path.read_text(encoding="utf-8")
        title = path.stem.replace("_", " ").title()
        cur.execute(
            """
            INSERT INTO knowledge_base (
                title, category, content, tags, source, chunks_json,
                embedding_blob, media_url, media_type, tenant_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, CURRENT_TIMESTAMP)
            """,
            (
                title,
                "automobile",
                body,
                "honda,cars,demo",
                path.name,
                "[]",
                TENANT_ID,
            ),
        )

    conn.commit()
    conn.close()
    print(f"faq_dataset + knowledge_base seeded ({len(chunk_rows)} chunks)")


def _publish_profile() -> None:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    profile = loader.validate_merged_profile(TENANT_ID, payload)
    store.save_draft(TENANT_ID, payload, updated_by="demo-setup")
    version = store.publish_version(TENANT_ID, payload, published_by="demo-setup")
    cache.purge(TENANT_ID)
    print(
        f"published {TENANT_ID} v{version} vertical={profile.vertical} "
        f"buttons={[b.id for b in profile.menu.visible_buttons(profile.features)]}"
    )


def _activate_for_demo() -> None:
    # Prefer DB helper used by the admin API.
    try:
        from database import set_active_test_tenant

        set_active_test_tenant(TENANT_ID)
    except Exception:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO app_settings(key, value) VALUES('active_test_tenant', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (TENANT_ID,),
        )
        conn.commit()
        conn.close()
    cache.purge(TENANT_ID)
    print("active_test_tenant =", TENANT_ID)


def _rebuild_indexes() -> None:
    try:
        from faq.service import faq_index

        faq_index.build(force=True)
        ntotal = faq_index.index.ntotal if faq_index.index else 0
        print("FAQ FAISS rebuilt, ntotal=", ntotal)
    except Exception as exc:
        print("WARN: FAQ index rebuild skipped:", exc)

    try:
        from kb.services.rag import rebuild_faiss_index

        rebuild_faiss_index()
        print("KB FAISS rebuild requested")
    except Exception as exc:
        print("WARN: KB index rebuild skipped:", exc)

    try:
        from kb.services.rag import rebuild_product_faiss_index

        rebuild_product_faiss_index()
        print("Product FAISS rebuild requested")
    except Exception as exc:
        print("WARN: product index rebuild skipped:", exc)


def main() -> int:
    os.chdir(REPO)
    print("DB_PATH =", DB_PATH)
    _ensure_tenant()
    _copy_knowledge()
    _seed_products()
    _seed_faq_kb()
    _publish_profile()
    _activate_for_demo()
    _rebuild_indexes()
    print("\nHonda automobile demo is ready.")
    print("WhatsApp 'Hi' on the shared number should route to Honda Cars.")
    print("Console login: admin1 / Admin@1234567  → Active Test Tenant = honda")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
