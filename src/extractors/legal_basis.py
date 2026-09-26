from __future__ import annotations

import re

from ..models import LegalBasis, Section
from ..normalizers import extract_case_numbers, normalize_article_reference, normalize_whitespace


def extract_legal_basis(sections: list[Section], source_text: str) -> LegalBasis:
    text = "\n\n".join(section.text for section in sections) + "\n" + source_text
    basis = LegalBasis()
    constitutional_articles: list[str] = []
    procedural_articles: list[str] = []
    for line in text.splitlines():
        lowered = line.lower()
        if "pasal" not in lowered:
            continue
        if re.search(r"(uud|1945)", lowered, flags=re.IGNORECASE):
            ref = normalize_article_reference(line)
            if ref and ref not in constitutional_articles:
                constitutional_articles.append(ref)
        elif re.search(r"(peraturan mahkamah|acara|registrasi|persidangan)", lowered, flags=re.IGNORECASE):
            ref = normalize_article_reference(line)
            if ref and ref not in procedural_articles:
                procedural_articles.append(ref)

    obj = []
    for pattern in [
        r"pengujian\s+undang-undang\s+nomor\s+[^,;\n]+",
        r"pengujian\s+undang-undang\s+terhadap\s+u?u?d?\s*1945",
        r"objek\s+uji[:\s]+(.+)",
    ]:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            candidate = normalize_article_reference(match.group(0)) or normalize_whitespace(match.group(0).rstrip(".;,"))
            if candidate not in obj:
                obj.append(candidate)
    basis.object_of_review = obj
    opening = normalize_whitespace(source_text[:4000])
    opening = re.sub(r"Undang\s*-\s*Undang", "Undang-Undang", opening, flags=re.I)
    challenged_law = re.search(
        r"Pengujian\s+(Undang-Undang\s+Nomor\s+.+?)\s+terhad\s*ap\s+Undang-Undang\s+Dasar",
        opening, re.I,
    )
    if challenged_law:
        basis.object_of_review = [challenged_law.group(1)]
    basis.constitutional_articles = constitutional_articles
    basis.procedural_articles = procedural_articles

    evidence = []
    for match in re.finditer(r"\b(?:bukti|alat bukti)\s*(?:p\s*-?\s*)?\d+[a-z]?\b", text, flags=re.IGNORECASE):
        candidate = " ".join(match.group(0).upper().split())
        if candidate not in evidence:
            evidence.append(candidate)
    for case_number in extract_case_numbers(text):
        candidate = f"REFERENSI:{case_number}"
        if candidate not in evidence:
            evidence.append(candidate)
    basis.evidence = evidence
    return basis
