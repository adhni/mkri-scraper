import json
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

from src.i18n import english, language_url, render_page, translations
from src.library import Library, form_values
from src.experience import search_matches
from src.webapp import create_app, _sort_case_summaries
from src.webdata import build_case_catalog, CaseRecord, summarize_case, filter_case_summaries


class Links(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links = []
        self.forms = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a':
            self.links.append(attrs)
        elif tag == 'form':
            self.forms.append(attrs)


class EnglishReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage = tempfile.TemporaryDirectory()
        cls.app = staticmethod(create_app(library_dir=cls.storage.name))
        cls.records = build_case_catalog(library_dir=cls.storage.name)
        cls.by_number = {r.payload['document']['case_number']: r for r in cls.records}
        cls.stories = json.loads(Path('data/editorial/stories.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.storage.cleanup()

    def request(self, path='/cases', **query):
        response = []
        body = b''.join(self.app({'PATH_INFO': path, 'QUERY_STRING': urlencode(query)},
                                lambda status, headers: response.append((status, dict(headers)))))
        self.assertEqual(response[0][0], '200 OK')
        return body.decode()

    def test_every_current_reader_content_field_has_a_saved_translation(self):
        sources = set()
        def collect(value):
            if isinstance(value, str) and value.strip():
                sources.add(value)
            elif isinstance(value, list):
                for child in value:
                    collect(child)
            elif isinstance(value, dict):
                for key, child in value.items():
                    if key not in {'slug', 'id', 'chapter', 'case_number', 'names', 'name', 'position',
                                   'source_pages', 'page', 'pages', 'amar_page', 'featured_rank', 'provisional_items'}:
                        collect(child)
        notes = json.loads(Path('data/editorial/cases.json').read_text())
        self.assertEqual(len(notes), 200)
        for note in notes.values():
            collect(note)
        collect(self.stories)
        insights = json.loads(Path('data/editorial/insights.json').read_text())
        for insight in insights.values():
            collect(insight)
        for record in self.records:
            collect(record.payload.get('outcome', {}).get('summary'))
        for source in sources:
            with self.subTest(source=source[:90]):
                self.assertIn(source, translations())
                self.assertTrue(translations()[source].strip())
        self.assertEqual(len(self.stories), 3)

    def test_default_invalid_and_english_languages_and_canonical_filter_values(self):
        self.assertIn('<html lang="id">', self.request())
        self.assertIn('<html lang="id">', self.request(lang='fr'))
        page = self.request(lang='en', topic='Pendidikan')
        self.assertIn('<html lang="en">', page)
        self.assertIn('Find constitutional cases.', page)
        self.assertIn('<option value="Pendidikan" selected data-en-content>Education</option>', page)
        self.assertIn('1–20 of 25 cases', page)
        self.assertIn('name="lang" value="en"', page)
        self.assertNotIn('English translation not available', page)
        self.assertIn('aria-label="Decision year"', page)
        self.assertIn('Newest decisions', page)
        self.assertIn('No matching cases.', self.request(lang='en', q='zzzzzzzzz'))

    def test_switching_preserves_query_filters_page_and_nested_return(self):
        page = self.request(lang='en', q='education', topic='Pendidikan', sort='oldest', page='2')
        links = Links(page).links
        switch = next(link for link in links if link.get('data-language') == 'id')
        self.assertEqual(parse_qs(urlsplit(switch['href']).query),
                         {'q': ['education'], 'topic': ['Pendidikan'], 'sort': ['oldest'], 'page': ['2']})
        case = next(link for link in links if 'data-case-link' in link)
        case_query = parse_qs(urlsplit(case['href']).query)
        self.assertEqual(case_query['lang'], ['en'])
        back_query = parse_qs(urlsplit(case_query['return'][0]).query)
        self.assertEqual(back_query['lang'], ['en'])
        self.assertEqual(back_query['page'], ['2'])
        self.assertEqual(back_query['topic'], ['Pendidikan'])
        id_link = language_url(case['href'], 'id')
        self.assertNotIn('lang', parse_qs(urlsplit(id_link).query))
        self.assertNotIn('lang', parse_qs(urlsplit(parse_qs(urlsplit(id_link).query)['return'][0]).query))
        for url in ['/api/cases/a', '/admin', '/cases/a/pdf#page=3', 'https://www.mkri.id/a', '//outside.test/cases', 'https://[']:
            self.assertEqual(language_url(url, 'en'), url)
        self.assertIn('<html lang="en">', self.request(lang='en', **{'return': 'https://['}))

    def test_bilingual_search_and_api_source_compatibility(self):
        for query in ['education', 'state-owned enterprises', 'personal data', 'UU ITE', 'Sisdiknas', 'hutan adat']:
            with self.subTest(query=query):
                original = json.loads(self.request('/api/cases', q=query))
                self.assertTrue(original['items'])
                self.assertEqual(original, json.loads(self.request('/api/cases', q=query, lang='en')))
                self.assertTrue(all(not key.startswith('_') for item in original['items'] for key in item))
                self.assertIn('case-card', self.request(q=query, lang='en'))
        for query in ['35/2012', '35 / 2012', '35 / PUU - X / 2012', '35 PUU 2012']:
            cases = json.loads(self.request('/api/cases', q=query))['items']
            self.assertEqual([case['case_number'] for case in cases], ['35/PUU-X/2012'])
            self.assertEqual(cases[0]['title'], 'Hutan adat bukan hutan negara')
        cases = json.loads(self.request('/api/cases', q='education', topic='Pendidikan'))['items']
        self.assertTrue(cases)
        self.assertTrue(all('Pendidikan' in case['topics'] for case in cases))

    def test_translated_titles_rank_above_incidental_english_document_mentions(self):
        title = 'Hutan adat bukan hutan negara'
        target = summarize_case(CaseRecord('target', 'parsed_json', Path('target.json'), {
            'document': {'case_number': '35/PUU-X/2012', 'decision_date': '2013-05-16'},
            'editorial': {'title': title}, 'sections': [{'text': 'Hutan adat.'}],
        }, {}))
        incidental = summarize_case(CaseRecord('other', 'parsed_json', Path('other.json'), {
            'document': {'case_number': '99/PUU-X/2012', 'decision_date': '2026-01-01'},
            'editorial': {'title': 'Perkara lain'}, 'sections': [{'text': 'References customary forests.'}],
        }, {}))
        query = 'customary forests'
        found = filter_case_summaries([incidental, target], query=query)
        ranked = _sort_case_summaries(search_matches(found, query), 'relevance')
        self.assertEqual(ranked[0]['case_id'], 'target')
        self.assertEqual(ranked[0]['_match_language'], 'en')
        self.assertEqual(ranked[0]['match_excerpt'], 'Customary forests are not state forests')

    def test_case_explanations_are_english_and_source_documents_stay_original(self):
        for number in ['35/PUU-X/2012', '90/PUU-XXI/2023', '60/PUU-XXII/2024', '91/PUU-XVIII/2020']:
            record = self.by_number[number]
            page = self.request('/cases/' + record.case_id, lang='en', **{'return': '/cases?q=35%2F2012#results'})
            self.assertIn(escape(english(record.payload['editorial']['summary'])), page)
            self.assertIn(escape(english(record.payload['editorial']['law'])), page)
            self.assertNotIn('English translation not available', page)
            self.assertIn('Full operative ruling / order — original Indonesian', page)
            self.assertIn('class="document-text" lang="id" translate="no"', page)
            self.assertIn(escape(record.payload['outcome']['dictum'][0]), page)
            self.assertIn(escape(record.payload['sections'][0]['text']), page)
            back = next(link['href'] for link in Links(page).links if 'data-browse-back' in link)
            self.assertEqual(parse_qs(urlsplit(back).query)['lang'], ['en'])
            pdfs = [link['href'] for link in Links(page).links if '/pdf' in link.get('href', '')]
            self.assertTrue(pdfs)
            self.assertTrue(all('lang=' not in url for url in pdfs))

    def test_all_stories_and_neighbor_links_are_localized_without_changing_anchors(self):
        for story in self.stories:
            page = self.request('/stories/' + story['slug'], lang='en')
            self.assertIn(escape(english(story['intro'])), page)
            self.assertIn(escape(english(story['conclusion'])), page)
            self.assertIn('id="chapter-1"', page)
            self.assertNotIn('English translation not available', page)
            for link in Links(page).links:
                url = link.get('href', '')
                if url.startswith(('/cases', '/stories/')) and '/pdf' not in url and 'data-language' not in link:
                    self.assertEqual(parse_qs(urlsplit(url).query).get('lang'), ['en'], url)

    def test_owner_edit_shows_current_source_instead_of_a_stale_translation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'parsed').mkdir()
            (root/'editorial').mkdir()
            number = '35/PUU-X/2012'
            raw = {'document': {'case_number': number, 'document_type': 'putusan'},
                   'outcome': {'summary': 'Mengabulkan permohonan untuk sebagian.',
                               'dictum': ['Mengabulkan permohonan untuk sebagian.']},
                   'parties': {'applicants': [{'name': 'AMAN'}]}}
            note = {'title': 'Hutan adat bukan hutan negara', 'summary': 'Hutan adat bukan hutan negara',
                    'law': 'UU 41/1999 tentang Kehutanan', 'topics': ['Masyarakat adat & lingkungan']}
            (root/'parsed/a.json').write_text(json.dumps(raw))
            (root/'editorial/cases.json').write_text(json.dumps({number: note}))
            app = create_app(root/'parsed', root/'validated', root/'review')
            def request():
                return b''.join(app({'PATH_INFO': '/cases/a', 'QUERY_STRING': 'lang=en'}, lambda *args: None)).decode()
            self.assertIn('Customary forests are not state forests', request())
            payload = dict(raw, editorial=note)
            fields = form_values(payload)
            fields['title'] = 'Judul baru <script>alert(1)</script>'
            fields['summary'] = 'Ringkasan baru setelah koreksi pemilik.'
            fields['topics'] = 'Topik baru'
            store = Library(root/'library')
            store.initialize()
            store.save_edit('a', payload, fields, 0)
            changed = request()
            self.assertIn('Ringkasan baru setelah koreksi pemilik.', changed)
            self.assertIn('English translation not available', changed)
            self.assertNotIn('Customary forests are not state forests', changed)
            self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', changed)
            self.assertNotIn('<script>alert(1)</script>', changed)
            dashboard = b''.join(app({'PATH_INFO': '/cases', 'QUERY_STRING': 'lang=en'}, lambda *args: None)).decode()
            self.assertIn('<option value="Topik baru" data-en-content>Topik baru — English translation not available</option>', dashboard)
            results = b''.join(app({'PATH_INFO': '/api/cases', 'QUERY_STRING': 'q=customary+forests'}, lambda *args: None))
            self.assertEqual(json.loads(results)['items'], [])
            saved = dict(translations())
            translation_path = root/'en.json'
            translation_path.write_text(json.dumps(saved))
            with patch('src.i18n.TRANSLATION_PATH', translation_path), patch('src.webapp.TRANSLATION_PATH', translation_path):
                try:
                    self.assertIn('English translation not available', request())
                    saved.update({fields['title']: 'Updated forest overview',
                                  fields['summary']: 'The owner corrected this summary.', 'Topik baru': 'New topic'})
                    translation_path.write_text(json.dumps(saved))
                    translated = request()
                    self.assertIn('Updated forest overview', translated)
                    self.assertNotIn('English translation not available', translated)
                    results = b''.join(app({'PATH_INFO': '/api/cases', 'QUERY_STRING': 'q=updated+forest+overview'}, lambda *args: None))
                    self.assertEqual(len(json.loads(results)['items']), 1)
                finally:
                    translations.cache_clear()


    def test_localization_escapes_translations_and_preserves_original_blocks(self):
        original = '<p translate="no">Menolak permohonan untuk seluruhnya.</p>'
        page = render_page('<html lang="id"><body><!--language-switch-->' + original + '</body></html>', '/cases', 'en')
        self.assertIn(original, page)
        self.assertEqual(page.count('aria-current="true"'), 1)
        page = render_page('<html lang="id"><p><span data-en-content>&lt;img src=x onerror=alert(1)&gt;</span></p></html>', '/cases', 'en')
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', page)
        self.assertNotIn('<img ', page)


if __name__ == '__main__':
    unittest.main()
