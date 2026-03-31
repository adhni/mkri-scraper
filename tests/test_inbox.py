from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.inbox import ingest_inbox


class InboxTests(unittest.TestCase):
    def test_ingest_inbox_processes_and_moves_new_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            inbox = root / "inbox"
            processed = root / "processed"
            failed = root / "failed"
            review = root / "review"
            manifest = root / "manifest.json"
            inbox.mkdir()
            pdf_path = inbox / "case-a.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 sample")

            fake_ingest = {
                "pdf_inputs": [str(pdf_path)],
                "parse_outputs": [str(root / "parsed" / "case-a.json")],
                "validate_outputs": [str(root / "review" / "case-a.json")],
                "manual_truth_outputs": [],
                "failures": [],
                "parsed_summary": {},
                "review_summary": {},
                "validated_summary": {},
            }

            with patch("src.inbox.ingest_pdf_files", return_value=fake_ingest):
                result = ingest_inbox(
                    inbox_dir=inbox,
                    processed_dir=processed,
                    failed_dir=failed,
                    manifest_path=manifest,
                    review_dir=review,
                )

            self.assertEqual(result["processed_count"], 1)
            self.assertEqual(result["review_count"], 1)
            self.assertFalse(pdf_path.exists())
            self.assertTrue((processed / "case-a.pdf").exists())
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["files"]), 1)

    def test_ingest_inbox_skips_same_file_hash_on_second_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            inbox = root / "inbox"
            processed = root / "processed"
            failed = root / "failed"
            manifest = root / "manifest.json"
            inbox.mkdir()
            sample_bytes = b"%PDF-1.4 duplicate"

            fake_ingest = {
                "pdf_inputs": [],
                "parse_outputs": [str(root / "parsed" / "case-b.json")],
                "validate_outputs": [str(root / "validated" / "case-b.json")],
                "manual_truth_outputs": [],
                "failures": [],
                "parsed_summary": {},
                "review_summary": {},
                "validated_summary": {},
            }

            with patch("src.inbox.ingest_pdf_files", return_value=fake_ingest) as ingest_mock:
                first_pdf = inbox / "case-b.pdf"
                first_pdf.write_bytes(sample_bytes)
                first_result = ingest_inbox(
                    inbox_dir=inbox,
                    processed_dir=processed,
                    failed_dir=failed,
                    manifest_path=manifest,
                )
                second_pdf = inbox / "case-b-copy.pdf"
                second_pdf.write_bytes(sample_bytes)
                second_result = ingest_inbox(
                    inbox_dir=inbox,
                    processed_dir=processed,
                    failed_dir=failed,
                    manifest_path=manifest,
                )

            self.assertEqual(first_result["processed_count"], 1)
            self.assertEqual(second_result["processed_count"], 0)
            self.assertEqual(second_result["skipped_count"], 1)
            self.assertEqual(ingest_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
