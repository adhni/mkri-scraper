"""Transactional PDF library. Raw extraction and owner corrections stay separate."""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .normalizers import normalize_case_number
from .validators import collect_review_flags, validate_business_rules


class ConflictError(ValueError):
    pass


FACT_FIELDS = {
    'case_number': ('document', 'case_number'),
    'document_type': ('document', 'document_type'),
    'decision_date': ('document', 'decision_date'),
    'applicants': ('parties', 'applicants'),
    'judges': ('adjudicators', 'judges'),
    'clerks': ('adjudicators', 'clerks'),
    'dictum': ('outcome', 'dictum'),
}
EDITORIAL_FIELDS = ('title', 'summary', 'topics', 'law', 'source_sections')


def apply_corrections(raw: dict, edits: dict, editorial: dict) -> dict:
    payload = copy.deepcopy(raw)
    for key, value in edits.items():
        if key in FACT_FIELDS:
            group, field = FACT_FIELDS[key]
            payload.setdefault(group, {})[field] = value
    if 'dictum' in edits:
        payload.setdefault('outcome', {})['summary'] = next(iter(edits['dictum']), None)
    if 'document_type' in edits:
        payload.setdefault('outcome', {})['decision_type'] = edits['document_type']
    if edits:
        validation = payload.setdefault('validation', {})
        flags = collect_review_flags(payload)
        validation['review_flags'] = flags
        validation['business_rule_errors'] = validate_business_rules(payload)
        validation['needs_manual_review'] = bool(flags or validation['business_rule_errors'] or validation.get('schema_errors'))
    payload['editorial'] = editorial
    return payload


def form_values(payload: dict) -> dict[str, str]:
    values = {}
    for key, (group, field) in FACT_FIELDS.items():
        value = payload.get(group, {}).get(field)
        if key == 'applicants':
            value = '\n'.join(item['name'] for item in value or [])
        elif key == 'dictum':
            value = '\n\n'.join(value or [])
        elif isinstance(value, list):
            value = '\n'.join(value)
        values[key] = value or ''
    editorial = payload.get('editorial', {})
    for key in EDITORIAL_FIELDS:
        value = editorial.get(key, '')
        if key == 'law' and key not in editorial:
            value = '; '.join(payload.get('legal_basis', {}).get('object_of_review', []))
        values[key] = ', '.join(value) if isinstance(value, list) else value
    return values


def read_corrections(raw: dict, fields: dict[str, str], previous: dict | None = None) -> tuple[dict, dict]:
    previous = previous or {}
    number = fields.get('case_number', '').strip()
    if not number or normalize_case_number(number) != number.replace(' ', ''):
        raise ValueError('Isi nomor perkara lengkap, misalnya 135/PUU-XXIII/2025.')
    kind = fields.get('document_type', '')
    if kind not in {'putusan', 'ketetapan'}:
        raise ValueError('Pilih jenis dokumen.')
    decision_date = fields.get('decision_date', '').strip()
    if decision_date:
        try:
            decision_date = date.fromisoformat(decision_date).isoformat()
        except ValueError:
            raise ValueError('Tanggal putusan tidak valid.') from None
    values: dict[str, Any] = dict(case_number=number.replace(' ', ''), document_type=kind, decision_date=decision_date or None)
    for key in ['applicants', 'judges', 'clerks']:
        names = list(dict.fromkeys(line.strip() for line in fields.get(key, '').splitlines() if line.strip()))
        values[key] = [{'name': name, 'role': 'applicant', 'description': None} for name in names] if key == 'applicants' else names
    if not values['applicants']:
        raise ValueError('Isi setidaknya satu pemohon.')
    values['dictum'] = [part.strip() for part in fields.get('dictum', '').replace('\r\n', '\n').split('\n\n') if part.strip()]
    if not values['dictum']:
        raise ValueError('Isi amar putusan atau ketetapan.')
    edits = {}
    for key, value in values.items():
        group, field = FACT_FIELDS[key]
        original = raw.get(group, {}).get(field)
        # Keep descriptions when applicant names were not changed.
        if key == 'applicants' and key not in previous and [p['name'] for p in value] == [p['name'] for p in original or []]:
            continue
        if value != original or key in previous:
            edits[key] = value
    editorial = {key: fields.get(key, '').strip() for key in EDITORIAL_FIELDS}
    editorial['topics'] = list(dict.fromkeys(t.strip() for t in fields.get('topics', '').split(',') if t.strip()))
    return edits, editorial


class Library:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.path = self.directory / 'library.sqlite3'

    def initialize(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS documents (
                    hash TEXT PRIMARY KEY, filename TEXT NOT NULL, pdf BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY, raw TEXT, edits TEXT NOT NULL, editorial TEXT NOT NULL,
                    document_hash TEXT REFERENCES documents(hash), revision INTEGER NOT NULL,
                    updated_at TEXT NOT NULL, case_number TEXT NOT NULL, document_type TEXT NOT NULL,
                    UNIQUE(case_number, document_type)
                );
                CREATE TABLE IF NOT EXISTS drafts (
                    id TEXT PRIMARY KEY, target TEXT NOT NULL, raw TEXT NOT NULL,
                    edits TEXT NOT NULL, editorial TEXT NOT NULL, document_hash TEXT NOT NULL REFERENCES documents(hash),
                    revision INTEGER NOT NULL, created_at TEXT NOT NULL
                );
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys = ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def cases(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM cases')]

    def drafts(self) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT d.*, f.filename FROM drafts d JOIN documents f ON f.hash=d.document_hash ORDER BY created_at DESC')]

    def draft(self, draft_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute('SELECT * FROM drafts WHERE id=?', (draft_id,)).fetchone()
            return dict(row) if row else None

    def stage(self, pdf: bytes, filename: str, raw: dict, catalog: list, target_id: str = '') -> str:
        digest = hashlib.sha256(pdf).hexdigest()
        stored = {row['id']: row for row in self.cases()}
        existing = next((r for r in catalog if r.case_id == target_id), None) if target_id else None
        if target_id and not existing:
            raise ValueError('Perkara tujuan tidak ditemukan.')
        if not existing:
            same_pdf = next((row for row in stored.values() if row['document_hash'] == digest), None)
            if same_pdf:
                existing = next((r for r in catalog if r.case_id == same_pdf['id']), None)
        if not existing:
            number = raw.get('document', {}).get('case_number')
            kind = raw.get('document', {}).get('document_type')
            matches = [r for r in catalog if number and any(
                p.get('document', {}).get('case_number') == number and p.get('document', {}).get('document_type') == kind
                for p in [r.payload, r.raw_payload or {}]
            )]
            if len(matches) > 1:
                raise ValueError('Ada beberapa dokumen dengan nomor ini. Buka perkara tujuan lalu pilih Ganti PDF.')
            existing = next(iter(matches), None)
        target = existing.case_id if existing else 'case-' + uuid.uuid4().hex
        current = stored.get(target)
        edits = json.loads(current['edits']) if current else {}
        editorial = existing.payload.get('editorial', {}) if existing else {}
        raw = copy.deepcopy(raw)
        raw['source']['file_name'] = filename
        raw['source']['pdf_path'] = 'library:' + digest
        draft_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO documents VALUES (?, ?, ?)', (digest, filename, pdf))
            db.execute('INSERT INTO drafts VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (
                draft_id, target, json.dumps(raw, ensure_ascii=False), json.dumps(edits),
                json.dumps(editorial, ensure_ascii=False), digest, current['revision'] if current else 0, self.now(),
            ))
        return draft_id

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _save(self, db, case_id, raw, edits, editorial, document_hash, revision, fields):
        existing = db.execute('SELECT revision FROM cases WHERE id=?', (case_id,)).fetchone()
        if (existing['revision'] if existing else 0) != revision:
            raise ConflictError('Data sudah diubah di halaman lain. Muat ulang sebelum menyimpan.')
        number = fields['case_number'].replace(' ', '')
        kind = fields['document_type']
        duplicate = db.execute('SELECT id FROM cases WHERE case_number=? AND document_type=? AND id<>?', (number, kind, case_id)).fetchone()
        if duplicate:
            raise ConflictError('Nomor dan jenis dokumen ini sudah ada. Buka perkara tersebut untuk memperbaruinya.')
        db.execute('INSERT OR REPLACE INTO cases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', (
            case_id, raw, json.dumps(edits, ensure_ascii=False), json.dumps(editorial, ensure_ascii=False),
            document_hash, revision + 1, self.now(), number, kind,
        ))

    def publish(self, draft_id: str, fields: dict[str, str]) -> str:
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            draft = db.execute('SELECT * FROM drafts WHERE id=?', (draft_id,)).fetchone()
            if not draft:
                raise ValueError('Draf tidak ditemukan atau sudah disimpan.')
            edits, editorial = read_corrections(json.loads(draft['raw']), fields, json.loads(draft['edits']))
            self._save(db, draft['target'], draft['raw'], edits, editorial, draft['document_hash'], draft['revision'], fields)
            db.execute('DELETE FROM drafts WHERE id=?', (draft_id,))
            return draft['target']

    def save_edit(self, case_id: str, raw: dict, fields: dict[str, str], revision: int) -> None:
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
            edits, editorial = read_corrections(raw, fields, json.loads(existing['edits']) if existing else {})
            self._save(db, case_id, existing['raw'] if existing else None, edits, editorial,
                       existing['document_hash'] if existing else None, revision, fields)

    def discard(self, draft_id: str) -> None:
        with self.connect() as db:
            db.execute('DELETE FROM drafts WHERE id=?', (draft_id,))
            db.execute('DELETE FROM documents WHERE hash NOT IN (SELECT document_hash FROM drafts) AND hash NOT IN (SELECT document_hash FROM cases WHERE document_hash IS NOT NULL)')

    def pdf(self, *, case_id: str = '', draft_id: str = '') -> bytes | None:
        if not self.path.exists():
            return None
        table = 'drafts' if draft_id else 'cases'
        with self.connect() as db:
            row = db.execute(f'SELECT f.pdf FROM documents f JOIN {table} c ON c.document_hash=f.hash WHERE c.id=?', (draft_id or case_id,)).fetchone()
            return bytes(row['pdf']) if row else None

    def backup(self, destination: str | Path) -> None:
        with self.connect() as source, sqlite3.connect(destination) as target:
            source.backup(target)
