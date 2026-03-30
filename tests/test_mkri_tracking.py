from __future__ import annotations

import unittest

from src.scrapers.mkri_tracking import build_case_number, build_tracking_url, extract_tracking_case


SAMPLE_TRACKING_HTML = """
<html>
  <body>
    <h5>Detail Perkara</h5>
    <table>
      <tr><td>No Perkara</td><td>:</td><td>176/PUU-XXIII/2025</td></tr>
      <tr><td>Pokok Perkara</td><td>:</td><td>Pengujian Materiil Undang-Undang Nomor 1 Tahun 2024</td></tr>
      <tr><td>Pemohon</td><td>:</td><td>Andi Saputra</td></tr>
      <tr><td></td><td></td><td>Budi Santoso</td></tr>
      <tr><td>Kuasa Hukum</td><td>:</td><td>Siti Aminah</td></tr>
      <tr><td></td><td></td><td>Rizky Maulana</td></tr>
    </table>
    <div>Detail Proses dan Dokumen</div>
    <a href="/index.php?id=9999&page=download.Putusan">File Putusan</a>
    <a href="https://s.mkri.id/public/content/persidangan/risalah/13015_risalah.pdf">PDF</a>
    <a href="https://s.mkri.id/public/content/persidangan/audio/13015_audio.mp3">AUDIO</a>
  </body>
</html>
"""


class MkriTrackingScraperTests(unittest.TestCase):
    def test_build_case_number_and_tracking_url(self) -> None:
        case_number = build_case_number(176, "PUU", 2025)
        self.assertEqual(case_number, "176/PUU-XXIII/2025")
        self.assertEqual(
            build_tracking_url(case_number),
            "https://tracking.mkri.id/index.php?id=176%2FPUU-XXIII%2F2025&page=web.TrackPerkara",
        )

    def test_extract_tracking_case(self) -> None:
        snapshot = extract_tracking_case(
            SAMPLE_TRACKING_HTML,
            "https://tracking.mkri.id/index.php?id=176%2FPUU-XXIII%2F2025&page=web.TrackPerkara",
        )
        assert snapshot is not None
        self.assertEqual(snapshot.case_number, "176/PUU-XXIII/2025")
        self.assertEqual(snapshot.case_type, "PUU")
        self.assertEqual(snapshot.year, 2025)
        self.assertEqual(snapshot.title, "Pengujian Materiil Undang-Undang Nomor 1 Tahun 2024")
        self.assertEqual(snapshot.applicants, ["Andi Saputra", "Budi Santoso"])
        self.assertEqual(snapshot.legal_counsels, ["Siti Aminah", "Rizky Maulana"])
        categories = {item.category for item in snapshot.document_links}
        self.assertIn("decision", categories)
        self.assertIn("hearing_minutes_pdf", categories)
        self.assertIn("hearing_audio", categories)


if __name__ == "__main__":
    unittest.main()
