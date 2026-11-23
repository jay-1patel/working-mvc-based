from fastapi import APIRouter

from database import get_db
from db.core import use_mongodb

router = APIRouter()


@router.get("/faqs")
def get_faqs():
    """FAQ chunks for the admin view.

    Reads faq_dataset directly — the old services/rag.py InMemoryKB this used
    to call was a second, dead FAQ index (the live one is the hybrid FAQIndex
    in faq/service.py) and was removed in Phase 7b.
    """
    if use_mongodb():
        from db.mongo import Repository

        rows = Repository("faq_dataset").find_all(sort=[("id", 1)])
    else:
        conn = get_db()
        try:
            rows = conn.execute("SELECT * FROM faq_dataset").fetchall()
            rows = [dict(row) for row in rows]
        finally:
            conn.close()
    return {
        "faqs": [
            {
                "id": row["id"],
                "category": row["source_file"],
                "content": row["content"],
                "content_type": row["content_type"],
                "module": row["module"],
            }
            for row in rows
        ]
    }