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
    match = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", text)
    if not match:
        return None
    day = int(match.group(1))
    month = MONTHS.get(match.group(2))
    year = int(match.group(3))
    if not month:
        return None
    return date(year, month, day).isoformat()


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
