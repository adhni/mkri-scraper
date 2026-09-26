from __future__ import annotations

import re

from ..normalizers import INDONESIAN_DATE_RE, extract_case_numbers, normalize_case_number, normalize_indonesian_date, normalize_whitespace

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
    # Public pronouncement can occur months after the judges' deliberation.
    closings = list(re.finditer(r"(?im)^\s*Demikian\s+(?:diputus\w*|ditetapkan)\b", text))
    closing = text[closings[-1].start():] if closings else "\n".join(
        line for line in text.splitlines()
        if re.match(r"\s*(?:diucapkan|dibacakan|ditetapkan)\b", line, re.I)
    )
    closing = normalize_whitespace(re.sub(r"(?m)^\s*\d+\s*$", "", closing))
    anchors = list(re.finditer(r"\b(?:diucapkan|dibacakan)\b", closing, re.I))
    if not anchors:
        anchors = list(re.finditer(r"\bditetapkan\b", closing, re.I))
    for anchor in anchors:
        candidate = closing[anchor.end():anchor.end() + 240]
        match = INDONESIAN_DATE_RE.search(candidate)
        if match and (parsed_date := normalize_indonesian_date(match.group())):
            decision_date_raw = match.group()
            decision_date = parsed_date
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
