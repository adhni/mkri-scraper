from __future__ import annotations

import re

from ..models import Adjudicators, Section
from ..normalizers import normalize_whitespace


def _signature_names(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        candidate = normalize_whitespace(re.sub(r"\bttd\.?", "", line, flags=re.I)).strip(" ,")
        if not candidate or len(candidate) > 80 or len(candidate.split()) > 8:
            continue
        if re.search(r"\d|ketua|anggota|panitera|salinan|putusan|sekretaris", candidate, re.I):
            continue
        if not re.fullmatch(r"[A-ZÀ-Ý][\w .,’'\-]+", candidate):
            continue
        if candidate not in names:
            names.append(candidate)
    return names


def extract_adjudicators(sections: list[Section], source_text: str) -> Adjudicators:
    # Read the signed panel, not every person mentioned in the proceedings.
    signatures = list(re.finditer(r"(?im)^\s*KETUA\s*,?\s*$", source_text))
    if not signatures:
        return Adjudicators()
    signature = source_text[signatures[-1].end():]
    clerk_heading = re.search(r"(?im)^\s*PANITERA(?:\s+PENGGANTI)?\s*,?\s*$", signature)
    if not clerk_heading:
        return Adjudicators(judges=_signature_names(signature))
    return Adjudicators(
        judges=_signature_names(signature[:clerk_heading.start()]),
        clerks=_signature_names(signature[clerk_heading.end():]),
    )
