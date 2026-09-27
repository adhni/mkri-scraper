import copy
import json
from pathlib import Path
import tempfile
import unittest

from src.stories import load_stories, render_story, story_navigation
from src.webapp import create_app
from src.webdata import build_case_catalog, summarize_case


ROOT = Path(__file__).resolve().parents[1] / 'data'


class GuidedStoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage = tempfile.TemporaryDirectory()
        cls.records = build_case_catalog(ROOT/'parsed_json', ROOT/'validated_json', ROOT/'review_queue', library_dir=cls.storage.name)
        cls.summaries = [summarize_case(record) for record in cls.records]
        cls.stories = load_stories(ROOT/'editorial/stories.json', cls.summaries)
        cls.app = staticmethod(create_app(ROOT/'parsed_json', ROOT/'validated_json', ROOT/'review_queue', library_dir=cls.storage.name))

    @classmethod
    def tearDownClass(cls):
        cls.storage.cleanup()

    def request(self, path, query=''):
        response = []
        body = b''.join(self.app({'PATH_INFO': path, 'QUERY_STRING': query}, lambda status, headers: response.append(status)))
        return response[0], body.decode()

    def test_editorial_references_chronology_sources_and_length(self):
        raw = json.loads((ROOT/'editorial/stories.json').read_text())
        self.assertEqual(len(raw), 3)
        self.assertEqual(len(self.stories), len(raw))
        self.assertEqual(len({s['slug'] for s in raw}), 3)
        records = {r.payload['document']['case_number']: r for r in self.records}
        referenced = []
        for story in raw:
            dates = []
            count = sum(len(story[key].split()) for key in ['title', 'description', 'intro', 'closing_title', 'conclusion'])
            self.assertRegex(story['slug'], r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
            for entry in story['entries']:
                referenced.append(entry['case_number'])
                payload = records[entry['case_number']].payload
                dates.append(payload['document']['decision_date'])
                self.assertTrue(entry['source_pages'])
                for page in entry['source_pages']:
                    self.assertIsInstance(page, int)
                    self.assertTrue(1 <= page <= payload['source']['page_count'])
                self.assertTrue(payload['insights']['impact'])
                self.assertTrue(payload['insights']['change']['before'])
                self.assertTrue(payload['insights']['change']['after'])
                for page in payload['insights']['change'].get('pages', [payload['insights']['change']['page']]):
                    self.assertTrue(1 <= page <= payload['source']['page_count'])
                count += sum(len(entry[key].split()) for key in ['heading', 'what', 'why', 'connection'])
            self.assertEqual(dates, sorted(dates))
            self.assertTrue(300 <= count <= 450, (story['slug'], count))
        self.assertEqual(set(referenced), {'5/PUU-V/2007', '60/PUU-XXII/2024', '62/PUU-XXII/2024',
                                         '91/PUU-XVIII/2020', '168/PUU-XXI/2023', '46/PUU-VIII/2010',
                                         '69/PUU-XIII/2015', '22/PUU-XV/2017'})

    def test_home_story_pages_and_not_found(self):
        status, home = self.request('/')
        self.assertEqual(status, '200 OK')
        self.assertEqual(home.count('class="story-card"'), 3)
        self.assertEqual(home.count('class="case-card"'), 34)
        self.assertNotIn('class="featured-card"', home)
        by_number = {s['case_number']: s for s in self.summaries}
        for story in self.stories:
            status, body = self.request('/stories/' + story['slug'])
            self.assertEqual(status, '200 OK')
            self.assertIn(story['title'], body)
            self.assertEqual(body.count('class="story-chapter"'), len(story['entries']))
            for entry in story['entries']:
                item = by_number[entry['case_number']]
                self.assertIn('/cases/' + item['case_id'] + '?', body)
                for page in entry['source_pages']:
                    self.assertIn('/cases/' + item['case_id'] + '/pdf#page=' + str(page), body)
        for path in ['/stories/unknown', '/stories/', '/stories/nested/hak-dalam-keluarga']:
            self.assertEqual(self.request(path)[0], '404 Not Found')

    def test_case_navigation_boundaries_and_search_return(self):
        by_number = {s['case_number']: s for s in self.summaries}
        for story in self.stories:
            entries = story['entries']
            for index, entry in enumerate(entries):
                item = by_number[entry['case_number']]
                status, body = self.request('/cases/' + item['case_id'], 'return=%2Fcases%3Fq%3Dkeluarga')
                self.assertEqual(status, '200 OK')
                self.assertIn('/stories/' + story['slug'] + '#chapter-' + str(index + 1), body)
                self.assertEqual('← Perkara sebelumnya' in body, index > 0)
                self.assertEqual('Perkara berikutnya →' in body, index < len(entries) - 1)
                self.assertIn('href="/cases?q=keluarga#results"', body)
                self.assertIn('return=%2Fcases%3Fq%3Dkeluarga%23results', body)
        unrelated = by_number['35/PUU-X/2012']
        self.assertNotIn('class="story-context"', self.request('/cases/' + unrelated['case_id'])[1])

    def test_filters_and_api_remain_available(self):
        status, body = self.request('/cases', 'q=hutan+adat')
        self.assertEqual(status, '200 OK')
        self.assertNotIn('class="story-card"', body)
        self.assertIn('Hutan adat bukan hutan negara', body)
        status, body = self.request('/api/cases', 'topic=Keluarga+%26+anak&year=2018')
        self.assertEqual(status, '200 OK')
        payload = json.loads(body)
        self.assertEqual(set(payload), {'items', 'stats', 'facets'})
        self.assertEqual([i['case_number'] for i in payload['items']], ['22/PUU-XV/2017'])

    def test_partial_collections_hide_incomplete_stories(self):
        self.assertEqual(load_stories(ROOT/'editorial/stories.json', []), [])
        self.assertEqual(load_stories(ROOT/'editorial/missing.json', self.summaries), [])
        remaining = [s for s in self.summaries if s['case_number'] != '5/PUU-V/2007']
        self.assertEqual(len(load_stories(ROOT/'editorial/stories.json', remaining)), 2)

    def test_story_text_is_escaped_and_does_not_invent_votes(self):
        story = copy.deepcopy(self.stories[0])
        story['title'] = '<script>bad()</script>'
        story['entries'][0]['what'] = '<img src=x onerror=bad()>'
        html = render_story(story, self.summaries)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('&lt;img', html)
        self.assertNotIn('<script>', html)
        html = story_navigation('5/PUU-V/2007', [story], self.summaries)
        self.assertIn('&lt;script&gt;', html)
        for case in ['5/PUU-V/2007', '62/PUU-XXII/2024', '168/PUU-XXI/2023',
                     '46/PUU-VIII/2010', '69/PUU-XIII/2015', '22/PUU-XV/2017']:
            record = next(r for r in self.records if r.payload['document']['case_number'] == case)
            self.assertNotIn('court', record.payload['insights'])


if __name__ == '__main__':
    unittest.main()
