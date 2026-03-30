from __future__ import annotations

import re

from ..normalizers import extract_case_numbers, normalize_case_number, normalize_indonesian_date, normalize_whitespace

PUTUSAN_RE = re.compile(r"\bputusan\b", re.IGNORECASE)
KETETAPAN_RE = re.compile(r"\bketetapan\b", re.IGNORECASE)
PUU_RE = re.compile(r"\bpuu\b", re.IGNORECASE)


def detect_document_info(text: str) -> dict[str, str | list[str] | None]:
    lines = [normalize_whitespace(line) for line in text.splitlines() if normalize_whitespace(line)]
    head = "\n".join(lines[:25])
    document_type = None
    if KETETAPAN_RE.search(head):
        document_type = "ketetapan"
    elif PUTUSAN_RE.search(head):
        document_type = "putusan"

    case_number = normalize_case_number(head) or (extract_case_numbers(head)[0] if extract_case_numbers(head) else None)
    decision_date = None
    decision_date_raw = None
    for pattern in [
        r"(?:ditetapkan|diucapkan|diputuskan|dibacakan).*?(\d{1,2}\s+[a-z]+\s+\d{4})",
        r"(?:jakarta|mahkamah konstitusi).*?(\d{1,2}\s+[a-z]+\s+\d{4})",
    ]:
        match = re.search(pattern, head, flags=re.IGNORECASE | re.DOTALL)
        if match:
            decision_date_raw = match.group(1)
            decision_date = normalize_indonesian_date(decision_date_raw)
            break

    title = lines[0] if lines else None
    case_type = "PUU" if PUU_RE.search(head) else None
    related_case_numbers = extract_case_numbers(head)
    if case_number and case_number in related_case_numbers:
        related_case_numbers = [item for item in related_case_numbers if item != case_number]

    return {
        "document_type": document_type,
        "case_type": case_type,
        "case_number": case_number,
        "related_case_numbers": related_case_numbers,
        "title": title,
        "decision_date": decision_date,
        "decision_date_raw": decision_date_raw,
    }

