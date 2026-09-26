from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.webapp import create_app


class WebAppTests(unittest.TestCase):
    def test_dashboard_uses_human_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            review = root / "review"
            review.mkdir()
            payload = {
                "source": {"file_name": "case_dashboard.pdf"},
                "document": {"case_number": "303/PUU/2025", "document_type": "putusan"},
                "parser": {"status": "partial", "failed_extractors": []},
                "validation": {"review_flags": ["decision_date_missing"], "needs_manual_review": True},
                "parties": {"applicants": [], "respondents": []},
                "outcome": {"summary": "Menolak permohonan"},
            }
            (review / "case_dashboard.json").write_text(json.dumps(payload), encoding="utf-8")

            app = create_app(parsed_dir=root / "parsed", validated_dir=root / "validated", review_dir=review)
            status_headers: dict[str, object] = {}

            def start_response(status: str, headers: list[tuple[str, str]]) -> None:
                status_headers["status"] = status
                status_headers["headers"] = headers

            body = b"".join(app({"PATH_INFO": "/cases", "QUERY_STRING": ""}, start_response)).decode("utf-8")

            self.assertEqual(status_headers["status"], "200 OK")
            self.assertIn("Daftar Perkara MKRI", body)
            self.assertIn("Status Parse", body)
            self.assertIn("Terapkan", body)
            self.assertIn("Tanggal putusan belum terbaca", body)
            self.assertIn("Perlu review", body)

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
                "proceedings": ["sidang pleno", "rapat permusyawaratan hakim"],
                "relations": {"joined_cases": ["100/PUU/2025"], "referenced_cases": ["50/PUU/2024"]},
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
            self.assertIn("https://www.mkri.id/perkara/persidangan/putusan?search=202%2FPUU%2F2025&amp;jenis=PUU", body)
            self.assertIn("https://tracking.mkri.id/index.php?id=202%2FPUU%2F2025&amp;page=web.TrackPerkara", body)
            self.assertIn("Duduk Perkara", body)
            self.assertIn("sidang pleno", body)
            self.assertIn("100/PUU/2025", body)

    def test_detail_page_hides_noisy_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            review = root / "review"
            review.mkdir()
            payload = {
                "source": {"file_name": "case_noisy.pdf"},
                "document": {
                    "case_number": "225/PUU-XXIII/2025",
                    "document_type": "putusan",
                    "case_type": "PUU",
                    "decision_date_raw": "18 Tahun 2003",
                },
                "parser": {"status": "partial", "failed_extractors": []},
                "validation": {"review_flags": ["decision_date_missing"], "needs_manual_review": True},
                "parties": {
                    "applicants": [{"name": "Dr. Togar Situmorang"}],
                    "legal_counsels": [{"name": "Axl Mattew Situmorang"}],
                    "respondents": [{"name": "Presiden"}, {"name": "Pemerintah"}],
                },
                "adjudicators": {
                    "judges": [
                        "paragraf panjang yang seharusnya tidak tampil sebagai nama hakim karena ini narasi penuh dari putusan",
                        "Saldi Isra",
                    ],
                    "clerks": ["Dian Chusnul Chatimah"],
                },
                "legal_basis": {
                    "constitutional_articles": ["Pasal 24C ayat (1)", "Pasal 28D ayat (1)", "PASAL 28", "Pasal sangat panjang yang seharusnya dibuang dari tampilan viewer karena noisy sekali"],
                    "procedural_articles": ["Pasal 4 ayat (2)", "Pasal 36 ayat (3)"],
                    "evidence": ["BUKTI P-1", "BUKTI P-2", "REFERENSI:230/PUU/PAN.MK/AP3/11/2025"],
                },
                "outcome": {"summary": "Permohonan tidak dapat diterima", "dictum": ["Menyatakan permohonan Pemohon tidak dapat diterima."]},
                "proceedings": [
                    "sidang pleno",
                    "rapat permusyawaratan hakim",
                    "DALAM HAL PEMERIKSAAN FRASA ITIKAD BAIK YANG SEHARUSNYA TIDAK TAMPIL PANJANG DI VIEWER",
                ],
                "relations": {
                    "joined_cases": ["225/PUU-XXIII/2025", "230/PUU/PAN.MK/AP3/11/2025"],
                    "referenced_cases": ["93/PUU-XV/2017", "referensi sangat panjang yang tidak boleh lolos ke panel relasi viewer"],
                },
                "sections": [
                    {"heading": "PUTUSAN", "text": "Nomor 225/PUU-XXIII/2025"},
                    {"heading": "Duduk Perkara", "text": "Narasi singkat"},
                    {"heading": "Kalimat heading palsu yang sangat panjang dan seharusnya tidak dipakai sebagai chip viewer", "text": "noise"},
                ],
            }
            (review / "case_noisy.json").write_text(json.dumps(payload), encoding="utf-8")

            app = create_app(parsed_dir=root / "parsed", validated_dir=root / "validated", review_dir=review)
            status_headers: dict[str, object] = {}

            def start_response(status: str, headers: list[tuple[str, str]]) -> None:
                status_headers["status"] = status
                status_headers["headers"] = headers

            body = b"".join(app({"PATH_INFO": "/cases/case_noisy", "QUERY_STRING": ""}, start_response)).decode("utf-8")

            self.assertEqual(status_headers["status"], "200 OK")
            self.assertIn("perlu review", body)
            self.assertIn("Saldi Isra", body)
            self.assertIn("Dian Chusnul Chatimah", body)
            self.assertIn("BUKTI P-1", body)
            self.assertIn("93/PUU-XV/2017", body)
            self.assertIn("Catatan Viewer", body)
            self.assertNotIn("paragraf panjang yang seharusnya tidak tampil", body)
            self.assertNotIn("REFERENSI:230/PUU/PAN.MK/AP3/11/2025", body)
            # The reader preview hides noisy headings; the explicitly labelled
            # raw-text disclosure preserves the complete source for inspection.
            preview, raw_text = body.split('<details id="teks-dokumen"', 1)
            self.assertNotIn("heading palsu yang sangat panjang", preview)
            self.assertIn("heading palsu yang sangat panjang", raw_text)


if __name__ == "__main__":
    unittest.main()
