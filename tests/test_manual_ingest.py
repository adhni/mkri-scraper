from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.discovery import ingest_decision_url, ingest_tracking_html_file


SAMPLE_TRACKING_HTML = """
<html>
  <body>
    <div>No Perkara : 6/PUU-XXIII/2025</div>
    <div>Pokok Perkara : Pengujian Materiil Undang-Undang Nomor 6 Tahun 2023</div>
    <div>Pemohon : Putra Arista Pratama</div>
    <a href="http://www.mkri.id/index.php?page=download.Putusan&id=5072">File Putusan</a>
  </body>
</html>
"""


class ManualIngestTests(unittest.TestCase):
    def test_ingest_tracking_html_file_writes_snapshot_and_ingests_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            html_path = root / "case6.html"
            html_path.write_text(SAMPLE_TRACKING_HTML, encoding="utf-8")
            pdf_dir = root / "pdfs"
            parsed_dir = root / "parsed"
            validated_dir = root / "validated"
            review_dir = root / "review"
            html_dir = root / "html_out"
            snapshot_dir = root / "snapshots"

            def fake_download(url: str, destination: str | Path, timeout: float = 30.0) -> Path:
                destination = Path(destination)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"%PDF-1.4")
                return destination

            fake_ingest = {
                "pdf_inputs": [str(pdf_dir / "6_PUU-XXIII_2025.pdf")],
                "parse_outputs": ["parsed.json"],
                "validate_outputs": ["review.json"],
                "manual_truth_outputs": [],
                "failures": [],
                "parsed_summary": {},
                "review_summary": {},
                "validated_summary": {},
            }

            with patch("src.discovery.download_binary", side_effect=fake_download), patch(
                "src.discovery.ingest_pdf_files",
                return_value=fake_ingest,
            ) as ingest_mock:
                result = ingest_tracking_html_file(
                    html_path=html_path,
                    html_dir=html_dir,
                    snapshot_dir=snapshot_dir,
                    pdf_dir=pdf_dir,
                    parsed_dir=parsed_dir,
                    validated_dir=validated_dir,
                    review_dir=review_dir,
                    force=True,
                )

            self.assertEqual(result["case_number"], "6/PUU-XXIII/2025")
            self.assertTrue((html_dir / "6_PUU-XXIII_2025.html").exists())
            self.assertTrue((snapshot_dir / "6_PUU-XXIII_2025.json").exists())
            self.assertEqual(ingest_mock.call_args.kwargs["pdf_paths"], [pdf_dir / "6_PUU-XXIII_2025.pdf"])
            self.assertEqual(result["ingest"], fake_ingest)

    def test_ingest_decision_url_downloads_then_ingests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            pdf_dir = root / "pdfs"

            def fake_download(url: str, destination: str | Path, timeout: float = 30.0) -> Path:
                destination = Path(destination)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"%PDF-1.4")
                return destination

            fake_ingest = {
                "pdf_inputs": [str(pdf_dir / "6_PUU-XXIII_2025.pdf")],
                "parse_outputs": ["parsed.json"],
                "validate_outputs": ["review.json"],
                "manual_truth_outputs": [],
                "failures": [],
                "parsed_summary": {},
                "review_summary": {},
                "validated_summary": {},
            }

            with patch("src.discovery.download_binary", side_effect=fake_download), patch(
                "src.discovery.ingest_pdf_files",
                return_value=fake_ingest,
            ) as ingest_mock:
                result = ingest_decision_url(
                    case_number="6/PUU-XXIII/2025",
                    decision_url="http://www.mkri.id/index.php?page=download.Putusan&id=5072",
                    pdf_dir=pdf_dir,
                    force=True,
                )

            self.assertEqual(result["downloaded_pdf"], str(pdf_dir / "6_PUU-XXIII_2025.pdf"))
            self.assertEqual(ingest_mock.call_args.kwargs["pdf_paths"], [pdf_dir / "6_PUU-XXIII_2025.pdf"])
            self.assertEqual(result["ingest"], fake_ingest)

    def test_ingest_decision_url_can_use_browser_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            pdf_dir = root / "pdfs"

            class FakeBrowserSession:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb) -> None:
                    return None

                def download_url(self, target_url: str, destination: str | Path) -> Path:
                    destination = Path(destination)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(b"%PDF-1.4")
                    return destination

            fake_ingest = {
                "pdf_inputs": [str(pdf_dir / "6_PUU-XXIII_2025.pdf")],
                "parse_outputs": ["parsed.json"],
                "validate_outputs": ["review.json"],
                "manual_truth_outputs": [],
                "failures": [],
                "parsed_summary": {},
                "review_summary": {},
                "validated_summary": {},
            }

            with patch("src.discovery.create_browser_session", return_value=FakeBrowserSession()), patch(
                "src.discovery.ingest_pdf_files",
                return_value=fake_ingest,
            ) as ingest_mock:
                result = ingest_decision_url(
                    case_number="6/PUU-XXIII/2025",
                    decision_url="http://www.mkri.id/index.php?page=download.Putusan&id=5072",
                    pdf_dir=pdf_dir,
                    use_browser=True,
                    force=True,
                )

            self.assertEqual(result["downloaded_pdf"], str(pdf_dir / "6_PUU-XXIII_2025.pdf"))
            self.assertEqual(ingest_mock.call_args.kwargs["pdf_paths"], [pdf_dir / "6_PUU-XXIII_2025.pdf"])


if __name__ == "__main__":
    unittest.main()
