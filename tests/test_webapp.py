from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.webapp import create_app


class WebAppTests(unittest.TestCase):
    def test_api_cases_supports_review_flag_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            review = root / "review"
            review.mkdir()
            payload = {
                "source": {"file_name": "case_filter.pdf"},
                "document": {"case_number": "101/PUU/2025", "document_type": "putusan"},
                "parser": {"status": "partial", "failed_extractors": []},
                "validation": {"review_flags": ["decision_date_missing"], "needs_manual_review": True},
                "parties": {"applicants": [], "respondents": []},
                "outcome": {"summary": "Menolak permohonan"},
            }
            (review / "case_filter.json").write_text(json.dumps(payload), encoding="utf-8")

            app = create_app(parsed_dir=root / "parsed", validated_dir=root / "validated", review_dir=review)
            status_headers: dict[str, object] = {}

            def start_response(status: str, headers: list[tuple[str, str]]) -> None:
                status_headers["status"] = status
                status_headers["headers"] = headers

            body = b"".join(
                app(
                    {"PATH_INFO": "/api/cases", "QUERY_STRING": "review_flag=decision_date_missing"},
                    start_response,
                )
            )
            payload_out = json.loads(body.decode("utf-8"))

            self.assertEqual(status_headers["status"], "200 OK")
            self.assertEqual(len(payload_out["items"]), 1)
            self.assertEqual(payload_out["items"][0]["case_number"], "101/PUU/2025")

    def test_detail_page_contains_api_link_and_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            parsed = root / "parsed"
            parsed.mkdir()
            payload = {
                "source": {"file_name": "case_detail.pdf"},
                "document": {"case_number": "202/PUU/2025", "document_type": "putusan", "title": "Judul Uji Materi"},
                "parser": {"status": "partial", "failed_extractors": []},
                "validation": {"review_flags": ["respondent_count_high"], "needs_manual_review": True},
                "parties": {"applicants": [{"name": "Pemohon A"}], "respondents": [{"name": "DPR"}]},
                "outcome": {"summary": "Permohonan tidak dapat diterima", "dictum": ["Menolak permohonan"]},
                "sections": [{"heading": "Duduk Perkara", "text": "Narasi singkat"}],
            }
            (parsed / "case_detail.json").write_text(json.dumps(payload), encoding="utf-8")

            app = create_app(parsed_dir=parsed, validated_dir=root / "validated", review_dir=root / "review")
            status_headers: dict[str, object] = {}

            def start_response(status: str, headers: list[tuple[str, str]]) -> None:
                status_headers["status"] = status
                status_headers["headers"] = headers

            body = b"".join(app({"PATH_INFO": "/cases/case_detail", "QUERY_STRING": ""}, start_response)).decode("utf-8")

            self.assertEqual(status_headers["status"], "200 OK")
            self.assertIn("/api/cases/case_detail", body)
            self.assertIn("Sumber JSON", body)
            self.assertIn("Duduk Perkara", body)


if __name__ == "__main__":
    unittest.main()
