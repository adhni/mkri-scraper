from __future__ import annotations

import re

from ..models import Outcome, Section
from ..normalizers import normalize_whitespace


def extract_outcome(sections: list[Section], source_text: str, document_type: str | None) -> Outcome:
    blob = source_text
    outcome = Outcome(decision_type=document_type)
    dictum: list[str] = []
    preferred_sections = [
        section
        for section in sections
        if re.search(r"(amar|mengadili|menetapkan|putusan|penetapan)", section.heading, flags=re.IGNORECASE)
        or re.search(r"(amar|mengadili|menetapkan)", section.slug, flags=re.IGNORECASE)
    ]
    section_candidates = preferred_sections or sections
    lines = blob.splitlines()
    collecting = False
    for raw_line in lines:
        text = normalize_whitespace(raw_line)
        if not text:
            continue
        if re.search(r"^\s*MENETAPKAN:\s*$", raw_line, flags=re.IGNORECASE) or re.search(r"^\s*MENETAPKAN:\s*", raw_line, flags=re.IGNORECASE):
            collecting = True
            continue
        if not collecting:
            continue
        if re.fullmatch(r"\d+", text):
            continue
        if re.match(r"^(?:demikian|ditetapkan|mengingat|rapat permusyawaratan hakim)", text, flags=re.IGNORECASE):
            break
        bullet = re.match(r"^(?:\d+|[a-z])[\.\)]\s*(.+)$", text, flags=re.IGNORECASE)
        if bullet:
            item = normalize_whitespace(bullet.group(1))
            if item and item not in dictum:
                dictum.append(item)
            continue
        if dictum and len(dictum) < 4:
            continue
        if not dictum and len(text) > 10:
            dictum.append(text)
    outcome_patterns = [
        r"mengabulkan",
        r"menolak",
        r"tidak dapat diterima",
        r"menerima\s+permohonan",
        r"menetapkan",
        r"dicabut",
        r"mengesahkan",
        r"membatalkan",
    ]
    if not dictum:
        for section in section_candidates:
            for line in section.text.splitlines():
                text = normalize_whitespace(line)
                if not text:
                    continue
                if len(text) <= 20 and text.isupper():
                    continue
                if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in outcome_patterns):
                    if text not in dictum:
                        dictum.append(text)
            if dictum:
                break
    if not dictum:
        for line in blob.splitlines():
            text = normalize_whitespace(line)
            if not text:
                continue
            if len(text) <= 20 and text.isupper():
                continue
            if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in outcome_patterns):
                if text not in dictum:
                    dictum.append(text)
    if dictum and len(dictum) > 1 and any(item.startswith("Mengabulkan") or item.startswith("Menyatakan") for item in dictum):
        dictum = dictum[:4]
    if not dictum:
        if document_type == "ketetapan":
            dictum.append("ketetapan tidak terdeteksi secara eksplisit")
        elif document_type == "putusan":
            dictum.append("amar putusan tidak terdeteksi secara eksplisit")
    outcome.dictum = dictum[:20]
    outcome.summary = dictum[0] if dictum else None
    return outcome
