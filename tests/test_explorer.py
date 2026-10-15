from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode
from unittest.mock import patch

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

    def test_pagination_keeps_filters_return_links_and_api_compatibility(self):
        for index in range(3, 48):
            payload = dict(self.payload, document=dict(self.payload['document'], case_number=f'{index}/PUU/2025'))
            (self.root/f'parsed_json/c{index:02}.json').write_text(json.dumps(payload))
        first = self.request('/cases', year='2026', sort='case_number')
        second = self.request('/cases', year='2026', sort='case_number', page='2')
        self.assertEqual(first.count('class="case-card"'), 20)
        self.assertEqual(second.count('class="case-card"'), 20)
        self.assertIn('21–40 dari 46 perkara', second)
        self.assertIn('year=2026&amp;sort=case_number&amp;page=3#results', second)
        self.assertIn('return=%2Fcases%3Fyear%3D2026%26sort%3Dcase_number%26page%3D2%23results', second)
        self.assertIn('aria-current="page"', second)
        self.assertEqual(self.request('/cases', page='999').count('class="case-card"'), 7)
        for invalid in ['0', '-2', 'bad']:
            self.assertEqual(self.request('/cases', page=invalid).count('class="case-card"'), 20)
        self.assertIn('Belum menemukan yang cocok', self.request('/cases', q='zzzzzz', page='4'))
        self.assertEqual(len(json.loads(self.request('/api/cases', year='2026', page='2'))['items']), 46)

    def test_filter_links_reset_page_and_owner_controls_are_private(self):
        from src.webapp import _query_href
        self.assertEqual(_query_href({'q':'haji','page':'3'}, topic='Pemilu'), '/cases?q=haji&topic=Pemilu#results')
        self.assertNotIn('name="status"', self.request('/cases'))
        self.app = create_app(self.root/'parsed_json', self.root/'validated_json', self.root/'review_queue', local_admin=True)
        # Local ownership is limited to a loopback request.
        body = b''.join(self.app({'PATH_INFO':'/cases','REMOTE_ADDR':'127.0.0.1','HTTP_HOST':'localhost'}, lambda *args:None)).decode()
        self.assertIn('name="status"', body)
        self.assertIn('name="source"', body)

    def test_search_index_is_reused_and_updates_after_file_and_owner_edits(self):
        from src.library import Library, form_values
        with patch('src.webapp.build_case_catalog', wraps=build_case_catalog) as load:
            self.request('/api/cases')
            self.request('/cases')
            self.assertEqual(load.call_count, 1)
            self.notes['1/PUU/2025']['title'] = 'Judul diperbarui'
            (self.root/'editorial/cases.json').write_text(json.dumps(self.notes))
            self.assertIn('Judul diperbarui', self.request('/cases'))
            self.assertEqual(load.call_count, 2)
            store = Library(self.root/'library')
            store.initialize()
            fields = form_values(self.payload)
            fields['title'] = 'Koreksi pemilik pertama'
            store.save_edit('a', self.payload, fields, 0)
            self.assertIn('Koreksi pemilik pertama', self.request('/cases'))
            fields['title'] = 'Koreksi pemilik kedua'
            store.save_edit('a', self.payload, fields, 1)
            self.assertIn('Koreksi pemilik kedua', self.request('/cases'))
            self.assertEqual(load.call_count, 4)
            (self.root/'parsed_json/b.json').unlink()
            self.assertEqual(len(json.loads(self.request('/api/cases'))['items']), 1)
            self.assertEqual(load.call_count, 5)


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
            '60/PUU-XXII/2024': '2024-08-20', '91/PUU-XVIII/2020': '2021-11-25',
            '35/PUU-X/2012': '2013-05-16',
            '62/PUU-XXII/2024': '2025-01-02', '105/PUU-XXII/2024': '2025-04-29',
            '114/PUU-XXIII/2025': '2025-11-13', '3/PUU-XXII/2024': '2025-05-27',
            '135/PUU-XXII/2024': '2025-06-26', '168/PUU-XXI/2023': '2024-10-31',
            '97/PUU-XIV/2016': '2017-11-07', '46/PUU-VIII/2010': '2012-02-17',
            '22/PUU-XV/2017': '2018-12-13', '5/PUU-V/2007': '2007-07-23',
            '85/PUU-XI/2013': '2015-02-18', '69/PUU-XIII/2015': '2016-10-27',
            '21/PUU-XII/2014': '2015-04-28', '006/PUU-IV/2006': '2006-12-07',
            '36/PUU-X/2012': '2012-11-13', '116/PUU-XXI/2023': '2024-02-29',
            '55/PUU-XVII/2019': '2020-02-26', '18/PUU-XVII/2019': '2020-01-06',
            '30/PUU-XVI/2018': '2018-07-23', '56/PUU-XVII/2019': '2019-12-11',
            '70/PUU-XXII/2024': '2024-08-20', '53/PUU-XV/2017': '2018-01-11',
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
                self.assertIn(len(record.payload['adjudicators']['judges']), [7] if case in {'97/PUU-XIV/2016', '85/PUU-XI/2013', '21/PUU-XII/2014', '70/PUU-XXII/2024'} else [8, 9])
                self.assertNotEqual(summary['outcome_key'], 'unknown')
        self.assertEqual(summaries['237/PUU-XXIII/2025']['outcome_key'], 'rejected')
        self.assertEqual(summaries['55/PUU-XVII/2019']['outcome_key'], 'rejected')
        self.assertEqual(summaries['70/PUU-XXII/2024']['outcome_key'], 'rejected')
        self.assertEqual(summaries['30/PUU-XVI/2018']['outcome_key'], 'granted')
        for case in ['53/PUU-XV/2017', '56/PUU-XVII/2019']:
            self.assertEqual(summaries[case]['outcome_key'], 'granted_partly')
        for case in ['191/PUU-XXIII/2025', '90/PUU-XXI/2023', '60/PUU-XXII/2024', '91/PUU-XVIII/2020', '35/PUU-X/2012']:
            self.assertEqual(summaries[case]['outcome_key'], 'granted_partly')
        self.assertEqual(summaries['21/PUU-XXIV/2026']['applicant_count'], 2)
        for case, count in {'3/PUU-XXII/2024': 4, '135/PUU-XXII/2024': 1,
                            '168/PUU-XXI/2023': 7, '46/PUU-VIII/2010': 2,
                            '36/PUU-X/2012': 42, '85/PUU-XI/2013': 11,
                            '006/PUU-IV/2006': 8, '116/PUU-XXI/2023': 1,
                            '30/PUU-XVI/2018': 1, '56/PUU-XVII/2019': 2,
                            '70/PUU-XXII/2024': 2, '53/PUU-XV/2017': 1}.items():
            self.assertEqual(summaries[case]['applicant_count'], count)
        for case in ['105/PUU-XXII/2024', '3/PUU-XXII/2024', '135/PUU-XXII/2024',
                     '168/PUU-XXI/2023', '46/PUU-VIII/2010', '22/PUU-XV/2017',
                     '5/PUU-V/2007', '69/PUU-XIII/2015', '21/PUU-XII/2014',
                     '36/PUU-X/2012', '116/PUU-XXI/2023', '18/PUU-XVII/2019']:
            self.assertEqual(summaries[case]['outcome_key'], 'granted_partly')


if __name__ == '__main__':
    unittest.main()
