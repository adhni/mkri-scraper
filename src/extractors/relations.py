from __future__ import annotations

from ..models import Relations, Section
from ..normalizers import extract_case_numbers


def extract_relations(sections: list[Section], source_text: str) -> Relations:
    blob = "\n\n".join(section.text for section in sections) + "\n" + source_text
    cases = extract_case_numbers(blob)
    return Relations(joined_cases=cases, referenced_cases=cases)

