from __future__ import annotations

import unittest

from src.scrapers.browser import _download_url_matches


class BrowserScraperTests(unittest.TestCase):
    def test_download_url_match_tolerates_scheme_and_query_order(self) -> None:
        candidate = "https://www.mkri.id/index.php?id=5072&page=download.Putusan"
        target = "http://www.mkri.id/index.php?page=download.Putusan&id=5072"
        self.assertTrue(_download_url_matches(candidate, target))

    def test_download_url_match_uses_putusan_id(self) -> None:
        candidate = "https://www.mkri.id/index.php?page=download.Putusan&id=5072&foo=bar"
        target = "http://www.mkri.id/index.php?page=download.Putusan&id=5072"
        self.assertTrue(_download_url_matches(candidate, target))

    def test_download_url_match_rejects_different_decision_id(self) -> None:
        candidate = "https://www.mkri.id/index.php?page=download.Putusan&id=9999"
        target = "http://www.mkri.id/index.php?page=download.Putusan&id=5072"
        self.assertFalse(_download_url_matches(candidate, target))


if __name__ == "__main__":
    unittest.main()
