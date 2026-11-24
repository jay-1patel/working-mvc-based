"""Throwaway acceptance checks for crawl speed / limits / partial finish.

Not part of the permanent suite — run manually:
  python -m tests._acceptance_crawl_perf
"""
from __future__ import annotations

import os
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("CRAWL_URL_ALLOWLIST", "127.0.0.1,localhost")

from services import site_crawler as site_crawler_mod
from services.site_crawler import SiteCrawler, assert_public_url, BlockedUrlError


PAGE_COUNT = 200
ARTICLE = (
    "The blue widget is our most popular workshop tool. It is machined "
    "from a single block of anodised aluminium and finished by hand. "
    "Every widget passes a twelve point quality inspection before it "
    "leaves the factory floor and ships to customers worldwide."
)


class _Handler(BaseHTTPRequestHandler):
    pages: dict = {}
    sleep_s: float = 0.15

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        if self.path not in ("/robots.txt", "/sitemap.xml") and self.sleep_s:
            time.sleep(self.sleep_s)
        item = self.pages.get(self.path)
        if not item:
            self.send_response(404)
            self.end_headers()
            return
        ctype, body = item
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _build_site(base: str, n: int) -> dict:
    links = "\n".join(f'<a href="/page-{i}">Page {i}</a>' for i in range(1, n))
    home = f"""<!DOCTYPE html><html><head><title>Home</title></head><body>
      <h1>Acceptance Site</h1><p>{ARTICLE}</p><nav>{links}</nav>
      <a href="/private">Private</a>
      <a href="/offsite-hint">Offsite hint</a>
      </body></html>"""
    pages = {"/": ("text/html", home.encode())}
    for i in range(1, n):
        body = f"""<!DOCTYPE html><html><head><title>Page {i}</title></head><body>
          <h1>Page {i}</h1><p>{ARTICLE} Page number {i}.</p>
          <a href="/">Home</a></body></html>"""
        pages[f"/page-{i}"] = ("text/html", body.encode())
    # Include /private in the sitemap so the crawler dequeues it and
    # records robots.txt disallow (discovery-time skips are silent).
    locs = "\n".join(
        f"<url><loc>{base}{path}</loc></url>"
        for path in ["/"] + [f"/page-{i}" for i in range(1, n)] + ["/private"]
    )
    pages["/sitemap.xml"] = (
        "application/xml",
        (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{locs}\n</urlset>"
        ).encode(),
    )
    pages["/robots.txt"] = (
        "text/plain",
        # No blanket Allow: / — that can mask Disallow in some parsers.
        f"User-agent: *\nDisallow: /private\nSitemap: {base}/sitemap.xml\n".encode(),
    )
    pages["/private"] = (
        "text/html",
        b"<html><body><p>secret private page should be skipped</p></body></html>",
    )
    pages["/offsite-hint"] = (
        "text/html",
        b'<html><body><a href="https://evil.example/x">x</a><p>'
        + ARTICLE.encode()
        + b"</p></body></html>",
    )
    return pages


def _start_server(n: int = PAGE_COUNT, sleep_s: float = 0.2):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    host, port = server.server_address
    base = f"http://127.0.0.1:{port}"
    _Handler.pages = _build_site(base, n)
    _Handler.sleep_s = sleep_s
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, base


def inventory_signature(res: dict) -> set:
    return {
        (
            (item.get("url") or "").rstrip("/"),
            bool(item.get("success")),
            item.get("error") or "",
        )
        for item in res.get("inventory") or []
    }


def main():
    print("=== Acceptance 1: parallel vs sequential on ~200-page site ===")
    # Per-page latency above the polite delay so overlapping in-flight
    # requests (not just start-spacing) drives the speedup.
    server, base = _start_server(PAGE_COUNT, sleep_s=0.4)
    try:
        # Baseline: concurrency 1 approximates the old sequential crawler.
        with patch.object(site_crawler_mod, "CRAWL_CONCURRENCY", 1):
            t0 = time.perf_counter()
            old = SiteCrawler(
                base, request_delay=0.05, page_timeout=5.0, respect_robots=True,
            ).crawl()
            old_s = time.perf_counter() - t0
        old_sig = inventory_signature(old)

        t1 = time.perf_counter()
        new = SiteCrawler(
            base, request_delay=0.05, page_timeout=5.0, respect_robots=True,
        ).crawl()
        new_s = time.perf_counter() - t1
        new_sig = inventory_signature(new)

        speedup = old_s / new_s if new_s > 0 else float("inf")
        print(f"  pages crawled old={old['pages_crawled_count']} new={new['pages_crawled_count']}")
        print(f"  duration old={old_s:.2f}s new={new_s:.2f}s speedup={speedup:.2f}x")
        print(f"  inventory match={old_sig == new_sig} (old={len(old_sig)} new={len(new_sig)})")
        assert old["pages_crawled_count"] >= PAGE_COUNT
        assert new["pages_crawled_count"] == old["pages_crawled_count"]
        assert old_sig == new_sig, "inventory URLs/success mismatch"
        assert speedup >= 3.0, f"expected >=3x speedup, got {speedup:.2f}x"
        print("  PASS")
    finally:
        server.shutdown()

    print("=== Acceptance 2: max_pages=10 stops at 10 ===")
    server, base = _start_server(60, sleep_s=0.0)
    try:
        res = SiteCrawler(base, max_pages=10, request_delay=0.0).crawl()
        print(f"  pages_crawled_count={res['pages_crawled_count']} stop_reason={res.get('stop_reason')}")
        assert res["pages_crawled_count"] == 10
        errors = {i.get("error") for i in res["inventory"]}
        assert "not_fetched_max_pages" in errors
        print("  PASS")
    finally:
        server.shutdown()

    print("=== Acceptance 3: total_timeout → finished_partial keeps pages ===")
    # Use pipeline helper status mapping via SiteCrawler stop_reason.
    server, base = _start_server(80, sleep_s=0.05)
    try:
        with patch.dict(os.environ, {"CRAWL_TOTAL_TIMEOUT_SECONDS": "20"}):
            from services.crawl_pipeline import (
                DEFAULT_MAX_PAGES,
                _crawl_total_timeout_seconds,
            )
            assert _crawl_total_timeout_seconds() == 20.0
        res = SiteCrawler(
            base,
            max_pages=500,
            max_depth=6,
            total_timeout=2.0,
            request_delay=0.05,
        ).crawl()
        print(
            f"  stop_reason={res.get('stop_reason')} pages={res['pages_crawled_count']} "
            f"found={res['pages_found']}"
        )
        assert res.get("stop_reason") == "total_timeout"
        assert res["pages_crawled_count"] > 0
        # Pipeline would mark finished_partial and still stage — simulate the gate.
        final_status = "finished_partial" if res.get("stop_reason") == "total_timeout" else "done"
        assert final_status == "finished_partial"
        assert DEFAULT_MAX_PAGES == 500
        print("  PASS (partial pages kept; status would be finished_partial)")
    finally:
        server.shutdown()

    print("=== Acceptance 4: bifurcation budget scales with page count ===")
    from services.crawl_pipeline import _bifurcation_timeout_seconds
    with patch.dict(os.environ, {"CRAWL_BIFURCATION_TIMEOUT_SECONDS": "180"}, clear=False):
        b50 = _bifurcation_timeout_seconds(50)
        b500 = _bifurcation_timeout_seconds(500)
        b2000 = _bifurcation_timeout_seconds(2000)
    print(f"  budget pages=50 → {b50}s; pages=500 → {b500}s; pages=2000 → {b2000}s")
    assert b50 == 180.0
    assert b500 == 1000.0  # max(180, 2*500)
    assert b2000 == 1800.0  # capped
    # 500+ pages get >= 1000s — enough that heuristic_timeout is not the default path.
    assert b500 >= 1000
    print("  PASS (budget scales; LLM path keeps time for 500+ pages)")

    print("=== Acceptance 5: SSRF / robots / off-domain ===")
    server, base = _start_server(5, sleep_s=0.0)
    try:
        try:
            assert_public_url("http://127.0.0.1/")
            # allowlist is set — loopback allowed for fixtures. Use a private non-allowlisted IP.
        except BlockedUrlError:
            pass
        with patch.dict(os.environ, {"CRAWL_URL_ALLOWLIST": ""}, clear=False):
            blocked = False
            try:
                assert_public_url("http://127.0.0.1/")
            except BlockedUrlError:
                blocked = True
            assert blocked, "loopback must be blocked without allowlist"
            print("  loopback blocked without allowlist: OK")

        res = SiteCrawler(base, request_delay=0.0, max_pages=20).crawl()
        errors = {
            (item.get("url") or "", item.get("error") or "")
            for item in res["inventory"]
        }
        private_hit = any(
            u.rstrip("/").endswith("/private") and err == "robots.txt disallow"
            for u, err in errors
        )
        assert private_hit, f"robots disallow missing: {errors}"
        urls = {p["url"] for p in res["pages"]}
        assert not any("evil.example" in u for u in urls)
        print("  robots-disallow skipped; off-domain not followed: OK")
        print("  PASS")
    finally:
        server.shutdown()

    print("\nAll acceptance checks passed.")


if __name__ == "__main__":
    main()
