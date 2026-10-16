import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode

from src.experience import search_matches
from src.webapp import _sort_case_summaries, create_app
from src.webdata import CaseRecord, filter_case_summaries, summarize_case


def summary(number, law, *, text='', topic='Pendidikan', year='2026'):
    return summarize_case(CaseRecord(number, 'parsed_json', Path('case.json'), {
        'document': {'case_number':number, 'document_type':'putusan', 'decision_date':year+'-01-01'},
        'legal_basis': {'object_of_review':[law]},
        'editorial': {'title':law, 'topics':[topic]},
        'sections': [{'text':text}],
    }, {}))


class ForgivingSearchTests(unittest.TestCase):
    def setUp(self):
        self.target = summary('35/PUU-X/2012', 'UU Kehutanan', text='Masyarakat adat', topic='Masyarakat adat & lingkungan')
        self.other = summary('135/PUU-X/2012', 'UU Lain', text='Mengutip Putusan Nomor 35/PUU-X/2012.')

    def test_number_variants_find_the_case_instead_of_incidental_references(self):
        for query in ['35/2012', '35 / 2012', '35 2012', '35 PUU 2012', '35 puu x 2012',
                      '35/PUU-X/2012', '35 / PUU - X / 2012', '0035/2012', 'Putusan nomor 35/2012']:
            with self.subTest(query=query):
                found = filter_case_summaries([self.other, self.target], query=query)
                self.assertEqual([item['case_number'] for item in found], ['35/PUU-X/2012'])
                ranked = _sort_case_summaries(search_matches(found, query), 'relevance')
                self.assertEqual(ranked[0]['match_label'], 'Nomor perkara')

    def test_number_search_respects_year_roman_numeral_and_other_filters(self):
        items = [self.target, self.other]
        for query in ['35/2013', '35/PUU-XI/2012', '35/2012 sekolah']:
            self.assertEqual(filter_case_summaries(items, query=query), [])
        self.assertEqual(filter_case_summaries(items, query='35/2012 adat'), [self.target])
        self.assertEqual(filter_case_summaries(items, query='35/2012', topic='Pendidikan'), [])
        old = summary('006/PUU-II/2004', 'UU Advokat')
        self.assertEqual(filter_case_summaries([old], query='6/2004'), [old])

    def test_law_number_is_not_interpreted_as_case_number(self):
        law = summary('99/PUU-X/2012', 'UU 35/2012 tentang Contoh')
        found = filter_case_summaries([self.target, law], query='UU 35/2012')
        self.assertIn(law, found)

    def test_law_abbreviations_and_names_work_in_both_directions(self):
        laws = {
            'UU ITE': 'Undang-Undang Nomor 11 Tahun 2008 tentang Informasi dan Transaksi Elektronik',
            'Sisdiknas': 'Sistem Pendidikan Nasional',
            'UU BUMN': 'Badan Usaha Milik Negara',
            'BPJS': 'Badan Penyelenggara Jaminan Sosial',
            'SJSN': 'Sistem Jaminan Sosial Nasional',
            'KUHAP': 'Kitab Undang-Undang Hukum Acara Pidana',
            'KUHP': 'Kitab Undang-Undang Hukum Pidana',
            'KPK': 'Komisi Pemberantasan Tindak Pidana Korupsi',
            'UU PDP': 'Pelindungan Data Pribadi',
            'Tapera': 'Tabungan Perumahan Rakyat',
            'Minerba': 'Pertambangan Mineral dan Batu Bara',
        }
        for alias, full_name in laws.items():
            with self.subTest(alias=alias):
                full = summary('1/PUU/2026', full_name)
                short = summary('2/PUU/2026', alias)
                self.assertEqual(len(filter_case_summaries([full, short], query=alias)), 2)
                # Use the matching name, without the extra law number/prefix.
                name = full_name.split('tentang ')[-1]
                self.assertEqual(len(filter_case_summaries([full, short], query=name)), 2)
                ranked = search_matches([full], alias)[0]
                self.assertEqual(ranked['match_label'], 'Judul')

    def test_kuhp_and_kuhap_remain_distinct(self):
        criminal = summary('1/PUU/2026', 'Kitab Undang-Undang Hukum Pidana')
        procedure = summary('2/PUU/2026', 'Kitab Undang-Undang Hukum Acara Pidana')
        self.assertEqual(filter_case_summaries([criminal, procedure], query='KUHP'), [criminal])
        self.assertEqual(filter_case_summaries([criminal, procedure], query='KUHAP'), [procedure])

    def test_punctuation_spacing_and_case_are_ignored(self):
        item = summary('1/PUU/2026', 'UU Perlindungan Konsumen', text='Hak atas informasi konsumen')
        for query in ['  HAK   INFORMASI ', 'hak, informasi', 'perlindungan-konsumen']:
            self.assertEqual(filter_case_summaries([item], query=query), [item])

    def test_title_and_law_matches_rank_above_incidental_document_references(self):
        incidental = summary('1/PUU/2026', 'UU Lain', text='Informasi dan Transaksi Elektronik')
        relevant = summary('2/PUU/2026', 'UU Informasi dan Transaksi Elektronik')
        found = filter_case_summaries([incidental, relevant], query='UU ITE')
        ranked = _sort_case_summaries(search_matches(found, 'UU ITE'), 'relevance')
        self.assertEqual(ranked[0]['case_number'], relevant['case_number'])

    def test_html_and_api_use_the_same_number_and_alias_search(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'parsed').mkdir()
            (root/'parsed/case.json').write_text(json.dumps({
                'document': {'case_number':'35/PUU-X/2012', 'document_type':'putusan'},
                'legal_basis': {'object_of_review':['Informasi dan Transaksi Elektronik']},
            }))
            app = create_app(root/'parsed', root/'validated', root/'review')
            for query in ['35/2012', 'UU ITE']:
                for route in ['/cases', '/api/cases']:
                    with self.subTest(query=query, route=route):
                        response=[]
                        body=b''.join(app({'PATH_INFO':route, 'QUERY_STRING':urlencode({'q':query})}, lambda status, headers:response.append(status))).decode()
                        self.assertEqual(response, ['200 OK'])
                        if route == '/api/cases':
                            items = json.loads(body)['items']
                            self.assertEqual([item['case_number'] for item in items], ['35/PUU-X/2012'])
                            self.assertFalse(any(key.startswith('_') for key in items[0]))
                        else:
                            self.assertIn('35/PUU-X/2012', body)
                            self.assertIn('1 dari 1 perkara', body)


if __name__ == '__main__':
    unittest.main()
