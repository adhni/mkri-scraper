from __future__ import annotations

import re

from .models import Section
from .normalizers import normalize_whitespace

KNOWN_HEADINGS = {
    "identitas",
    "duduk perkara",
    "pertimbangan hukum",
    "amar putusan",
    "amar penetapan",
    "konklusi",
    "menimbang",
    "mengadili",
    "menetapkan",
    "pokok perkara",
    "kesimpulan",
    "hal-hal yang terjadi",
    "proses persidangan",
    "bukti",
    "alat bukti",
}

HEADING_RE = re.compile(
    r"^(?:"
    r"bab\s+[ivxlcdm]+(?:\s+.*)?"
    r"|[ivxlcdm]+\s*[\.\-]?\s+.*"
    r"|\d+\.\s+.*"
    r"|[A-Z][A-Z\s\-]{4,}"
    r")$"
)


def slugify_heading(heading: str) -> str:
    slug = heading.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "section"


def looks_like_heading(line: str) -> bool:
    text = normalize_whitespace(line)
    if not text:
        return False
    lowered = text.lower()
    if lowered in KNOWN_HEADINGS:
        return True
    if len(text) <= 120 and HEADING_RE.match(text):
        return True
    return False


def split_sections(text: str) -> list[Section]:
    lines = text.splitlines()
    sections: list[Section] = []
    current_heading = "pembuka"
    current_lines: list[str] = []
    current_start = 1
    heading_line = 1
    for idx, line in enumerate(lines, start=1):
        stripped = normalize_whitespace(line)
        if idx == 1 and stripped.lower() in {"putusan", "ketetapan"}:
            current_lines.append(line)
            continue
        if looks_like_heading(stripped):
            if current_lines:
                sections.append(
                    Section(
                        heading=current_heading,
                        slug=slugify_heading(current_heading),
                        text="\n".join(current_lines).strip(),
                        start_line=current_start,
                        end_line=idx - 1,
                    )
                )
            current_heading = stripped
            current_lines = []
            current_start = idx + 1
            heading_line = idx
            continue
        current_lines.append(line)
    if current_lines or not sections:
        sections.append(
            Section(
                heading=current_heading,
                slug=slugify_heading(current_heading),
                text="\n".join(current_lines).strip(),
                start_line=current_start,
                end_line=len(lines) if lines else heading_line,
            )
        )
    return sections
