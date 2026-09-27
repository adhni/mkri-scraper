import json
from pathlib import Path
import tempfile
import unittest
from src.experience import browse_return, highlighted, search_matches, judges_html, pdf_source
from src.extractors.outcome import extract_outcome
from src.webapp import _sort_case_summaries, create_app


class ReaderExperienceTests(unittest.TestCase):
    def test_title_beats_incidental_document_match_and_explicit_sort_wins(self):
        items = [dict(case_id='recent',title='Privasi',decision_date='2026-01-01',_excerpt_text='Tentang hutan adat.'),
                 dict(case_id='forest',title='Hutan adat bukan hutan negara',decision_date='2013-05-16',_excerpt_text='Hutan adat.')]
        matched = search_matches(items, 'hutan adat')
        self.assertEqual(_sort_case_summaries(matched, 'relevance')[0]['case_id'], 'forest')
        self.assertEqual(_sort_case_summaries(matched, 'newest')[0]['case_id'], 'recent')
        self.assertEqual(matched[0]['match_label'], 'Teks dokumen')

    def test_navigation_and_highlighting_do_not_accept_external_urls_or_html(self):
        self.assertEqual(browse_return('/cases?topic=Pemilu'), '/cases?topic=Pemilu#results')
        for bad in ['//evil.test', 'https://evil.test/cases', 'https://[', '/admin']:
            self.assertEqual(browse_return(bad), '/cases#results')
        self.assertEqual(highlighted('<img> hutan', 'hutan'), '&lt;img&gt; <mark>hutan</mark>')
        self.assertIsNone(pdf_source({'source': {'download_url': 'javascript:alert(1)'}}))

    def test_unknown_judges_are_not_counted_as_supporting(self):
        html = judges_html(['Hakim A', 'Hakim B'], {})
        self.assertIn('belum diverifikasi', html)
        self.assertNotIn('Mengikuti putusan', html)
        self.assertNotIn('judge-card position-majority', html)

    def test_deciding_panel_and_opinions_are_distinct_from_reading_panel(self):
        data = json.loads(Path('data/editorial/insights.json').read_text())
        court = data['60/PUU-XXII/2024']['court']
        self.assertIn('Ridwan Mansyur', court['names'])
        self.assertEqual(len(court['names']), 9)
        positions = {p['name']: p['position'] for p in court['positions']}
        self.assertEqual(positions['M. Guntur Hamzah'], 'dissenting')
        self.assertEqual(positions['Daniel Yusmic P. Foekh'], 'concurring')
        for case in data.values():
            names = case.get('court', {}).get('names', [])
            for p in case.get('court', {}).get('positions', []):
                self.assertIn(p['name'], names)
                self.assertGreater(p['page'], 0)
                self.assertTrue(p['explanation'])

    def test_million_at_line_start_is_not_a_new_dictum(self):
        text = 'AMAR PUTUSAN\nMengadili:\n1. Mengabulkan permohonan.\n2. Lebih dari\n1.000.000 (satu juta) jiwa.\n3. Memerintahkan pemuatan.\nDemikian diputus.'
        result = extract_outcome([], text, 'putusan')
        self.assertEqual(len(result.dictum), 3)
        self.assertIn('1.000.000', result.dictum[1])

    def test_seed_pdf_serves_known_file_then_falls_back_to_official_host(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'parsed').mkdir(); (root/'raw_pdfs').mkdir()
            file = 'putusan_mkri_123_456.pdf'
            (root/'parsed/a.json').write_text(json.dumps({'source':{'file_name':file}}))
            pdf = root/'raw_pdfs'/file; pdf.write_bytes(b'%PDF-test')
            app = create_app(root/'parsed',root/'validated',root/'review')
            def request():
                response=[]
                body=b''.join(app({'PATH_INFO':'/cases/a/pdf'},lambda status,headers: response.append((status,dict(headers)))))
                return response[0],body
            (status,headers),body=request()
            self.assertEqual(status,'200 OK');self.assertEqual(body,b'%PDF-test')
            pdf.unlink()
            (status,headers),body=request()
            self.assertEqual(status,'302 Found')
            self.assertEqual(headers['Location'],'https://s.mkri.id/public/content/persidangan/putusan/'+file)


if __name__ == '__main__': unittest.main()
