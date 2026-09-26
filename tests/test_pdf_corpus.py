from __future__ import annotations

import json
from pathlib import Path
import unittest

from src.parser import MkriParser


ROOT = Path(__file__).parent
PDF_DIR = ROOT / "fixtures" / "pdfs"
GOLDEN = ROOT / "golden" / "pdf_corpus_summary.json"


def summarize(payload: dict) -> dict:
    return {
        "document_type": payload["document"]["document_type"],
        "case_number": payload["document"]["case_number"],
        "decision_date": payload["document"]["decision_date"],
        "judges": payload["adjudicators"]["judges"],
        "clerks": payload["adjudicators"]["clerks"],
        "applicant_count": len(payload["parties"]["applicants"]),
        "legal_counsel_count": len(payload["parties"]["legal_counsels"]),
        "respondent_count": len(payload["parties"]["respondents"]),
        "expert_count": len(payload["parties"]["experts"]),
        "witness_count": len(payload["parties"]["witnesses"]),
        "amicus_count": len(payload["parties"]["amicus_curiae"]),
        "outcome_summary": payload["outcome"]["summary"],
    }


class PdfCorpusGoldenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = MkriParser()

    def test_pdf_corpus_snapshot(self) -> None:
        pdfs = sorted(PDF_DIR.glob("*.pdf"))
        if not pdfs:
            self.skipTest("local PDF fixtures are not available")
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
        got: dict[str, dict] = {}
        for pdf_path in pdfs:
            record = self.parser.parse_pdf(pdf_path)
            got[pdf_path.name] = summarize(record.to_dict())
        self.assertEqual(got, expected)


if __name__ == "__main__":
    unittest.main()
