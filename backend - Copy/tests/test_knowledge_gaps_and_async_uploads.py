"""Tests for Background Async Document Ingestion and In-Dashboard Knowledge Gap Analytics.

Run under pytest after porting fixtures to ``mongo_test_support`` (SQLite removed).
"""

import os
import sys
import unittest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


@unittest.skip("SQLite pytest fixtures removed for MongoDB-only backend; port to mongomock")
class TestKnowledgeGapDatabase(unittest.TestCase):
    def test_record_and_list_unanswered_queries(self):
        pass


@unittest.skip("SQLite pytest fixtures removed for MongoDB-only backend; port to mongomock")
class TestAsyncFileUploads(unittest.TestCase):
    def test_save_and_update_admin_file_status(self):
        pass