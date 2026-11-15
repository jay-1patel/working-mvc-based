"""A split PDF must remain discoverable by the upload completion poll."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT), str(ROOT / "routing")]


class UploadParentRetentionTests(unittest.TestCase):
    def test_split_keeps_original_ready_row_and_bifurcation_stats(self):
        from routes import admin

        rows = {"catalog.pdf": {"status": "processing"}}
        stats = {"status": "configured", "offerings_created": 1}

        def update(name, **values):
            rows[name].update(values)

        def split(**kwargs):
            if kwargs.get("cleanup_original", True):
                rows.pop(kwargs["original_filename"], None)
            return {"faq_pdf": "catalog_faq.pdf", "kb_pdf": "catalog_kb.pdf"}

        modules = {
            "services.upload_auto_router": SimpleNamespace(route_uploaded_document=Mock(return_value=stats)),
            "services.pdf_section_extractor": SimpleNamespace(auto_extract_and_register=Mock(side_effect=split)),
            "faq.service": SimpleNamespace(faq_index=Mock()),
            "kb.services.brain": SimpleNamespace(clear_response_cache=Mock()),
        }
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "catalog.pdf"
            source.write_bytes(b"test document")
            with patch.dict(sys.modules, modules), patch.dict(os.environ, {"AUTO_BIFURCATE": "0"}), \
                 patch.object(admin, "process_file", return_value={"pages": ["content"]}), \
                 patch.object(admin, "results_to_chunks", return_value=[{"content": "content"}]), \
                 patch.object(admin, "delete_file_chunks"), \
                 patch.object(admin, "delete_knowledge_base_file"), \
                 patch.object(admin, "save_chunks"), \
                 patch.object(admin, "update_admin_file_status", side_effect=update):
                admin._process_document_background(
                    str(source), "catalog.pdf", ".pdf", "faq", "", "pdf", "test-tenant"
                )
        self.assertIn("catalog.pdf", rows)
        self.assertEqual(rows["catalog.pdf"]["status"], "ready")
        self.assertEqual(rows["catalog.pdf"]["bifurcation_stats"], stats)
        modules["services.pdf_section_extractor"].auto_extract_and_register.assert_called_once()


if __name__ == "__main__":
    unittest.main()
