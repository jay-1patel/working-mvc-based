"""Throwaway: pipeline total_timeout → finished_partial with staged payload."""
from __future__ import annotations

import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
sys.path[:0] = [BACKEND_DIR, os.path.join(BACKEND_DIR, "tests"), PROJECT_ROOT]

os.environ.setdefault("CRAWL_URL_ALLOWLIST", "127.0.0.1,localhost")
os.environ["CRAWL_TOTAL_TIMEOUT_SECONDS"] = "3"
os.environ.setdefault("SCRAPER_JS_RENDER", "off")

from mongo_test_support import MongomockSession
import database
from services.crawl_pipeline import run_crawl_pipeline

ARTICLE = "The blue widget is our most popular workshop tool. " * 5


class H(BaseHTTPRequestHandler):
    pages: dict = {}

    def log_message(self, *a):
        return

    def do_GET(self):
        if self.path not in ("/robots.txt", "/sitemap.xml"):
            time.sleep(0.25)
        item = self.pages.get(self.path)
        if not item:
            self.send_response(404)
            self.end_headers()
            return
        ct, body = item
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), H)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    links = "".join(f'<a href="/p{i}">p{i}</a>' for i in range(40))
    pages = {
        "/": (
            "text/html",
            f"<html><body><h1>Home</h1><p>{ARTICLE}</p>{links}</body></html>".encode(),
        ),
        "/robots.txt": ("text/plain", b"User-agent: *\nDisallow:\n"),
    }
    for i in range(40):
        pages[f"/p{i}"] = (
            "text/html",
            f"<html><body><h1>P{i}</h1><p>{ARTICLE}</p></body></html>".encode(),
        )
    locs = "".join(f"<url><loc>{base}/p{i}</loc></url>" for i in range(40))
    pages["/sitemap.xml"] = (
        "application/xml",
        f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>'.encode(),
    )
    H.pages = pages
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        with MongomockSession():
            database.init_db()
            from shared.tenancy import store as tenancy_store

            tenancy_store.ensure_tenant(
                tenant_id="acc-partial",
                slug="acc-partial",
                vertical="generic",
                display_name="Acc",
                status="active",
            )
            run = database.create_crawl_run(
                "acc-partial", base, trigger="manual", created_by="test"
            )
            fake = {
                "brand": {"name": "Acc"},
                "offerings": [],
                "faqs": [],
                "knowledge_articles": [],
                "bifurcation_source": "llm",
            }
            with patch(
                "services.url_scraper.UrlAutoOnboarder.extract_bifurcation",
                return_value=fake,
            ):
                result = run_crawl_pipeline(
                    tenant_id="acc-partial",
                    url=base,
                    run_id=run["id"],
                    max_pages=500,
                    max_depth=6,
                    actor={
                        "username": "test",
                        "role": "admin",
                        "tenant_id": "acc-partial",
                    },
                )
            detail = database.get_crawl_run(run["id"], "acc-partial")
            staged = database.get_crawl_staged(run["id"], "acc-partial")
            print(
                "status", result["status"],
                "pages", result.get("pages_scraped"),
                "stop", result.get("stop_reason"),
            )
            print(
                "db_status", detail["status"],
                "staged", staged["status"] if staged else None,
                "pages_found", detail["pages_found"],
            )
            assert result["status"] == "finished_partial"
            assert detail["status"] == "finished_partial"
            assert staged and staged["status"] == "staged"
            assert (result.get("pages_scraped") or 0) > 0
            print("PIPELINE_PARTIAL_OK")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
