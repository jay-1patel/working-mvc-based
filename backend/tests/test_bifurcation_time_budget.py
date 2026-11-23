"""The local document bifurcator must honor its whole-document time budget."""

import os
import sys
import unittest
from unittest.mock import patch


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services import auto_bifurcator as module  # noqa: E402
from services.auto_bifurcator import AutoBifurcator  # noqa: E402


class BifurcationTimeBudgetTests(unittest.TestCase):
    def test_stops_starting_windows_after_total_budget(self):
        bifurcator = AutoBifurcator("acme")
        with (
            patch.dict(
                os.environ,
                {
                    "BIFURCATE_PROVIDER": "ollama",
                    "BIFURCATE_TOTAL_TIMEOUT_SECONDS": "10",
                },
                clear=False,
            ),
            patch.object(module, "heuristic_extract_corpus", return_value={}),
            patch.object(module, "_chunk_text", return_value=["one", "two", "three"]),
            patch.object(module, "merge_bifurcation_results", return_value={}),
            patch.object(bifurcator, "_bifurcation_system_prompt", return_value="system"),
            patch.object(
                bifurcator,
                "_call_llm_json",
                return_value={"knowledge_articles": []},
            ) as call,
            patch.object(module.time, "monotonic", side_effect=[0.0, 0.0, 11.0]),
        ):
            result = bifurcator.bifurcate_with_llm(
                [{"filename": "kit.txt", "text": "content"}]
            )

        self.assertEqual(call.call_count, 1)
        self.assertTrue(result["_llm_ok"])
        self.assertLessEqual(call.call_args.kwargs["timeout_override"], 10.0)

    def test_uses_fast_configurable_chunk_size(self):
        bifurcator = AutoBifurcator("acme")
        with (
            patch.dict(
                os.environ,
                {
                    "BIFURCATE_CHUNK_CHARS": "18000",
                    "BIFURCATE_CHUNK_OVERLAP": "250",
                },
                clear=False,
            ),
            patch.object(module, "heuristic_extract_corpus", return_value={}),
            patch.object(module, "_chunk_text", return_value=[]) as chunk,
            patch.object(module, "merge_bifurcation_results", return_value={}),
        ):
            bifurcator.bifurcate_with_llm(
                [{"filename": "kit.txt", "text": "content"}]
            )

        self.assertEqual(chunk.call_args.kwargs, {"size": 18000, "overlap": 250})


if __name__ == "__main__":
    unittest.main()
