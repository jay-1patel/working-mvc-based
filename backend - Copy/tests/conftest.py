"""Shared path setup for the backend test suite.

Tests live one level below the backend package. Put the backend folder
itself (for top-level application modules) and the project root (for
package-style imports) on sys.path before test modules are imported.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("ADMIN_SECRET_KEY", "test-admin-signing-key")
# Set before any test imports routing.config, which freezes DB_PATH at import.
os.environ["ROUTING_DB_PATH"] = "/tmp/wa-routing-test.sqlite3"

TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TESTS_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

for _path in (str(TESTS_DIR), str(BACKEND_DIR), str(PROJECT_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
