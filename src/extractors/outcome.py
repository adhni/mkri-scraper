from __future__ import annotations

import re

from ..models import Outcome, Section
from ..normalizers import normalize_whitespace


def extract_outcome(sections: list[Section], source_text: str, document_type: str | None) -> Outcome:
    # Use the operative section, not a petitioner's request or quoted precedent.
    headings = list(re.finditer(
        r"(?im)^\s*(?:\d+\.\s*)?(?:AMAR\s+(?:PUTUSAN|PENETAPAN)|MENETAPKAN)\s*:?\s*$",
        source_text,
    ))
    if not headings:
        headings = list(re.finditer(r"(?im)^\s*MENGADILI\s*:?\s*$", source_text))
    if not headings:
        label = "ketetapan" if document_type == "ketetapan" else "amar putusan"
        message = f"{label} tidak terdeteksi secara eksplisit"
        return Outcome(decision_type=document_type, dictum=[message], summary=message)
    body = source_text[headings[-1].end():]
    body = re.split(
        r"(?im)^\s*(?:\d+\.\s*)?(?:Demikian\b|ALASAN\s+BERBEDA|PENDAPAT\s+BERBEDA|DISSENTING\s+OPINION|KETUA\s*,)",
        body, maxsplit=1,
    )[0]
    items: list[str] = []
    current: list[str] = []
    for line in body.splitlines():
        line = normalize_whitespace(line)
        if not line or re.fullmatch(r"\d+|[-–—]+|Mengadili\s*:?|Menetapkan\s*:?", line, re.I):
            continue
        if re.match(r"^(?:Dalam (?:Provisi|Pokok Permohonan|Eksepsi)|DALAM POKOK)", line, re.I):
            if current:
                items.append(normalize_whitespace(" ".join(current)))
                current = []
            continue
        numbered = re.match(r"^\d+[.)]\s*(.*)", line)
        if numbered and current:
            items.append(normalize_whitespace(" ".join(current)))
            current = []
        current.append(numbered.group(1) if numbered else line)
    if current:
        items.append(normalize_whitespace(" ".join(current)))
    items = [re.sub(r"\s+([;,.])", r"\1", item) for item in items if item]
    return Outcome(decision_type=document_type, dictum=items, summary=items[0] if items else None)
