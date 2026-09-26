from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode

from src.webapp import create_app, _sort_case_summaries
from src.webdata import build_case_catalog, summarize_case, filter_case_summaries


class ExplorerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ['parsed_json', 'validated_json', 'review_queue', 'editorial']:
            (self.root / name).mkdir()
        self.payload = {
            'source': {'file_name': 'a.pdf'},
            'document': {'case_number': '1/PUU/2025', 'document_type': 'putusan', 'title': 'PUTUSAN', 'decision_date': '2026-01-19'},
            'parties': {'applicants': [{'name': 'Nama Pemohon Unik'}]},
            'outcome': {'summary': 'Menolak permohonan untuk seluruhnya.', 'dictum': ['Menolak permohonan untuk seluruhnya.']},
            'sections': [{'heading': 'Pertimbangan', 'text': 'Pembahasan kuota haji secara mendalam.'}],
            'adjudicators': {'judges': ['Suhartoyo']},
        }
        (self.root/'parsed_json/a.json').write_text(json.dumps(self.payload))
        other = dict(self.payload, document={'case_number': '2/PUU/2024', 'document_type': 'ketetapan', 'decision_date': '2024-01-16'})
        (self.root/'parsed_json/b.json').write_text(json.dumps(other))
        self.notes = {'1/PUU/2025': {'title': 'Aturan haji', 'summary': 'Penjelasan singkat.', 'topics': ['Haji & umrah'], 'law': 'UU Pilihan'}, '2/PUU/2024': {'title': 'Topik lain', 'topics': ['Pemilu']}}
        (self.root/'editorial/cases.json').write_text(json.dumps(self.notes))
        self.app = create_app(self.root/'parsed_json', self.root/'validated_json', self.root/'review_queue')

    def request(self, path, **query):
        statuses = []
        body = b''.join(self.app({'PATH_INFO': path, 'QUERY_STRING': urlencode(query)}, lambda status, headers: statuses.append(status))).decode()
        self.assertEqual(statuses, ['200 OK'])
        return body

    def test_combined_filters_and_full_text_search(self):
        result = json.loads(self.request('/api/cases', q='kuota mendalam', topic='Haji & umrah', year='2026', outcome='rejected'))
        self.assertEqual([i['case_id'] for i in result['items']], ['a'])
        self.assertEqual(result['facets']['topic_counts'], {'Haji & umrah': 1, 'Pemilu': 1})
        self.assertEqual(result['facets']['years'], ['2026', '2024'])
        self.assertNotIn('_search_text', result['items'][0])
        self.assertEqual(result['items'][0]['year'], '2026')  # decision, not registration year
        self.assertEqual(json.loads(self.request('/api/cases', year='2025'))['items'], [])
        for query in ['NAMA PEMOHON UNIK', 'UU Pilihan', 'Aturan haji']:
            self.assertTrue(json.loads(self.request('/api/cases', q=query))['items'])

    def test_editorial_survives_new_parse(self):
        updated = dict(self.payload, document=dict(self.payload['document'], title='PUTUSAN BARU'))
        (self.root/'parsed_json/a.json').write_text(json.dumps(updated))
        result = json.loads(self.request('/api/cases/a'))
        self.assertEqual(result['summary']['title'], 'Aturan haji')
        self.assertEqual(result['payload']['document']['title'], 'PUTUSAN BARU')
        self.assertNotIn('_search_text', result['summary'])

    def test_reader_pages_and_empty_results(self):
        body = self.request('/cases', topic='Haji & umrah')
        self.assertIn('1 dari 2 perkara', body)
        self.assertIn('Aturan haji', body)
        self.assertIn('value="Pemilu"', body)
        self.assertIn('Tidak dapat diterima', body)
        self.assertIn('Belum menemukan yang cocok', self.request('/cases', q='zzzzzz'))
        detail = self.request('/cases/a')
        self.assertIn('Ringkasan editorial', detail)
        self.assertIn('Suhartoyo', detail)
        self.assertIn('19 Januari 2026', detail)
        self.assertIn('Pembahasan kuota haji', detail)

    def test_editorial_and_query_are_html_escaped(self):
        self.notes['1/PUU/2025']['title'] = '<script>alert("x")</script>'
        (self.root/'editorial/cases.json').write_text(json.dumps(self.notes))
        for body in [self.request('/cases'), self.request('/cases/a'), self.request('/cases', q='"><script>bad</script>')]:
            self.assertNotIn('<script>', body)
            self.assertIn('&lt;script&gt;', body)

    def test_chronological_sort_keeps_unknown_dates_last(self):
        items = [{'case_id': 'missing'}, {'case_id': 'new', 'decision_date': '2026-01-19'}, {'case_id': 'old', 'decision_date': '2024-01-16'}]
        self.assertEqual([i['case_id'] for i in _sort_case_summaries(items, 'newest')], ['new', 'old', 'missing'])
        self.assertEqual([i['case_id'] for i in _sort_case_summaries(items, 'oldest')], ['old', 'new', 'missing'])

    def test_empty_collection_renders(self):
        for p in (self.root/'parsed_json').glob('*.json'):
            p.unlink()
        self.assertIn('0 dari 0 perkara', self.request('/cases'))


class SavedCollectionTests(unittest.TestCase):
    def test_saved_cases_have_expected_core_facts_and_editorial(self):
        root = Path(__file__).resolve().parents[1] / 'data'
        # Check the committed seed collection, independently of local owner edits.
        with tempfile.TemporaryDirectory() as library_dir:
            records = build_case_catalog(root/'parsed_json', root/'validated_json', root/'review_queue', library_dir=library_dir)
        dates = {
            '135/PUU-XXIII/2025': '2026-01-19', '225/PUU-XXIII/2025': '2026-01-19',
            '11/PUU-XXIV/2026': '2026-01-30', '262/PUU-XXIII/2025': '2026-01-30', '246/PUU-XXIII/2025': '2026-01-30',
            '281/PUU-XXIII/2025': '2026-03-02', '271/PUU-XXIII/2025': '2026-03-02', '21/PUU-XXIV/2026': '2026-03-02',
            '237/PUU-XXIII/2025': '2026-03-16', '176/PUU-XXIII/2025': '2026-03-16', '191/PUU-XXIII/2025': '2026-03-16',
            '90/PUU-XXI/2023': '2023-10-16', '160/PUU-XXI/2023': '2024-01-16',
        }
        summaries = {summarize_case(r)['case_number']: summarize_case(r) for r in records}
        self.assertTrue(dates.keys() <= summaries.keys())
        for record in records:
            case = record.payload['document']['case_number']
            if case not in dates:
                continue
            with self.subTest(case=case):
                summary = summaries[case]
                self.assertEqual(summary['decision_date'], dates[case])
                self.assertTrue(summary['editorial'])
                self.assertTrue(summary['topics'])
                self.assertTrue(summary['law'])
                self.assertIn(len(record.payload['adjudicators']['judges']), [8, 9])
                self.assertNotEqual(summary['outcome_key'], 'unknown')
        self.assertEqual(summaries['237/PUU-XXIII/2025']['outcome_key'], 'rejected')
        for case in ['191/PUU-XXIII/2025', '90/PUU-XXI/2023']:
            self.assertEqual(summaries[case]['outcome_key'], 'granted_partly')
        self.assertEqual(summaries['21/PUU-XXIV/2026']['applicant_count'], 2)


if __name__ == '__main__':
    unittest.main()
