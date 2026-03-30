from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.webdata import build_case_catalog, build_dashboard_stats, filter_case_summaries, summarize_case


class WebDataTests(unittest.TestCase):
    def test_catalog_prefers_review_queue_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            parsed = root / "parsed"
            validated = root / "validated"
            review = root / "review"
            parsed.mkdir()
            validated.mkdir()
            review.mkdir()

            payload = {
                "source": {"file_name": "case_a.pdf"},
                "document": {"case_number": "1/PUU/2024", "document_type": "putusan"},
                "parser": {"status": "partial", "failed_extractors": []},
                "validation": {"review_flags": ["decision_date_missing"], "needs_manual_review": True},
                "parties": {"applicants": [], "respondents": []},
                "outcome": {"summary": "Menolak permohonan"},
            }
            (parsed / "case_a.json").write_text(json.dumps(payload), encoding="utf-8")
            (review / "case_a.json").write_text(json.dumps(payload), encoding="utf-8")

            catalog = build_case_catalog(parsed_dir=parsed, validated_dir=validated, review_dir=review)
            self.assertEqual(len(catalog), 1)
            self.assertEqual(catalog[0].source, "review_queue")

    def test_summary_and_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            parsed = root / "parsed"
            validated = root / "validated"
            review = root / "review"
            parsed.mkdir()
            validated.mkdir()
            review.mkdir()

            payload = {
                "source": {"file_name": "case_b.pdf"},
                "document": {"case_number": "225/PUU-XXIII/2025", "document_type": "putusan", "decision_date": None},
                "parser": {"status": "partial", "failed_extractors": []},
                "validation": {"review_flags": ["decision_date_missing"], "needs_manual_review": True},
                "parties": {"applicants": [{"name": "Andi"}], "respondents": [{"name": "DPR"}]},
                "outcome": {"summary": "Menyatakan permohonan tidak dapat diterima"},
            }
            (review / "case_b.json").write_text(json.dumps(payload), encoding="utf-8")

            summary = summarize_case(build_case_catalog(parsed_dir=parsed, validated_dir=validated, review_dir=review)[0])
            filtered = filter_case_summaries(
                [summary],
                query="225/PUU",
                status="partial",
                document_type="putusan",
                source="review_queue",
                review_flag="decision_date_missing",
            )
            stats = build_dashboard_stats(filtered)

            self.assertEqual(len(filtered), 1)
            self.assertEqual(stats["needs_review"], 1)
            self.assertEqual(stats["review_flag_counts"]["decision_date_missing"], 1)


if __name__ == "__main__":
    unittest.main()
