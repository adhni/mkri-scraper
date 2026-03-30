from __future__ import annotations

import json
from pathlib import Path
import unittest

from src.models import SourceInfo
from src.parser import MkriParser
from src.normalizers import normalize_case_number, normalize_indonesian_date, normalize_party_name
from src.validators import collect_review_flags
from src.manual_truth import build_manual_truth_template


ROOT = Path(__file__).parent


def compact(payload: dict) -> dict:
    return {
        "document": {
            "document_type": payload["document"]["document_type"],
            "case_type": payload["document"]["case_type"],
            "case_number": payload["document"]["case_number"],
            "related_case_numbers": payload["document"]["related_case_numbers"],
        },
        "parser": {
            "status": payload["parser"]["status"],
            "warnings": payload["parser"]["warnings"],
            "failed_extractors": payload["parser"]["failed_extractors"],
        },
        "parties": {
            "applicants": [item["name"] for item in payload["parties"]["applicants"]],
            "legal_counsels": [item["name"] for item in payload["parties"]["legal_counsels"]],
            "respondents": [item["name"] for item in payload["parties"]["respondents"]],
            "experts": [item["name"] for item in payload["parties"]["experts"]],
            "witnesses": [item["name"] for item in payload["parties"]["witnesses"]],
            "amicus_curiae": [item["name"] for item in payload["parties"]["amicus_curiae"]],
        },
        "legal_basis": {
            "object_of_review": payload["legal_basis"]["object_of_review"],
            "constitutional_articles": payload["legal_basis"]["constitutional_articles"],
            "procedural_articles": payload["legal_basis"]["procedural_articles"],
            "evidence": payload["legal_basis"]["evidence"],
        },
        "proceedings": payload["proceedings"],
        "outcome": payload["outcome"],
        "relations": payload["relations"],
        "sections": [item["slug"] for item in payload["sections"]],
    }


class ParserGoldenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = MkriParser()

    def test_putusan_golden(self) -> None:
        text = (ROOT / "fixtures" / "sample_putusan.txt").read_text(encoding="utf-8")
        payload = self.parser.parse_text(text, SourceInfo(pdf_path="sample_putusan.pdf", file_name="sample_putusan.pdf"))
        got = compact(payload.to_dict())
        expected = json.loads((ROOT / "golden" / "sample_putusan.compact.json").read_text(encoding="utf-8"))
        self.assertEqual(got, expected)

    def test_ketetapan_golden(self) -> None:
        text = (ROOT / "fixtures" / "sample_ketetapan.txt").read_text(encoding="utf-8")
        payload = self.parser.parse_text(text, SourceInfo(pdf_path="sample_ketetapan.pdf", file_name="sample_ketetapan.pdf"))
        got = compact(payload.to_dict())
        expected = json.loads((ROOT / "golden" / "sample_ketetapan.compact.json").read_text(encoding="utf-8"))
        self.assertEqual(got, expected)

    def test_normalizers(self) -> None:
        self.assertEqual(normalize_case_number("Nomor 12/PUU-XX/2024"), "12/PUU-XX/2024")
        self.assertEqual(normalize_indonesian_date("12 maret 2024"), "2024-03-12")
        self.assertEqual(normalize_party_name("Pemohon: PT Contoh"), "PT Contoh")

    def test_review_flags_detect_suspicious_output(self) -> None:
        payload = {
            "document": {"document_type": "putusan", "decision_date": None},
            "parties": {
                "applicants": [{"name": "Andi", "role": "applicant"}],
                "legal_counsels": [],
                "respondents": [],
                "experts": [],
                "witnesses": [],
                "amicus_curiae": [],
            },
            "outcome": {"summary": "berdasarkan pertimbangan hukum di atas", "dictum": ["berdasarkan pertimbangan hukum di atas"]},
            "legal_basis": {"constitutional_articles": [], "procedural_articles": [], "object_of_review": [], "evidence": []},
            "adjudicators": {"judges": [], "clerks": []},
            "sections": [{"heading": "Pembuka", "slug": "pembuka", "text": "..."}, {"heading": "Menimbang", "slug": "menimbang", "text": "..."}],
        }
        flags = collect_review_flags(payload)
        self.assertIn("decision_date_missing", flags)
        self.assertIn("judges_not_extracted", flags)
        self.assertIn("outcome_summary_not_in_amar_style", flags)
        self.assertIn("constitutional_articles_missing_for_putusan", flags)

    def test_manual_truth_template(self) -> None:
        payload = {
            "source": {"file_name": "sample.pdf"},
            "document": {"document_type": "putusan", "case_number": "12/PUU-XX/2024", "decision_date": "2024-03-12"},
            "parties": {
                "applicants": [{"name": "Andi", "role": "applicant"}],
                "legal_counsels": [{"name": "Budi", "role": "legal_counsel"}],
                "respondents": [{"name": "DPR", "role": "respondent"}],
            },
            "legal_basis": {"constitutional_articles": ["Pasal 28D ayat (1)"], "procedural_articles": [], "object_of_review": [], "evidence": []},
            "outcome": {"summary": "Menolak permohonan", "dictum": ["Menolak permohonan"]},
        }
        template = build_manual_truth_template(payload)
        self.assertEqual(template["source_file"], "sample.pdf")
        self.assertEqual(template["verified_fields"]["case_number"], "12/PUU-XX/2024")
        self.assertEqual(template["verified_fields"]["applicants"], ["Andi"])


if __name__ == "__main__":
    unittest.main()
