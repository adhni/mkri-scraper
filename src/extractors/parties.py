from __future__ import annotations

import re

from ..models import Parties, PersonLike, Section
from ..normalizers import normalize_party_name, normalize_whitespace

ROLE_PATTERNS = {
    "applicants": [r"\bpemohon\b", r"\bpara pemohon\b"],
    "legal_counsels": [r"\bkuasa hukum\b", r"\bpemberi kuasa\b", r"\bkuasa pemohon\b", r"\bmemberi kuasa\b"],
    "respondents": [r"\btermohon\b", r"\bpemerintah\b", r"\bdpr\b", r"\bpresiden\b", r"\bpihak terkait\b"],
    "experts": [r"\bahli\b"],
    "witnesses": [r"\bsaksi\b"],
    "amicus_curiae": [r"\bamicus curiae\b"],
}


NAME_BLOCK_RE = re.compile(
    r"(?is)(?:^|\n)\s*(?:\d+\.\s*)?Nama\s*:\s*(?P<name>.+?)(?=\n\s*(?:Pekerjaan|Alamat|Selanjutnya disebut sebagai|Nama\s*:|Dalam hal ini|Sebagai|Membaca|Mendengar|Memeriksa|Menimbang|$))"
)

AMICUS_RE = re.compile(
    r"(?is)amicus curiae\s*(?:dari|:)\s*(?P<name>.+?)(?=(?:;|\n|\.))"
)

KUASA_RE = re.compile(
    r"(?is)(?:memberi kuasa kepada|memberikan kuasa kepada|kuasa kepada)\s*(?P<name>.+?)(?=(?:;|\n|bertindak|selanjutnya|kesemuanya|yang berkedudukan|$))"
)

TITLE_TOKEN_RE = re.compile(
    r"^(?:S\.?H\.?|M\.?H\.?|M\.?H\.?um\.?|M\.?A\.?P\.?|M\.?K\.?n\.?|M\.?K\.?om\.?|M\.?I\.?K\.?om\.?|S\.?I\.?K\.?om\.?|S\.?K\.?om\.?|LL\.?M\.?|A\.?P\.?|A\.?P\.?T\.?|M\.?Ag\.?|M\.?M\.?)$",
    re.IGNORECASE,
)


def _strip_representation_clause(text: str) -> str:
    cleaned = re.split(r"\s+yang\s+dalam\s+hal\s+ini\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
    cleaned = re.split(r"\s+yang\s+diwakili\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    cleaned = re.split(r"\s+selaku\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    return cleaned


def _split_name_list(text: str) -> list[str]:
    tokens = [part.strip() for part in re.split(r",|\bdan\b|/|\+|;", text, flags=re.IGNORECASE) if part.strip()]
    names: list[str] = []
    current: str | None = None
    for token in tokens:
        if TITLE_TOKEN_RE.match(token):
            if current:
                current = f"{current}, {token}"
            continue
        if current:
            names.append(current)
        current = token
    if current:
        names.append(current)
    return names


def _clean_candidate(candidate: str) -> str:
    candidate = _strip_representation_clause(candidate)
    candidate = normalize_party_name(candidate)
    candidate = re.sub(r"\s+", " ", candidate)
    return candidate.strip()


def _extract_people_from_name_blocks(text: str, role: str) -> list[PersonLike]:
    people: list[PersonLike] = []
    for match in NAME_BLOCK_RE.finditer(text):
        candidate = _clean_candidate(match.group("name"))
        if candidate:
            people.append(PersonLike(name=candidate, role=role))
    return people


def _opening_block(text: str) -> str:
    lines = text.splitlines()
    collected: list[str] = []
    stop_re = re.compile(
        r"^\s*(?:\d+\.\s*)?(?:duduk perkara|pertimbangan hukum|menimbang|konklusi|amar putusan|amar penetapan|mengadili|menetapkan)\b",
        re.IGNORECASE,
    )
    for line in lines:
        if stop_re.search(line):
            break
        collected.append(line)
    return "\n".join(collected)


def _blocks_around_phrase(text: str, phrase: str, span: int = 20) -> list[str]:
    lines = text.splitlines()
    blocks: list[str] = []
    for index, line in enumerate(lines):
        if phrase in line.lower():
            blocks.append("\n".join(lines[index : index + span]))
    return blocks


def _extract_from_kuasa(text: str) -> list[PersonLike]:
    people: list[PersonLike] = []
    for match in KUASA_RE.finditer(text):
        blob = _clean_candidate(match.group("name"))
        for name in _split_name_list(blob):
            cleaned = _clean_candidate(name)
            if cleaned and len(cleaned) > 2:
                people.append(PersonLike(name=cleaned, role="legal_counsel"))
    return people


def _extract_amicus_names(text: str) -> list[PersonLike]:
    names: list[PersonLike] = []
    for match in AMICUS_RE.finditer(text):
        blob = _clean_candidate(match.group("name"))
        for name in _split_name_list(blob):
            cleaned = _clean_candidate(name)
            if cleaned:
                names.append(PersonLike(name=cleaned, role="amicus_curiae"))
    return names


def _extract_respondents(text: str) -> list[PersonLike]:
    respondents: list[PersonLike] = []
    mappings = [
        ("DPR", r"\bDPR\b"),
        ("Presiden", r"\bPresiden\b"),
        ("Pemerintah", r"\bPemerintah\b"),
        ("Pihak Terkait", r"\bPihak Terkait\b"),
    ]
    for name, pattern in mappings:
        if re.search(pattern, text, flags=re.IGNORECASE):
            respondents.append(PersonLike(name=name, role="respondent"))
    return respondents


def _dedupe(items: list[PersonLike]) -> list[PersonLike]:
    seen: set[tuple[str, str]] = set()
    out: list[PersonLike] = []
    for item in items:
        key = (item.name.lower(), item.role.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def extract_parties(sections: list[Section], source_text: str) -> Parties:
    parties = Parties()
    section_blob = "\n\n".join(section.text for section in sections)
    heading_blob = "\n".join(section.heading for section in sections)
    opening_blob = _opening_block(source_text)

    parties.applicants.extend(_extract_people_from_name_blocks(opening_blob, "applicant"))
    if not parties.applicants:
        # Ketetapan introduces applicants in a sentence, not a 'Nama:' table.
        opening = normalize_whitespace(source_text[:5000])
        match = re.search(
            r"(?:atas nama|bernama)\s+(.+?)(?=\s*\(|\s*,?\s*yang\b)", opening, re.I,
        ) or re.search(
            r"permohonan bertanggal\s+.+?\s+dari\s+(.+?)(?=,?\s+yang\b)", opening, re.I,
        )
        if match:
            for name in _split_name_list(match.group(1)):
                parties.applicants.append(PersonLike(name=_clean_candidate(name), role="applicant"))
        else:
            match = re.search(r"(?im)^\s*Pemohon\s*:\s*(.+)$", source_text)
            if match:
                parties.applicants.append(PersonLike(name=_clean_candidate(match.group(1)), role="applicant"))

    parties.legal_counsels.extend(_extract_from_kuasa(opening_blob))
    parties.respondents.extend(_extract_respondents(section_blob + "\n" + heading_blob))
    parties.amicus_curiae.extend(_extract_amicus_names(opening_blob))

    expert_blocks = _blocks_around_phrase(source_text, "keterangan ahli")
    witness_blocks = _blocks_around_phrase(source_text, "keterangan saksi")
    for block in expert_blocks:
        parties.experts.extend(_extract_people_from_name_blocks(block, "expert"))
    for block in witness_blocks:
        parties.witnesses.extend(_extract_people_from_name_blocks(block, "witness"))

    parties.applicants = _dedupe(parties.applicants)
    parties.legal_counsels = _dedupe(parties.legal_counsels)
    parties.respondents = _dedupe(parties.respondents)
    parties.experts = _dedupe(parties.experts)
    parties.witnesses = _dedupe(parties.witnesses)
    parties.amicus_curiae = _dedupe(parties.amicus_curiae)
    return parties
