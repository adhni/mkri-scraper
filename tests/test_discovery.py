from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from src.discovery import sync_and_ingest_cases, sync_new_cases


SAMPLE_TRACKING_HTML = """
<html>
  <body>
    <div>No Perkara : 133/PUU-XXIII/2025</div>
    <div>Pokok Perkara : Pengujian Materiil Undang-Undang Nomor 2 Tahun 2002</div>
    <div>Pemohon : Leon Maulana Mirza Pasha, S.H.</div>
    <div>Kuasa Hukum : Zico Leonard Djagardo Simanjuntak</div>
    <a href="https://www.mkri.id/index.php?id=5219&page=download.Putusan">File Putusan</a>
  </body>
</html>
"""


class DiscoveryTests(unittest.TestCase):
    def test_sync_new_cases_can_use_browser_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            html_dir = root / "html"
            snapshot_dir = root / "snapshots"
            pdf_dir = root / "pdfs"
            state_path = root / "state.json"

            class FakeBrowserSession:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb) -> None:
                    return None

                def fetch_html(self, url: str) -> str:
                    return SAMPLE_TRACKING_HTML

                def download_from_current_page(self, target_url: str, destination: str | Path) -> Path:
                    destination = Path(destination)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(b"%PDF-1.4")
                    return destination

            with patch("src.discovery.create_browser_session", return_value=FakeBrowserSession()):
                result = sync_new_cases(
                    case_type="PUU",
                    year=2025,
                    start_sequence=133,
                    max_candidates=1,
                    max_misses=1,
                    state_path=state_path,
                    html_dir=html_dir,
                    snapshot_dir=snapshot_dir,
                    pdf_dir=pdf_dir,
                    download_decisions=True,
                    use_browser=True,
                    sleep_seconds=0.0,
                )

            self.assertEqual(result["new_cases"], ["133/PUU-XXIII/2025"])
            self.assertTrue(result["browser_mode_used"])
            self.assertTrue((pdf_dir / "133_PUU-XXIII_2025.pdf").exists())

    def test_sync_new_cases_writes_snapshots_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            html_dir = root / "html"
            snapshot_dir = root / "snapshots"
            pdf_dir = root / "pdfs"
            state_path = root / "state.json"

            def fake_fetch(url: str, timeout: float = 20.0) -> str:
                if "133%2FPUU-XXIII%2F2025" in url:
                    return SAMPLE_TRACKING_HTML
                raise HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

            def fake_download(url: str, destination: str | Path, timeout: float = 30.0) -> Path:
                destination = Path(destination)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"%PDF-1.4")
                return destination

            with patch("src.discovery.fetch_url_text", side_effect=fake_fetch), patch(
                "src.discovery.download_binary",
                side_effect=fake_download,
            ):
                result = sync_new_cases(
                    case_type="PUU",
                    year=2025,
                    start_sequence=133,
                    max_candidates=5,
                    max_misses=2,
                    state_path=state_path,
                    html_dir=html_dir,
                    snapshot_dir=snapshot_dir,
                    pdf_dir=pdf_dir,
                    download_decisions=True,
                    sleep_seconds=0.0,
                )

            self.assertEqual(result["new_cases"], ["133/PUU-XXIII/2025"])
            self.assertEqual(result["last_checked_sequence"], 135)
            self.assertEqual(result["next_sequence"], 136)
            self.assertEqual(result["consecutive_misses"], 2)

            snapshot_path = snapshot_dir / "133_PUU-XXIII_2025.json"
            self.assertTrue(snapshot_path.exists())
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["case_number"], "133/PUU-XXIII/2025")

            pdf_path = pdf_dir / "133_PUU-XXIII_2025.pdf"
            self.assertTrue(pdf_path.exists())
            self.assertTrue(state_path.exists())

    def test_sync_and_ingest_cases_uses_new_downloaded_pdfs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            pdf_dir = root / "pdfs"
            pdf_dir.mkdir()
            pdf_path = pdf_dir / "176_PUU-XXIII_2025.pdf"
            pdf_path.write_bytes(b"%PDF-1.4")

            fake_discovery = {
                "new_cases": ["176/PUU-XXIII/2025"],
                "downloaded_pdfs": [str(pdf_path)],
                "failures": [],
            }
            fake_ingest = {
                "pdf_inputs": [str(pdf_path)],
                "parse_outputs": ["data/parsed_json/176_PUU-XXIII_2025.json"],
                "validate_outputs": ["data/review_queue/176_PUU-XXIII_2025.json"],
                "manual_truth_outputs": [],
                "failures": [],
                "parsed_summary": {},
                "review_summary": {},
                "validated_summary": {},
            }

            with patch("src.discovery.sync_new_cases", return_value=fake_discovery) as sync_mock, patch(
                "src.discovery.ingest_pdf_files",
                return_value=fake_ingest,
            ) as ingest_mock:
                result = sync_and_ingest_cases(
                    case_type="PUU",
                    year=2025,
                    pdf_dir=pdf_dir,
                    sleep_seconds=0.0,
                )

            sync_mock.assert_called_once()
            ingest_mock.assert_called_once()
            self.assertEqual(result["discovery"], fake_discovery)
            self.assertEqual(result["ingest"], fake_ingest)
            self.assertEqual(ingest_mock.call_args.kwargs["pdf_paths"], [pdf_path])


if __name__ == "__main__":
    unittest.main()
