from __future__ import annotations

import json
from pathlib import Path
import unittest

from src.models import SourceInfo
from src.parser import MkriParser
from src.normalizers import normalize_case_number, normalize_indonesian_date, normalize_party_name


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


if __name__ == "__main__":
    unittest.main()

