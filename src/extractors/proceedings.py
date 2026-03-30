from __future__ import annotations

import re

from ..models import Section
from ..normalizers import normalize_whitespace


def extract_proceedings(sections: list[Section], source_text: str) -> list[str]:
    events: list[str] = []
    blob = "\n".join(section.text for section in sections) + "\n" + source_text
    for pattern, label in [
        (r"mendengar\s+keterangan\s+ahli", "mendengar keterangan ahli"),
        (r"mendengar\s+keterangan\s+saksi", "mendengar keterangan saksi"),
        (r"menerima\s+.*?amicus curiae", "menerima amicus curiae"),
        (r"sidang\s+gabungan", "sidang gabungan"),
        (r"sidang\s+pleno", "sidang pleno"),
        (r"rapat permusyawaratan hakim", "rapat permusyawaratan hakim"),
        (r"pembacaan\s+putusan", "pembacaan putusan"),
        (r"pembacaan\s+penetapan", "pembacaan ketetapan"),
    ]:
        if re.search(pattern, blob, flags=re.IGNORECASE):
            events.append(label)
    for line in blob.splitlines():
        normalized = normalize_whitespace(line)
        if re.search(r"\b(hearing|sidang|persidangan|pemeriksaan)\b", normalized, flags=re.IGNORECASE):
            lowered = normalized.lower()
            if "perkara nomor" in lowered or len(normalized) > 60:
                continue
            if normalized not in events:
                events.append(normalized)
    return events[:40]
