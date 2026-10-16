"""Shared search normalization for reader queries and case metadata."""
from __future__ import annotations

import re
import unicodedata


LAW_NAMES = {
    'ite': 'informasi dan transaksi elektronik',
    'sisdiknas': 'sistem pendidikan nasional',
    'bumn': 'badan usaha milik negara',
    'bpjs': 'badan penyelenggara jaminan sosial',
    'sjsn': 'sistem jaminan sosial nasional',
    'kuhap': 'kitab uu hukum acara pidana',
    'kuhp': 'kitab uu hukum pidana',
    'tipikor': 'tindak pidana korupsi',
    'kpk': 'komisi pemberantasan tindak pidana korupsi',
    'asn': 'aparatur sipil negara',
    'apbn': 'anggaran pendapatan dan belanja negara',
    'pdp': 'pelindungan data pribadi',
    'tapera': 'tabungan perumahan rakyat',
    'minerba': 'pertambangan mineral dan batubara',
}
_LAW_LOOKUP = {name: alias for alias, name in LAW_NAMES.items()}
_LAW_LOOKUP.update({
    'komisi pemberantasan korupsi': 'kpk',
    'perlindungan data pribadi': 'pdp',
    'mineral dan batubara': 'minerba',
})
_CASE_QUERY = re.compile(
    r'(?<!\w)(?:(?:putusan|perkara)\s+)?(?:(?:nomor|no\.?)[\s]+)?'
    r'(?P<number>\d+)\s*[/\s]\s*'
    r'(?:(?P<kind>puu)(?:[\s/-]+(?P<roman>[ivxlcdm]+))?[\s/]+)?'
    r'(?P<year>(?:19|20)\d{2})(?!\w)', re.I,
)
_CASE_NUMBER = re.compile(
    r'\s*0*(?P<number>\d+)\s*/\s*(?P<kind>[a-z]+)'
    r'(?:\s*-\s*(?P<roman>[ivxlcdm]+))?\s*/\s*(?P<year>\d{4})\s*', re.I,
)
_LAW_PREFIX = re.compile(r'\b(?:uu|undang[\s-]+undang|perppu|perpu|pasal)\s*(?:(?:no\.?|nomor)\s*)?$', re.I)


def normalize_search_text(value: str) -> str:
    text = ' ' + re.sub(r'[\W_]+', ' ', unicodedata.normalize('NFKC', value).casefold()).strip() + ' '
    text = text.replace(' undang undang ', ' uu ').replace(' batu bara ', ' batubara ')
    words = []
    for word in text.split():
        name = LAW_NAMES.get(word)
        if name:
            if words and words[-1] == 'uu':
                words.pop()
            words.append(name)
        words.append(word)
    text = ' '.join(words)
    # Keep the full name searchable and add a shared abbreviation. The distinct
    # abbreviation also prevents KUHP queries from matching KUHAP by word overlap.
    padded = ' ' + text + ' '
    aliases = {alias for name, alias in _LAW_LOOKUP.items()
               if ' ' + name + ' ' in padded and ' ' + alias + ' ' not in padded}
    return text + (' ' + ' '.join(LAW_NAMES[alias] + ' ' + alias for alias in sorted(aliases)) if aliases else '')


def search_query(query: str) -> tuple[dict[str, str] | None, list[str]]:
    text = unicodedata.normalize('NFKC', query)
    match = _CASE_QUERY.search(text)
    reference = None
    if match and not _LAW_PREFIX.search(text[:match.start()]):
        reference = {key: value.casefold() for key, value in match.groupdict().items() if value}
        reference['number'] = str(int(reference['number']))
        text = text[:match.start()] + ' ' + text[match.end():]
    return reference, normalize_search_text(text).split()


def matches_case_number(number: str, reference: dict[str, str]) -> bool:
    match = _CASE_NUMBER.fullmatch(number)
    if not match:
        return False
    actual = {key: (value or '').casefold() for key, value in match.groupdict().items()}
    actual['number'] = str(int(actual['number']))
    return all(actual[key] == value for key, value in reference.items())
