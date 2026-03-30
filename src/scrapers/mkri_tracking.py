from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen


TRACKING_BASE_URL = "https://tracking.mkri.id/index.php"
DEFAULT_USER_AGENT = "mkri-scraper/0.1 (+https://tracking.mkri.id)"


@dataclass
class TrackingDocumentLink:
    title: str
    url: str
    category: str
    file_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "category": self.category,
            "file_name": self.file_name,
        }


@dataclass
class TrackingCaseSnapshot:
    case_number: str
    case_type: str | None
    year: int | None
    tracking_url: str
    title: str | None = None
    applicants: list[str] = field(default_factory=list)
    legal_counsels: list[str] = field(default_factory=list)
    document_links: list[TrackingDocumentLink] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_number": self.case_number,
            "case_type": self.case_type,
            "year": self.year,
            "tracking_url": self.tracking_url,
            "title": self.title,
            "applicants": self.applicants,
            "legal_counsels": self.legal_counsels,
            "document_links": [item.to_dict() for item in self.document_links],
        }


class _AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_map = dict(attrs)
        self._current_href = attrs_map.get("href")
        self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current_href is None:
            return
        text = normalize_text("".join(self._text_parts))
        if text:
            self.items.append((self._current_href, text))
        self._current_href = None
        self._text_parts = []


def normalize_text(value: str) -> str:
    return " ".join(unescape(value).replace("\xa0", " ").split()).strip()


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "\n", html)
    text = re.sub(r"(?s)<!--.*?-->", "\n", text)
    text = re.sub(r"(?is)</t[dh]>\s*<t[dh][^>]*>", " : ", text)
    text = re.sub(r"(?is)</tr>", "\n", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|tr|td|th|li|ul|ol|h[1-6]|table|section)>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    lines = [normalize_text(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _extract_line_value(text: str, label: str) -> str | None:
    pattern = re.compile(rf"{re.escape(label)}\s*:?\s*(.+)", re.IGNORECASE)
    for line in text.splitlines():
        match = pattern.search(line)
        if match:
            return normalize_text(re.sub(r"^[:\-\s]+", "", match.group(1)))
    return None


def _extract_block(text: str, label: str, stop_labels: list[str]) -> list[str]:
    lines = text.splitlines()
    start_index: int | None = None
    collected: list[str] = []
    label_pattern = re.compile(rf"^{re.escape(label)}\s*:?\s*(.*)$", re.IGNORECASE)
    stop_patterns = [re.compile(rf"^{re.escape(item)}\s*:?", re.IGNORECASE) for item in stop_labels]

    for index, line in enumerate(lines):
        match = label_pattern.match(line)
        if not match:
            continue
        start_index = index
        initial = normalize_text(re.sub(r"^[:\-\s]+", "", match.group(1)))
        if initial:
            collected.append(initial)
        break

    if start_index is None:
        return []

    for line in lines[start_index + 1 :]:
        if any(pattern.match(line) for pattern in stop_patterns):
            break
        if line.startswith("#####") or line.upper() in {"BERKAS", "TRACKING PERKARA"}:
            break
        normalized = normalize_text(re.sub(r"^[:\-\s]+", "", line))
        if normalized:
            collected.append(normalized)
    return _dedupe_strings(collected)


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        normalized = normalize_text(item)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(normalized)
    return output


def _infer_document_category(title: str, url: str) -> str:
    lowered = title.casefold()
    path = url.casefold()
    if "putusan" in lowered or "download.putusan" in path:
        return "decision"
    if "permohonan" in lowered and "perbaikan" in lowered:
        return "petition_revision"
    if "permohonan" in lowered:
        return "petition"
    if "risalah" in lowered or ("pdf" == lowered and "risalah" in path):
        return "hearing_minutes_pdf"
    if "audio" == lowered or "audio" in path:
        return "hearing_audio"
    if "jadwal sidang" in lowered:
        return "hearing_schedule"
    if lowered in {"ap3", "arpk"}:
        return lowered
    return "other"


def _file_name_from_url(url: str) -> str | None:
    name = Path(urlparse(url).path).name
    return name or None


def to_roman(value: int) -> str:
    if value <= 0:
        raise ValueError("Roman numerals require a positive integer")
    mapping = [
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ]
    parts: list[str] = []
    remaining = value
    for number, roman in mapping:
        while remaining >= number:
            parts.append(roman)
            remaining -= number
    return "".join(parts)


def session_roman_for_year(year: int) -> str:
    return to_roman(year - 2002)


def build_case_number(sequence: int, case_type: str, year: int) -> str:
    return f"{sequence}/{case_type}-{session_roman_for_year(year)}/{year}"


def slugify_case_number(case_number: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9\-_/]+", "", case_number)
    return normalized.replace("/", "_")


def build_tracking_url(case_number: str) -> str:
    return f"{TRACKING_BASE_URL}?id={quote(case_number, safe='')}&page=web.TrackPerkara"


def fetch_url_text(url: str, timeout: float = 20.0, user_agent: str = DEFAULT_USER_AGENT) -> str:
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def download_binary(url: str, destination: str | Path, timeout: float = 30.0, user_agent: str = DEFAULT_USER_AGENT) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=timeout) as response:
        destination.write_bytes(response.read())
    return destination


def extract_tracking_case(html: str, tracking_url: str) -> TrackingCaseSnapshot | None:
    plain_text = _strip_html(html)
    case_number = _extract_line_value(plain_text, "No Perkara")
    if not case_number:
        return None

    case_match = re.match(r"^\s*\d+/([A-Z]+)(?:-[A-Z0-9]+)?/(\d{4})\s*$", case_number)
    case_type = case_match.group(1) if case_match else None
    year = int(case_match.group(2)) if case_match else None

    applicants = _extract_block(
        plain_text,
        "Pemohon",
        ["Kuasa Hukum", "Risalah Sidang", "Pengujian Undang Undang yang serupa", "Berkas", "Detail Proses dan Dokumen"],
    )
    legal_counsels = _extract_block(
        plain_text,
        "Kuasa Hukum",
        ["Risalah Sidang", "Pengujian Undang Undang yang serupa", "Berkas", "Detail Proses dan Dokumen"],
    )

    collector = _AnchorCollector()
    collector.feed(html)
    links: list[TrackingDocumentLink] = []
    seen: set[tuple[str, str]] = set()
    for href, text in collector.items:
        absolute_url = urljoin(tracking_url, href)
        key = (absolute_url, text.casefold())
        if key in seen:
            continue
        seen.add(key)
        links.append(
            TrackingDocumentLink(
                title=text,
                url=absolute_url,
                category=_infer_document_category(text, absolute_url),
                file_name=_file_name_from_url(absolute_url),
            )
        )

    return TrackingCaseSnapshot(
        case_number=case_number,
        case_type=case_type,
        year=year,
        tracking_url=tracking_url,
        title=_extract_line_value(plain_text, "Pokok Perkara"),
        applicants=applicants,
        legal_counsels=legal_counsels,
        document_links=links,
    )
