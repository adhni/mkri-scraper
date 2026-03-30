from __future__ import annotations

import re

from ..models import Adjudicators, Section
from ..normalizers import normalize_party_name, normalize_whitespace


def _extract_person_candidates(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        candidate = normalize_whitespace(line)
        if not candidate:
            continue
        if len(candidate) > 80:
            continue
        if re.search(r"\b(hakim|panitera|sekretaris)\b", candidate, flags=re.IGNORECASE):
            continue
        if re.search(r"[A-Z][a-z]+ [A-Z][a-z]+", candidate) or candidate.isupper():
            normalized = normalize_party_name(candidate)
            if normalized and normalized not in names:
                names.append(normalized)
    return names


def extract_adjudicators(sections: list[Section], source_text: str) -> Adjudicators:
    blob = "\n\n".join(section.text for section in sections) + "\n" + source_text
    judges: list[str] = []
    clerks: list[str] = []
    for pattern in [r"hakim konstitusi", r"majelis hakim", r"ditandatangani oleh"]:
        if re.search(pattern, blob, flags=re.IGNORECASE):
            judges.extend(_extract_person_candidates(blob))
            break
    for pattern in [r"panitera", r"panitera pengganti"]:
        if re.search(pattern, blob, flags=re.IGNORECASE):
            for line in blob.splitlines():
                if re.search(pattern, line, flags=re.IGNORECASE):
                    candidate = normalize_party_name(line)
                    if candidate and candidate not in clerks:
                        clerks.append(candidate)
    judges = list(dict.fromkeys(judges))
    clerks = list(dict.fromkeys(clerks))
    return Adjudicators(judges=judges, clerks=clerks)

