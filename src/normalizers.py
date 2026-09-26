from __future__ import annotations

import re
from datetime import date

MONTHS = {
    "januari": 1,
    "februari": 2,
    "maret": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "agustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "desember": 12,
}

_NUMBERS = dict(zip(
    "nol satu dua tiga empat lima enam tujuh delapan sembilan sepuluh sebelas".split(), range(12),
))
_NUMBER_WORD = r"(?:nol|satu|dua|tiga|empat|lima|enam|tujuh|delapan|sembilan|sepuluh|sebelas|belas|puluh|ratus|ribu)"
_NUMBER = rf"(?:\d+|{_NUMBER_WORD}(?:\s+{_NUMBER_WORD})*)"
INDONESIAN_DATE_RE = re.compile(
    rf"(?P<day>{_NUMBER})\s*,?\s*(?:bulan\s+)?"
    rf"(?P<month>{'|'.join(MONTHS)})\s*,?\s*(?:tahun\s+)?(?P<year>{_NUMBER})\b", re.I,
)


def _indonesian_number(value: str) -> int:
    if value.isdigit():
        return int(value)
    total = current = 0
    for word in value.split():
        if word in _NUMBERS:
            current += _NUMBERS[word]
        elif word == "belas":
            current += 10
        elif word in {"puluh", "ratus"}:
            current *= 10 if word == "puluh" else 100
        elif word == "ribu":
            total += current * 1000
            current = 0
    return total + current


CASE_NUMBER_RE = re.compile(
    r"(?P<number>\d+/\s*[A-Z0-9\-./ ]+/\s*\d{4})",
    re.IGNORECASE,
)

ARTICLE_RE = re.compile(
    r"(pasal\s+\d+[A-Z]?(?:\s+ayat\s*\(\d+\))?(?:\s+h\.?u\.?f?\s*[a-z])?(?:\s+undang-undang\s+dasar\s+negara\s+republik\s+indonesia\s+tahun\s+1945|uud\s*1945|uud\s*nkri\s*tahun\s*1945)?)",
    re.IGNORECASE,
)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_case_number(text: str) -> str | None:
    match = CASE_NUMBER_RE.search(text.replace("\n", " "))
    if not match:
        return None
    normalized = normalize_whitespace(match.group("number"))
    normalized = normalized.replace(" /", "/").replace("/ ", "/")
    normalized = normalized.replace(" ", "")
    return normalized


def normalize_indonesian_date(text: str) -> str | None:
    text = normalize_whitespace(text.lower())
    match = INDONESIAN_DATE_RE.search(text)
    if not match:
        return None
    day = _indonesian_number(match.group("day"))
    month = MONTHS[match.group("month")]
    year = _indonesian_number(match.group("year"))
    if not 1900 <= year <= 2100:
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def normalize_party_name(text: str) -> str:
    cleaned = normalize_whitespace(text)
    cleaned = re.sub(r"^(\d+[\.\)]\s*)+", "", cleaned)
    cleaned = re.sub(r"^(pemohon|termohon|pemerintah|dpr|presiden|pihak terkait|kuasa hukum|ahli|saksi|amicus curiae)\s*[:\-]?\s*",
                     "",
                     cleaned,
                     flags=re.IGNORECASE)
    cleaned = re.split(r"\s+yang\s+dalam\s+hal\s+ini\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    cleaned = re.split(r"\s+yang\s+diwakili\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    cleaned = re.split(r"\s+selaku\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    return cleaned.strip(" ,;:-.")


def normalize_article_reference(text: str) -> str | None:
    match = ARTICLE_RE.search(text.replace("\n", " "))
    if not match:
        return None
    ref = normalize_whitespace(match.group(1))
    ref = ref.replace("h. u. f.", "huruf").replace("h u f", "huruf")
    return ref


def extract_case_numbers(text: str) -> list[str]:
    numbers: list[str] = []
    for match in CASE_NUMBER_RE.finditer(text.replace("\n", " ")):
        number = normalize_whitespace(match.group("number"))
        number = number.replace(" ", "")
        if number not in numbers:
            numbers.append(number)
    return numbers
