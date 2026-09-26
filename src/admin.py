"""Small owner-only upload and correction interface for the WSGI viewer."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import time
from email import policy
from email.parser import BytesParser
from html import escape
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import parse_qs, quote

from .library import Library, ConflictError, apply_corrections, form_values
from .parser import MkriParser

MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_FORM_BYTES = 256 * 1024
MAX_PAGES = 500


def parse_upload(pdf: bytes, filename: str) -> dict:
    if not filename.lower().endswith('.pdf') or not pdf.lstrip().startswith(b'%PDF-'):
        raise ValueError('Pilih file PDF yang valid.')
    if len(pdf) > MAX_PDF_BYTES:
        raise ValueError('Ukuran PDF maksimal 25 MB.')
    from pypdf import PdfReader
    with tempfile.TemporaryDirectory(prefix='mkri-upload-') as tmp:
        path = Path(tmp) / 'document.pdf'
        path.write_bytes(pdf)
        try:
            reader = PdfReader(path)
            if reader.is_encrypted:
                raise ValueError('PDF terkunci. Unggah salinan tanpa kata sandi.')
            if len(reader.pages) > MAX_PAGES:
                raise ValueError('PDF maksimal 500 halaman.')
        except ValueError:
            raise
        except Exception:
            raise ValueError('PDF tidak dapat dibaca. Periksa file lalu coba lagi.') from None
        try:
            raw = MkriParser().parse_pdf(path).to_dict()
        except Exception:
            raise ValueError('PDF tidak dapat diproses. Periksa file lalu coba lagi.') from None
    if not any(s.get('text', '').strip() for s in raw.get('sections', [])):
        raise ValueError('PDF tidak memiliki teks yang dapat dibaca. Gunakan PDF dengan teks atau jalankan OCR terlebih dahulu.')
    return raw


def read_form(environ, *, upload=False) -> tuple[dict, bytes | None, str]:
    try:
        length = int(environ.get('CONTENT_LENGTH') or 0)
    except ValueError:
        raise ValueError('Ukuran permintaan tidak valid.') from None
    limit = MAX_PDF_BYTES + MAX_FORM_BYTES if upload else MAX_FORM_BYTES
    if not 0 < length <= limit:
        raise ValueError('Ukuran permintaan tidak valid atau melebihi batas.')
    body = environ['wsgi.input'].read(length)
    if len(body) != length:
        raise ValueError('Unggahan belum lengkap. Silakan coba lagi.')
    content_type = environ.get('CONTENT_TYPE', '')
    if not upload:
        if not content_type.startswith('application/x-www-form-urlencoded'):
            raise ValueError('Format formulir tidak valid.')
        return {k: v[-1] for k, v in parse_qs(body.decode('utf-8'), keep_blank_values=True).items()}, None, ''
    if not content_type.startswith('multipart/form-data') or '\r' in content_type or '\n' in content_type:
        raise ValueError('Gunakan formulir unggah PDF.')
    message = BytesParser(policy=policy.default).parsebytes(('Content-Type: ' + content_type + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + body)
    if not message.is_multipart():
        raise ValueError('Unggahan tidak valid.')
    fields, pdf, filename = {}, None, ''
    parts = list(message.iter_parts())
    if len(parts) > 10:
        raise ValueError('Terlalu banyak bagian unggahan.')
    for part in parts:
        name = part.get_param('name', header='content-disposition')
        content = part.get_payload(decode=True) or b''
        if part.get_filename() is not None:
            if name != 'pdf' or pdf is not None:
                raise ValueError('Unggah satu PDF setiap kali.')
            pdf = content
            filename = part.get_filename().replace('\\', '/').rsplit('/', 1)[-1][:200]
        elif name:
            if len(content) > MAX_FORM_BYTES:
                raise ValueError('Isian formulir terlalu panjang.')
            fields[name] = content.decode('utf-8')
    return fields, pdf, filename


class OwnerApp:
    def __init__(self, library: Library, render_layout, *, password='', local=False, enabled=False):
        self.library, self.render_layout = library, render_layout
        self.password, self.local, self.enabled = password, local, enabled
        self.secret = secrets.token_bytes(32)
        if enabled:
            library.initialize()

    def local_request(self, env):
        host = env.get('HTTP_HOST', '').split(':', 1)[0]
        return self.local and env.get('REMOTE_ADDR') in {'127.0.0.1', '::1'} and host in {'localhost', '127.0.0.1'} and not env.get('HTTP_X_FORWARDED_FOR')

    def session(self, env):
        try:
            cookie = SimpleCookie(env.get('HTTP_COOKIE', ''))
            token = cookie['mkri_owner'].value
            value, signature = token.split('.')
            expected = hmac.new(self.secret, value.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return None
            payload = json.loads(base64.urlsafe_b64decode(value))
            return payload if payload['expires'] > time.time() else None
        except (KeyError, ValueError, TypeError, CookieError):
            return None

    def can_edit(self, env):
        session = self.session(env)
        return self.enabled and (self.local_request(env) or bool(session and session.get('owner')))

    def cookie(self, session, env):
        value = base64.urlsafe_b64encode(json.dumps(session).encode()).decode()
        signature = hmac.new(self.secret, value.encode(), hashlib.sha256).hexdigest()
        secure = '; Secure' if env.get('wsgi.url_scheme') == 'https' or env.get('HTTP_X_FORWARDED_PROTO') == 'https' else ''
        return ('Set-Cookie', f'mkri_owner={value}.{signature}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800{secure}')

    def page(self, start, title, body, *, status='200 OK', headers=()):
        body = self.render_layout(title + ' · MKRI', body).encode()
        start(status, [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(body))), ('Cache-Control', 'no-store'), ('X-Frame-Options', 'DENY'), *headers])
        return [body]

    @staticmethod
    def redirect(start, path, headers=()):
        start('303 See Other', [('Location', path), ('Content-Length', '0'), ('Cache-Control', 'no-store'), *headers])
        return [b'']

    @staticmethod
    def binary(start, body, content_type, filename):
        start('200 OK', [('Content-Type', content_type), ('Content-Length', str(len(body))), ('Content-Disposition', f'inline; filename="{filename}"'), ('X-Content-Type-Options', 'nosniff'), ('Cache-Control', 'private, no-store')])
        return [body]

    @staticmethod
    def csrf_field(session):
        return f'<input type="hidden" name="csrf" value="{escape(session["nonce"])}">'

    def __call__(self, env, start, catalog):
        path = env.get('PATH_INFO', '')
        if path != '/admin' and not path.startswith('/admin/'):
            return None
        if not self.enabled:
            return self.page(start, 'Kelola koleksi', '<section class="panel owner-intro"><h1>Kelola koleksi</h1><p>Pengelolaan koleksi belum diaktifkan pada situs ini.</p><a class="inline-link" href="/cases">Kembali ke koleksi</a></section>', status='403 Forbidden')
        session = self.session(env) or {'nonce': secrets.token_urlsafe(24), 'expires': time.time() + 28800, 'owner': False}
        if self.local_request(env):
            session['owner'] = True
        headers = [self.cookie(session, env)]
        method = env.get('REQUEST_METHOD', 'GET')
        if method not in {'GET', 'POST'}:
            return self.page(start, 'Metode tidak didukung', '<p>Gunakan formulir yang tersedia.</p>', status='405 Method Not Allowed')
        fields = {}
        try:
            if method == 'POST':
                if not session['owner'] and path != '/admin/login':
                    return self.page(start, 'Masuk diperlukan', '<p>Masuk sebelum mengubah koleksi.</p>', status='403 Forbidden')
                fields, pdf, filename = read_form(env, upload=path == '/admin/upload')
                if not hmac.compare_digest(fields.get('csrf', '').encode(), session['nonce'].encode()):
                    return self.page(start, 'Formulir kedaluwarsa', '<p>Muat ulang halaman lalu coba lagi.</p>', status='403 Forbidden')
                if path == '/admin/login':
                    if not self.password or not hmac.compare_digest(fields.get('password', '').encode(), self.password.encode()):
                        return self.login(start, session, headers, 'Kata sandi tidak cocok.')
                    session.update(owner=True, nonce=secrets.token_urlsafe(24))
                    return self.redirect(start, '/admin', [self.cookie(session, env)])
                if path == '/admin/logout':
                    return self.redirect(start, '/cases', [('Set-Cookie', 'mkri_owner=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/')])
                if path == '/admin/upload':
                    if not pdf:
                        raise ValueError('Pilih PDF terlebih dahulu.')
                    raw = parse_upload(pdf, filename)
                    draft_id = self.library.stage(pdf, filename, raw, catalog, fields.get('target', ''))
                    return self.redirect(start, '/admin/drafts/' + draft_id, headers)
            if not session['owner']:
                return self.login(start, session, headers)
            if path == '/admin/backup' and method == 'GET':
                with tempfile.TemporaryDirectory(prefix='mkri-backup-') as tmp:
                    backup = Path(tmp) / 'library.sqlite3'
                    self.library.backup(backup)
                    return self.binary(start, backup.read_bytes(), 'application/octet-stream', 'mkri-library.sqlite3')
            if path in {'/admin', '/admin/upload'} and method == 'GET':
                query = parse_qs(env.get('QUERY_STRING', ''))
                return self.dashboard(start, session, headers, catalog, target=query.get('target', [''])[0])
            match = re.fullmatch(r'/admin/drafts/([a-f0-9]{32})(/pdf|/discard)?', path)
            if match:
                draft_id, action = match.groups()
                draft = self.library.draft(draft_id)
                if not draft:
                    return self.page(start, 'Draf tidak ditemukan', '<p>Draf sudah disimpan atau dihapus.</p>', status='404 Not Found')
                if action == '/pdf' and method == 'GET':
                    return self.binary(start, self.library.pdf(draft_id=draft_id), 'application/pdf', 'document.pdf')
                if action == '/discard' and method == 'POST':
                    self.library.discard(draft_id)
                    return self.redirect(start, '/admin', headers)
                raw = json.loads(draft['raw'])
                payload = apply_corrections(raw, json.loads(draft['edits']), json.loads(draft['editorial']))
                if not action and method == 'POST':
                    try:
                        self.check_duplicate(catalog, fields, draft['target'])
                        case_id = self.library.publish(draft_id, fields)
                        return self.redirect(start, '/cases/' + quote(case_id), headers)
                    except ValueError as exc:
                        return self.editor(start, session, headers, payload, path, draft['revision'], pdf_url=path+'/pdf', fields=fields, error=str(exc), status='409 Conflict' if isinstance(exc, ConflictError) else '400 Bad Request', draft=True)
                if not action and method == 'GET':
                    return self.editor(start, session, headers, payload, path, draft['revision'], pdf_url=path+'/pdf', draft=True)
            match = re.fullmatch(r'/admin/cases/([^/]+)', path)
            if match:
                record = next((r for r in catalog if r.case_id == match[1]), None)
                if not record:
                    return self.page(start, 'Perkara tidak ditemukan', '<p>Perkara tidak ditemukan.</p>', status='404 Not Found')
                if method == 'POST':
                    try:
                        self.check_duplicate(catalog, fields, record.case_id)
                        self.library.save_edit(record.case_id, record.raw_payload or record.payload, fields, int(fields.get('revision', '-1')))
                        return self.redirect(start, '/cases/' + quote(record.case_id), headers)
                    except ValueError as exc:
                        return self.editor(start, session, headers, record.payload, path, record.revision, fields=fields, error=str(exc), status='409 Conflict' if isinstance(exc, ConflictError) else '400 Bad Request')
                return self.editor(start, session, headers, record.payload, path, record.revision, pdf_url='/cases/'+quote(record.case_id)+'/pdf' if record.payload.get('has_pdf') else '')
            return self.page(start, 'Tidak ditemukan', '<p>Halaman tidak ditemukan.</p>', status='404 Not Found')
        except (ValueError, UnicodeError) as exc:
            if not session['owner']:
                return self.login(start, session, headers, 'Formulir tidak valid. Muat ulang lalu coba lagi.')
            return self.dashboard(start, session, headers, catalog, error=str(exc), status='400 Bad Request')

    @staticmethod
    def check_duplicate(catalog, fields, target):
        for record in catalog:
            doc = record.payload.get('document', {})
            if record.case_id != target and doc.get('case_number') == fields.get('case_number', '').replace(' ', '') and doc.get('document_type') == fields.get('document_type'):
                raise ConflictError('Nomor dan jenis dokumen ini sudah ada. Buka perkara yang ada untuk memperbaruinya.')

    def login(self, start, session, headers, error=''):
        return self.page(start, 'Masuk pemilik', f'''<section class="panel owner-intro"><h1>Kelola koleksi</h1><p>Masuk untuk menambahkan PDF dan memperbaiki data perkara.</p><p class="form-error" role="alert">{escape(error)}</p><form class="owner-form" action="/admin/login" method="post">{self.csrf_field(session)}<label class="field">Kata sandi<input type="password" name="password" autocomplete="current-password" required></label><button class="small-button">Masuk</button></form></section>''', headers=headers, status='403 Forbidden' if error else '200 OK')

    def dashboard(self, start, session, headers, catalog, *, target='', error='', status='200 OK'):
        options = '<option value="">Cocokkan otomatis atau buat perkara baru</option>' + ''.join(f'<option value="{escape(r.case_id)}" {"selected" if r.case_id == target else ""}>{escape(r.payload.get("document", {}).get("case_number") or r.case_id)}</option>' for r in catalog)
        drafts = ''.join(f'<li><a class="inline-link" href="/admin/drafts/{d["id"]}">{escape(d["filename"])}</a></li>' for d in self.library.drafts())
        body = f'''<section class="owner-intro"><span class="eyebrow">Kelola koleksi</span><h1>Tambahkan perkara.</h1><p>Unggah PDF, periksa hasilnya, lalu simpan ke koleksi.</p></section>
        <div class="detail-layout"><section class="panel"><h2>Unggah PDF</h2><p class="form-error" role="alert">{escape(error)}</p><form class="owner-form" action="/admin/upload" method="post" enctype="multipart/form-data">{self.csrf_field(session)}<label class="drop-zone field">Pilih atau jatuhkan PDF di sini<input type="file" name="pdf" accept="application/pdf,.pdf" required></label><p class="subtle">Maksimal 25 MB / 500 halaman. Dokumen belum tampil di koleksi sampai Anda menyimpannya.</p><label class="field">Perkara tujuan<select name="target">{options}</select></label><p class="subtle">PDF dengan nomor perkara yang sama akan memperbarui dokumen. Koreksi yang sudah disimpan tetap dipertahankan.</p><button class="small-button">Unggah & periksa</button><p class="upload-progress" role="status" hidden>PDF sedang diproses. Tunggu sebentar…</p></form></section>
        <aside class="stack"><section class="panel"><h2>Draf belum disimpan</h2><ul>{drafts or '<li>Belum ada draf.</li>'}</ul></section><section class="panel"><h2>Cadangan koleksi</h2><p>Unduh salinan PDF, draf, dan koreksi yang tersimpan.</p><a class="inline-link" href="/admin/backup">Unduh cadangan</a></section><form method="post" action="/admin/logout">{self.csrf_field(session)}<button class="small-button">Keluar</button></form></aside></div>
        <script>const form=document.querySelector('form.owner-form');form.addEventListener('submit',()=>{{form.querySelector('button').disabled=true;form.querySelector('.upload-progress').hidden=false;}});const zone=document.querySelector('.drop-zone');zone.addEventListener('dragover',e=>e.preventDefault());zone.addEventListener('drop',e=>{{e.preventDefault();if(e.dataTransfer.files.length===1)zone.querySelector('input').files=e.dataTransfer.files;}});</script>'''
        return self.page(start, 'Kelola koleksi', body, headers=headers, status=status)

    def editor(self, start, session, headers, payload, action, revision, *, pdf_url='', fields=None, error='', status='200 OK', draft=False):
        values = form_values(payload) if fields is None else fields
        labels = [('case_number', 'Nomor perkara'), ('document_type', 'Jenis dokumen'), ('decision_date', 'Tanggal putusan'), ('title', 'Judul singkat'), ('topics', 'Topik (pisahkan dengan koma)'), ('summary', 'Ringkasan untuk pembaca'), ('law', 'Undang-undang yang diuji'), ('applicants', 'Pemohon (satu nama per baris)'), ('judges', 'Hakim (satu nama per baris)'), ('clerks', 'Panitera (satu nama per baris)'), ('dictum', 'Amar (pisahkan butir dengan baris kosong)'), ('source_sections', 'Bagian dokumen yang mendasari ringkasan')]
        inputs = []
        for key, label in labels:
            value = escape(str(values.get(key, '') or ''))
            if key == 'document_type':
                control = '<select name="document_type" aria-label="Jenis dokumen" required>' + ''.join(f'<option value="{v}" {"selected" if values.get(key) == v else ""}>{text}</option>' for v, text in [('', 'Pilih jenis'), ('putusan','Putusan'),('ketetapan','Ketetapan')]) + '</select>'
            elif key in {'summary', 'applicants', 'judges', 'clerks', 'dictum'}:
                control = f'<textarea name="{key}" rows="{6 if key == "dictum" else 3}" {"required" if key in {"applicants", "dictum"} else ""}>{value}</textarea>'
            else:
                control = f'<input name="{key}" type="{"date" if key == "decision_date" else "text"}" value="{value}" {"required" if key == "case_number" else ""}>'
            inputs.append(f'<label class="field">{label}{control}</label>')
        viewer = f'<a class="inline-link" href="{escape(pdf_url)}" target="_blank" rel="noopener">Buka PDF asli ↗</a><iframe title="PDF sumber" src="{escape(pdf_url)}"></iframe>' if pdf_url else '<p>PDF asli belum tersimpan. Gunakan Ganti PDF untuk menambahkan dokumennya.</p>'
        case_id = action.rsplit('/',1)[-1]
        alternative = f'<form method="post" action="{escape(action)}/discard">{self.csrf_field(session)}<button class="small-button">Buang draf</button></form>' if '/drafts/' in action else f'<a class="inline-link" href="/admin?target={quote(case_id)}">Ganti PDF</a>'
        body = f'''<a class="back-link" href="/admin">← Kelola koleksi</a><section class="owner-intro"><h1>{'Periksa sebelum menyimpan.' if draft else 'Periksa & ubah data.'}</h1><p>Bandingkan dengan dokumen sumber. Koreksi Anda tetap disimpan saat PDF diimpor ulang.</p><p class="form-error" role="alert">{escape(error)}</p></section><div class="review-layout"><form class="panel owner-form" method="post" action="{escape(action)}">{self.csrf_field(session)}<input type="hidden" name="revision" value="{escape(str(revision))}">{''.join(inputs)}<div class="save-bar"><button class="small-button">Simpan ke koleksi</button><a class="inline-link" href="/admin">Kembali nanti</a></div></form><aside class="panel pdf-preview">{viewer}<div class="filter-actions">{alternative}</div><details><summary>Teks hasil ekstraksi</summary><div class="document-text">{''.join('<p>'+escape(s.get('text',''))+'</p>' for s in payload.get('sections', []))}</div></details></aside></div>'''
        return self.page(start, 'Periksa perkara', body, headers=headers, status=status)
