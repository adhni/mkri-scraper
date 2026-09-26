from __future__ import annotations

import io
import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from src.admin import parse_upload
from src.library import Library, form_values, apply_corrections, ConflictError
from src.webapp import create_app
from src.webdata import build_case_catalog


def sample_pdf(text=None):
    text = text or 'PUTUSAN\nNomor 12/PUU-XX/2024\nPEMOHON\nPemohon: Andi Setiawan\nAMAR PUTUSAN\nMenolak permohonan Pemohon untuk seluruhnya.\nDemikian diputus dalam rapat.\nDiucapkan pada tanggal 12 Maret 2024.\nKETUA,\nSuhartoyo\nPANITERA PENGGANTI,\nNama Panitera'
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    commands = ['BT /F1 12 Tf 40 780 Td 16 TL']
    for line in text.splitlines():
        escaped = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        commands.append(f'({escaped}) Tj T*')
    commands.append('ET')
    stream.set_data('\n'.join(commands).encode())
    page[NameObject('/Contents')] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = Library(self.root/'library')
        self.store.initialize()
        self.pdf = sample_pdf()
        self.raw = parse_upload(self.pdf, 'sample.pdf')

    def catalog(self):
        return build_case_catalog(self.root/'parsed', self.root/'validated', self.root/'review', library_dir=self.store.directory)

    def publish(self, raw=None, pdf=None, changes=None):
        draft = self.store.stage(pdf or self.pdf, 'sample.pdf', raw or self.raw, self.catalog())
        row = self.store.draft(draft)
        fields = form_values(apply_corrections(json.loads(row['raw']), json.loads(row['edits']), json.loads(row['editorial'])))
        fields.update(changes or {})
        return self.store.publish(draft, fields)

    def test_real_pdf_draft_is_private_until_published(self):
        draft = self.store.stage(self.pdf, '../../sample.pdf', self.raw, [])
        self.assertEqual(self.catalog(), [])
        self.assertEqual(self.store.pdf(draft_id=draft), self.pdf)
        self.assertEqual(self.raw['document']['case_number'], '12/PUU-XX/2024')
        case_id = self.store.publish(draft, form_values(self.raw))
        self.assertEqual(self.catalog()[0].case_id, case_id)
        self.assertEqual(self.store.pdf(case_id=case_id), self.pdf)
        self.assertIsNone(self.store.draft(draft))

    def test_corrections_survive_repeat_upload_and_restart(self):
        case_id = self.publish(changes={'decision_date': '2024-04-20', 'title': 'Judul pilihan', 'applicants': 'Nama Diperbaiki'})
        self.store = Library(self.store.directory)
        self.assertEqual(self.publish(), case_id)
        record = self.catalog()[0]
        self.assertEqual(len(self.catalog()), 1)
        self.assertEqual(record.payload['document']['decision_date'], '2024-04-20')
        self.assertEqual(record.payload['editorial']['title'], 'Judul pilihan')
        self.assertEqual(record.payload['parties']['applicants'][0]['name'], 'Nama Diperbaiki')
        # A parser temporarily agreeing with an owner correction must not erase it.
        agreed = json.loads(json.dumps(self.raw))
        agreed['document']['decision_date'] = '2024-04-20'
        self.publish(raw=agreed, pdf=self.pdf+b'\n%new')
        self.publish()
        self.assertEqual(self.catalog()[0].payload['document']['decision_date'], '2024-04-20')

    def test_edit_legacy_case_tracks_new_extraction_without_losing_corrections(self):
        directory = self.root/'parsed'
        directory.mkdir()
        path = directory/'legacy.json'
        path.write_text(json.dumps(self.raw))
        fields = form_values(self.raw)
        fields['decision_date'] = '2024-06-01'
        self.store.save_edit('legacy', self.raw, fields, 0)
        changed = json.loads(json.dumps(self.raw))
        changed['adjudicators']['judges'] = ['Hakim Baru']
        path.write_text(json.dumps(changed))
        record = self.catalog()[0]
        self.assertEqual(record.payload['document']['decision_date'], '2024-06-01')
        self.assertEqual(record.payload['adjudicators']['judges'], ['Hakim Baru'])

    def test_stale_save_and_duplicate_drafts_do_not_overwrite(self):
        case_id = self.publish()
        fields = form_values(self.raw)
        self.store.save_edit(case_id, self.raw, fields, 1)
        with self.assertRaises(ConflictError):
            self.store.save_edit(case_id, self.raw, fields, 1)
        first = self.store.stage(self.pdf, 'one.pdf', self.raw, self.catalog())
        second = self.store.stage(self.pdf, 'two.pdf', self.raw, self.catalog())
        self.store.publish(first, fields)
        with self.assertRaises(ConflictError):
            self.store.publish(second, fields)
        self.assertIsNotNone(self.store.draft(second))

    def test_backup_restores_pdf_and_corrections(self):
        case_id = self.publish(changes={'title': 'Cadangan saya'})
        destination = self.root/'restore'
        destination.mkdir()
        self.store.backup(destination/'library.sqlite3')
        restored = Library(destination)
        self.assertEqual(restored.pdf(case_id=case_id), self.pdf)
        self.assertEqual(json.loads(restored.cases()[0]['editorial'])['title'], 'Cadangan saya')

    def test_reimport_matches_original_number_after_number_correction(self):
        case_id = self.publish(changes={'case_number': '14/PUU-XX/2024'})
        self.assertEqual(self.publish(pdf=self.pdf+b'\n%revised-file'), case_id)
        self.assertEqual(len(self.catalog()), 1)
        self.assertEqual(self.catalog()[0].payload['document']['case_number'], '14/PUU-XX/2024')

    def test_two_new_drafts_cannot_publish_duplicate_cases(self):
        first = self.store.stage(self.pdf, 'first.pdf', self.raw, [])
        second = self.store.stage(self.pdf, 'second.pdf', self.raw, [])
        self.store.publish(first, form_values(self.raw))
        with self.assertRaises(ConflictError):
            self.store.publish(second, form_values(self.raw))
        self.assertEqual(len(self.catalog()), 1)

    def test_discard_only_deletes_unreferenced_pdf(self):
        case_id = self.publish()
        draft = self.store.stage(self.pdf, 'sample.pdf', self.raw, self.catalog())
        self.store.discard(draft)
        self.assertEqual(self.store.pdf(case_id=case_id), self.pdf)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM drafts').fetchone()[0], 0)

    def test_rejects_invalid_encrypted_and_image_only_pdfs(self):
        for data, name in [(b'hello', 'bad.pdf'), (self.pdf, 'bad.html'), (b'%PDF-1.4 junk', 'bad.pdf')]:
            with self.assertRaises(ValueError):
                parse_upload(data, name)
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        blank = io.BytesIO()
        writer.write(blank)
        with self.assertRaisesRegex(ValueError, 'teks'):
            parse_upload(blank.getvalue(), 'scan.pdf')
        writer.encrypt('secret')
        encrypted = io.BytesIO()
        writer.write(encrypted)
        with self.assertRaisesRegex(ValueError, 'terkunci'):
            parse_upload(encrypted.getvalue(), 'locked.pdf')


class OwnerFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.app = create_app(self.root/'parsed', self.root/'valid', self.root/'review', library_dir=self.root/'library', admin_password='test-owner-password')
        self.cookie = ''

    def request(self, path='/admin', fields=None, *, body=None, content_type=None, cookie=True, extra=None):
        method = 'POST' if fields is not None or body is not None else 'GET'
        if fields is not None:
            body = urlencode(fields).encode()
            content_type = 'application/x-www-form-urlencoded'
        env = {'PATH_INFO': path, 'QUERY_STRING': '', 'REQUEST_METHOD': method, 'HTTP_HOST': 'localhost:8000', 'REMOTE_ADDR': '127.0.0.1', 'wsgi.url_scheme': 'http', 'wsgi.input': io.BytesIO(body or b''), 'CONTENT_LENGTH': str(len(body or b'')), 'CONTENT_TYPE': content_type or '', 'HTTP_COOKIE': self.cookie if cookie else ''}
        env.update(extra or {})
        result = {}
        def start(status, headers):
            result['status'] = status
            result['headers'] = dict(headers)
        result['body'] = b''.join(self.app(env, start))
        if cookie and 'Set-Cookie' in result['headers']:
            self.cookie = result['headers']['Set-Cookie'].split(';')[0]
        return result

    def login(self):
        page = self.request()
        csrf = re.search(rb'name="csrf" value="([^"]+)"', page['body'])[1].decode()
        result = self.request('/admin/login', {'csrf': csrf, 'password': 'test-owner-password'})
        self.assertEqual(result['status'], '303 See Other')
        page = self.request()
        return re.search(rb'name="csrf" value="([^"]+)"', page['body'])[1].decode()

    def upload(self, csrf):
        boundary = '----mkri-test'
        body = f'--{boundary}\r\nContent-Disposition: form-data; name="csrf"\r\n\r\n{csrf}\r\n--{boundary}\r\nContent-Disposition: form-data; name="pdf"; filename="../../sample.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode()+sample_pdf()+f'\r\n--{boundary}--\r\n'.encode()
        return self.request('/admin/upload', body=body, content_type='multipart/form-data; boundary='+boundary)

    def test_upload_preview_edit_publish_and_read(self):
        csrf = self.login()
        result = self.upload(csrf)
        self.assertEqual(result['status'], '303 See Other')
        draft_path = result['headers']['Location']
        preview = self.request(draft_path)
        self.assertIn(b'Periksa sebelum', preview['body'])
        self.assertTrue(self.request(draft_path+'/pdf')['body'].startswith(b'%PDF'))
        self.assertEqual(json.loads(self.request('/api/cases')['body'])['items'], [])
        fields = form_values(parse_upload(sample_pdf(), 'sample.pdf'))
        fields.update(csrf=csrf, title='Judul baru', decision_date='2024-05-02')
        result = self.request(draft_path, fields)
        self.assertEqual(result['status'], '303 See Other')
        case_path = result['headers']['Location']
        detail = self.request(case_path)
        self.assertIn(b'Judul baru', detail['body'])
        self.assertIn(b'2 Mei 2024', detail['body'])
        self.assertIn(b'Ubah data perkara', detail['body'])
        self.assertTrue(self.request(case_path+'/pdf')['body'].startswith(b'%PDF'))
        self.assertNotIn(b'Ubah data perkara', self.request(case_path, cookie=False)['body'])
        self.assertTrue(self.request('/admin/backup')['body'].startswith(b'SQLite format 3'))

    def test_auth_and_csrf_block_mutations(self):
        self.assertEqual(self.request('/admin/upload', {}, cookie=False)['status'], '403 Forbidden')
        csrf = self.login()
        self.assertEqual(self.upload('wrong')['status'], '403 Forbidden')
        self.assertEqual(self.upload('salah-é')['status'], '403 Forbidden')
        self.assertEqual(Library(self.root/'library').drafts(), [])
        self.assertNotEqual(csrf, 'wrong')

    def test_hosted_writes_need_explicit_storage(self):
        self.app = create_app(self.root/'parsed', self.root/'valid', self.root/'review', admin_password='password')
        self.assertEqual(self.request()['status'], '403 Forbidden')

    def test_local_admin_rejects_remote_and_rebinding_hosts(self):
        self.app = create_app(self.root/'parsed', self.root/'valid', self.root/'review', local_admin=True)
        self.assertIn(b'Unggah PDF', self.request()['body'])
        self.cookie = ''
        for extra in [{'REMOTE_ADDR': '192.0.2.1'}, {'HTTP_HOST': 'evil.example'}, {'HTTP_X_FORWARDED_FOR': '192.0.2.1'}]:
            self.assertIn(b'Kata sandi', self.request(cookie=False, extra=extra)['body'])

    def test_invalid_dates_leave_draft_unpublished(self):
        csrf = self.login()
        draft_path = self.upload(csrf)['headers']['Location']
        fields = form_values(parse_upload(sample_pdf(), 'sample.pdf'))
        fields.update(csrf=csrf, decision_date='2024-02-31', title='Keep my work')
        response = self.request(draft_path, fields)
        self.assertEqual(response['status'], '400 Bad Request')
        self.assertIn(b'Keep my work', response['body'])
        self.assertEqual(json.loads(self.request('/api/cases')['body'])['items'], [])


if __name__ == '__main__':
    unittest.main()
