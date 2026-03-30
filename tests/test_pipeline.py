from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.pipeline import summarize_json_directory
from src.reporting import build_pipeline_report, write_pipeline_report


class PipelineSummaryTests(unittest.TestCase):
    def test_summarize_json_directory_counts_status_and_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload_ok = {
                "document": {"document_type": "putusan"},
                "parser": {"status": "ok", "failed_extractors": []},
                "validation": {"review_flags": [], "needs_manual_review": False},
            }
            payload_partial = {
                "document": {"document_type": "ketetapan"},
                "parser": {"status": "partial", "failed_extractors": ["outcome"]},
                "validation": {"review_flags": ["decision_date_missing"], "needs_manual_review": True},
            }
            (root / "a.json").write_text(json.dumps(payload_ok), encoding="utf-8")
            (root / "b.json").write_text(json.dumps(payload_partial), encoding="utf-8")

            summary = summarize_json_directory(root)
            self.assertEqual(summary["file_count"], 2)
            self.assertEqual(summary["status_counts"]["ok"], 1)
            self.assertEqual(summary["status_counts"]["partial"], 1)
            self.assertEqual(summary["document_type_counts"]["putusan"], 1)
            self.assertEqual(summary["document_type_counts"]["ketetapan"], 1)
            self.assertEqual(summary["review_flag_counts"]["decision_date_missing"], 1)
            self.assertEqual(summary["failed_extractor_counts"]["outcome"], 1)
            self.assertEqual(summary["files_needing_review"], ["b.json"])

    def test_write_pipeline_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            parsed = root / "parsed"
            validated = root / "validated"
            review = root / "review"
            parsed.mkdir()
            validated.mkdir()
            review.mkdir()

            sample = {
                "document": {"document_type": "putusan"},
                "parser": {"status": "ok", "failed_extractors": []},
                "validation": {"review_flags": [], "needs_manual_review": False},
            }
            (parsed / "a.json").write_text(json.dumps(sample), encoding="utf-8")
            (validated / "a.json").write_text(json.dumps(sample), encoding="utf-8")

            report = build_pipeline_report(parsed_dir=parsed, validated_dir=validated, review_dir=review)
            self.assertEqual(report["parsed"]["file_count"], 1)
            self.assertEqual(report["review_queue"]["file_count"], 0)

            output_path = root / "reports" / "latest.json"
            written = write_pipeline_report(output_path, parsed_dir=parsed, validated_dir=validated, review_dir=review)
            self.assertEqual(written, output_path)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["validated"]["file_count"], 1)


if __name__ == "__main__":
    unittest.main()
