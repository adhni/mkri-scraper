"""Import a checked batch of official PDFs without duplicating existing cases.

Run from the repository root:
    python3 scripts/import_collection.py data/editorial/collection_sources.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.normalizers import normalize_case_number
from src.parser import MkriParser
from src.scrapers.mkri_tracking import download_binary
from src.webdata import build_case_catalog


def identity(number: str, kind: str) -> tuple[str | None, str]:
    return normalize_case_number(re.sub(r'\s+', '', number or '')), kind


def import_batch(manifest: Path, data_dir: Path, *, dry_run: bool = False) -> dict:
    entries = json.loads(manifest.read_text(encoding='utf-8'))
    seen = set()
    for entry in entries:
        key = identity(entry['case_number'], entry['document_type'])
        url = urlsplit(entry['url'])
        if not key[0] or key[1] not in {'putusan', 'ketetapan'} or key in seen:
            raise ValueError('Nomor/jenis perkara tidak valid atau berulang dalam batch.')
        if url.scheme != 'https' or url.hostname not in {'s.mkri.id', 'www.mkri.id'} or not url.path.endswith('.pdf'):
            raise ValueError('Sumber harus berupa PDF resmi MKRI melalui HTTPS.')
        if Path(entry['file_name']).name != entry['file_name'] or not entry['file_name'].endswith('.pdf'):
            raise ValueError('Nama file PDF tidak valid.')
        if not re.fullmatch(r'[a-f0-9]{64}', entry.get('sha256', '')):
            raise ValueError('Checksum SHA-256 diperlukan untuk batch yang telah diperiksa.')
        seen.add(key)

    catalog = build_case_catalog(data_dir/'parsed_json', data_dir/'validated_json', data_dir/'review_queue')
    existing = {identity(r.payload.get('document', {}).get('case_number'), r.payload.get('document', {}).get('document_type')) for r in catalog}
    result = {'added': 0, 'skipped': 0, 'pending': 0, 'failures': []}
    parser = MkriParser(ROOT/'schemas/mkri_case.schema.json')
    for entry in entries:
        key = identity(entry['case_number'], entry['document_type'])
        if key in existing:
            result['skipped'] += 1
            continue
        if dry_run:
            result['pending'] += 1
            continue
        try:
            path = data_dir/'raw_pdfs'/entry['file_name']
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.is_file():
                download_binary(entry['url'], path, timeout=60)
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                raise ValueError('Checksum PDF berbeda dari sumber yang diperiksa.')
            payload = parser.parse_pdf(path).to_dict()
            detected = identity(payload['document'].get('case_number'), entry['document_type'])[0]
            if detected and detected != key[0]:
                raise ValueError('Nomor perkara dalam PDF berbeda dari batch.')
            # These corrections were checked against this exact PDF checksum.
            for group in ('document', 'parties', 'legal_basis', 'outcome'):
                payload[group].update(entry.get('facts', {}).get(group, {}))
            if identity(payload['document'].get('case_number'), payload['document'].get('document_type')) != key:
                raise ValueError('Identitas perkara belum terverifikasi.')
            payload['source']['download_url'] = entry['url']
            output = data_dir/'parsed_json'/(path.stem + '.json')
            if output.exists():
                raise ValueError('Nama file sudah digunakan oleh perkara lain.')
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            parser.validate_json_file(output, data_dir/'validated_json', data_dir/'review_queue')
            existing.add(key)
            result['added'] += 1
            print(f'Ditambahkan: {entry["case_number"]}', flush=True)
        except Exception as exc:
            result['failures'].append({'case_number': entry['case_number'], 'error': str(exc)})
    return result


def main() -> int:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument('manifest', type=Path)
    command.add_argument('--data-dir', type=Path, default=ROOT/'data')
    command.add_argument('--dry-run', action='store_true')
    args = command.parse_args()
    try:
        result = import_batch(args.manifest, args.data_dir, dry_run=args.dry_run)
    except (ValueError, KeyError) as exc:
        command.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(bool(result['failures']))


if __name__ == '__main__':
    raise SystemExit(main())
