"""Regression: onboarding-kit PDFs must bifurcate into FAQ and KB derivatives."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

KIT_DIR = Path(PROJECT_ROOT) / "onboarding_kit_examples"

# Kits that embed a real FAQ block (Customer Question / [SECTION: FAQS]).
KITS_EXPECTING_FAQ = (
    "it_software_onboarding_kit.pdf",
    "ecommerce_onboarding_kit.pdf",
    "banking_onboarding_kit.pdf",
    "generic_onboarding_kit.pdf",
    "healthcare_onboarding_kit.pdf",
    "finance_onboarding_kit.pdf",
    "real_estate_onboarding_kit.pdf",
    "tours_travel_onboarding_kit.pdf",
)

# Kits that also embed Knowledge Article / INFO content on a shared or later page.
KITS_EXPECTING_KB = (
    "it_software_onboarding_kit.pdf",
    "ecommerce_onboarding_kit.pdf",
    "banking_onboarding_kit.pdf",
    "generic_onboarding_kit.pdf",
    "healthcare_onboarding_kit.pdf",
    "finance_onboarding_kit.pdf",
    "real_estate_onboarding_kit.pdf",
    "tours_travel_onboarding_kit.pdf",
)


@unittest.skipUnless(KIT_DIR.is_dir(), "onboarding_kit_examples not present")
class PdfSectionBifurcationTests(unittest.TestCase):
    def test_kit_pdfs_produce_faq_and_kb_derivatives(self):
        try:
            import fitz  # noqa: F401
        except ImportError:
            self.skipTest("PyMuPDF not installed")

        from services.pdf_section_extractor import extract_sections_from_pdf

        failures = []
        for name in KITS_EXPECTING_FAQ:
            pdf = KIT_DIR / name
            if not pdf.exists():
                failures.append(f"{name}: missing fixture")
                continue
            with tempfile.TemporaryDirectory() as tmp:
                faq_path, kb_path = extract_sections_from_pdf(
                    source_path=str(pdf),
                    output_dir=tmp,
                    base_name=pdf.stem,
                )
                if name in KITS_EXPECTING_FAQ and not faq_path:
                    failures.append(f"{name}: expected FAQ PDF, got none")
                if name in KITS_EXPECTING_KB and not kb_path:
                    failures.append(f"{name}: expected KB PDF, got none")

        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_catalog_preview_does_not_wipe_faq_on_same_page(self):
        """Banking kit page mixes catalog image preview + FAQS section."""
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF not installed")

        from services.pdf_section_extractor import _compute_page_scores

        pdf = KIT_DIR / "banking_onboarding_kit.pdf"
        if not pdf.exists():
            self.skipTest("banking kit missing")

        doc = fitz.open(str(pdf))
        try:
            # Page 3 (index 2) has "Catalog images" then [SECTION: FAQS & POLICIES]
            faq_s, kb_s = _compute_page_scores(doc[2], 2)
        finally:
            doc.close()

        self.assertGreaterEqual(
            faq_s,
            8,
            msg=f"FAQ score wiped on catalog+FAQ page (faq={faq_s}, kb={kb_s})",
        )

    def test_mixed_faq_kb_page_can_enter_both_buckets(self):
        try:
            import fitz  # noqa: F401
        except ImportError:
            self.skipTest("PyMuPDF not installed")

        from services.pdf_section_extractor import extract_sections_from_pdf

        pdf = KIT_DIR / "ecommerce_onboarding_kit.pdf"
        if not pdf.exists():
            self.skipTest("ecommerce kit missing")

        with tempfile.TemporaryDirectory() as tmp:
            faq_path, kb_path = extract_sections_from_pdf(
                source_path=str(pdf),
                output_dir=tmp,
                base_name=pdf.stem,
            )
        self.assertTrue(faq_path, "mixed FAQ+article page must still yield FAQ PDF")
        self.assertTrue(kb_path, "mixed FAQ+article page must still yield KB PDF")


if __name__ == "__main__":
    unittest.main()
