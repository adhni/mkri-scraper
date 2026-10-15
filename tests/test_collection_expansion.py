import json
import tempfile
import unittest
import copy
import hashlib
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

from scripts.import_collection import import_batch
from src.experience import pdf_source
from src.webapp import create_app
from src.webdata import build_case_catalog, summarize_case


ROOT = Path(__file__).resolve().parents[1]


class CollectionExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage = tempfile.TemporaryDirectory()
        data = ROOT/'data'
        cls.records = build_case_catalog(data/'parsed_json', data/'validated_json', data/'review_queue', library_dir=cls.storage.name)
        cls.manifest = json.loads((data/'editorial/collection_sources.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.storage.cleanup()

    def test_collection_has_100_unique_described_cases_and_official_sources(self):
        self.assertEqual(len(self.records), 100)
        identities = set()
        for record in self.records:
            item = summarize_case(record)
            with self.subTest(case=item['case_number']):
                identities.add((item['case_number'], item['document_type']))
                for key in ['title', 'description', 'topics', 'decision_date', 'law']:
                    self.assertTrue(item[key], key)
                self.assertNotEqual(item['outcome_key'], 'unknown')
                self.assertTrue(record.payload['parties']['applicants'])
                source = urlsplit(pdf_source(record.payload))
                self.assertEqual(source.scheme, 'https')
                self.assertIn(source.hostname, {'s.mkri.id', 'www.mkri.id'})
        self.assertEqual(len(identities), 100)
        self.assertEqual(len(self.manifest), 62)
        self.assertEqual(Counter(e['batch'] for e in self.manifest), {'recent': 40, 'history': 22})

    def test_every_pdf_redirects_to_official_source_without_local_pdfs(self):
        app = create_app(library_dir=self.storage.name)
        original = Path.is_file
        def without_pdfs(path):
            return False if path.suffix == '.pdf' else original(path)
        with patch('src.webapp.build_case_catalog', return_value=self.records), patch.object(Path, 'is_file', without_pdfs):
            for record in self.records:
                response = []
                body = b''.join(app({'PATH_INFO':f'/cases/{record.case_id}/pdf'}, lambda status, headers:response.append((status,dict(headers)))))
                with self.subTest(case=record.case_id):
                    self.assertEqual(response[0][0], '302 Found')
                    self.assertEqual(response[0][1]['Location'], pdf_source(record.payload))
                    self.assertEqual(body, b'')

    def test_manifest_restores_source_url_after_reparse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'parsed_json').mkdir(); (root/'editorial').mkdir()
            record = self.records[0]
            payload = json.loads(json.dumps(record.payload))
            payload['source'] = {'file_name':'renamed.pdf'}
            (root/'parsed_json/renamed.json').write_text(json.dumps(payload))
            entry = {'case_number':payload['document']['case_number'], 'document_type':payload['document']['document_type'], 'url':pdf_source(record.payload)}
            (root/'editorial/collection_sources.json').write_text(json.dumps([entry]))
            reread = build_case_catalog(root/'parsed_json', root/'validated_json', root/'review_queue')
            self.assertEqual(pdf_source(reread[0].payload), entry['url'])

    def test_repeat_import_skips_existing_identity_even_with_different_filename(self):
        entry = json.loads(json.dumps(self.manifest[0]))
        entry['file_name'] = 'different-official-filename.pdf'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'parsed_json').mkdir()
            (root/'parsed_json/existing-id.json').write_text(json.dumps({'document':entry['facts']['document']}))
            manifest = root/'sources.json'
            manifest.write_text(json.dumps([entry]))
            with patch('scripts.import_collection.download_binary') as download:
                result = import_batch(manifest, root)
            self.assertEqual(result, {'added':0, 'skipped':1, 'pending':0, 'failures':[]})
            download.assert_not_called()
            self.assertEqual([p.stem for p in (root/'parsed_json').glob('*.json')], ['existing-id'])

    def test_new_import_applies_checked_facts_and_is_idempotent(self):
        entry = copy.deepcopy(self.manifest[0])
        raw = copy.deepcopy(next(r.payload for r in self.records if r.payload['document']['case_number'] == entry['case_number']))
        raw['document']['decision_date'] = None
        pdf = b'%PDF-checked-test'
        entry['sha256'] = hashlib.sha256(pdf).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'raw_pdfs').mkdir()
            (root/'raw_pdfs'/entry['file_name']).write_bytes(pdf)
            manifest = root/'sources.json'
            manifest.write_text(json.dumps([entry]))
            with patch('scripts.import_collection.MkriParser.parse_pdf', return_value=SimpleNamespace(to_dict=lambda:copy.deepcopy(raw))) as parse:
                first = import_batch(manifest, root)
                second = import_batch(manifest, root)
            self.assertEqual(first['added'], 1)
            self.assertEqual(first['failures'], [])
            self.assertEqual(second['skipped'], 1)
            parse.assert_called_once()
            saved = json.loads(next((root/'parsed_json').glob('*.json')).read_text())
            self.assertEqual(saved['document']['decision_date'], entry['facts']['document']['decision_date'])
            self.assertEqual(saved['source']['download_url'], entry['url'])

    def test_changed_pdf_checksum_does_not_publish_a_case(self):
        entry = copy.deepcopy(self.manifest[0])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'raw_pdfs').mkdir()
            (root/'raw_pdfs'/entry['file_name']).write_bytes(b'%PDF-different-document')
            manifest = root/'sources.json'
            manifest.write_text(json.dumps([entry]))
            with patch('scripts.import_collection.MkriParser.parse_pdf') as parse:
                result = import_batch(manifest, root)
            self.assertEqual(result['added'], 0)
            self.assertEqual(len(result['failures']), 1)
            self.assertFalse((root/'parsed_json').exists())
            parse.assert_not_called()

    def test_mixed_outcomes_and_primary_pdf_facts_are_preserved(self):
        cases = {summarize_case(record)['case_number']:record for record in self.records}
        for number in ['132/PUU-XXIV/2026','322/PUU-XXIV/2026','308/PUU-XXIV/2026','293/PUU-XXIV/2026','157/PUU-XXIV/2026']:
            self.assertEqual(summarize_case(cases[number])['outcome_key'], 'mixed')
        # The listing omitted applicants that are present in the actual PDFs.
        self.assertEqual(len(cases['322/PUU-XXIV/2026'].payload['parties']['applicants']), 4)
        self.assertEqual(len(cases['334/PUU-XXIV/2026'].payload['parties']['applicants']), 4)
        self.assertEqual(len(cases['157/PUU-XXIV/2026'].payload['parties']['applicants']), 4)
        self.assertEqual(cases['5/PUU-VIII/2010'].payload['document']['decision_date'], '2011-02-24')
        self.assertEqual(summarize_case(cases['84/PUU-X/2012'])['outcome_key'], 'rejected')
        ruling = ' '.join(cases['006/PUU-II/2004'].payload['outcome']['dictum'])
        self.assertNotIn('PENDAPAT BERBEDA', ruling)
        self.assertNotIn('pepatah Melayu', ruling)


if __name__ == '__main__':
    unittest.main()
