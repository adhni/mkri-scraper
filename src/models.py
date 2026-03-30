from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SCHEMA_VERSION = "1.0.0"


def _empty_list() -> list[Any]:
    return []


@dataclass
class SourceInfo:
    pdf_path: str
    file_name: str
    page_count: int | None = None
    text_extraction_engine: str | None = None


@dataclass
class ParserInfo:
    status: str = "ok"
    warnings: list[str] = field(default_factory=_empty_list)
    failed_extractors: list[str] = field(default_factory=_empty_list)


@dataclass
class DocumentInfo:
    document_type: str | None = None
    case_type: str | None = None
    case_number: str | None = None
    related_case_numbers: list[str] = field(default_factory=_empty_list)
    title: str | None = None
    decision_date: str | None = None
    decision_date_raw: str | None = None
    summary: str | None = None


@dataclass
class PersonLike:
    name: str
    role: str
    description: str | None = None


@dataclass
class Parties:
    applicants: list[PersonLike] = field(default_factory=_empty_list)
    legal_counsels: list[PersonLike] = field(default_factory=_empty_list)
    respondents: list[PersonLike] = field(default_factory=_empty_list)
    experts: list[PersonLike] = field(default_factory=_empty_list)
    witnesses: list[PersonLike] = field(default_factory=_empty_list)
    amicus_curiae: list[PersonLike] = field(default_factory=_empty_list)


@dataclass
class LegalBasis:
    object_of_review: list[str] = field(default_factory=_empty_list)
    constitutional_articles: list[str] = field(default_factory=_empty_list)
    procedural_articles: list[str] = field(default_factory=_empty_list)
    evidence: list[str] = field(default_factory=_empty_list)


@dataclass
class Outcome:
    decision_type: str | None = None
    dictum: list[str] = field(default_factory=_empty_list)
    summary: str | None = None


@dataclass
class Adjudicators:
    judges: list[str] = field(default_factory=_empty_list)
    clerks: list[str] = field(default_factory=_empty_list)


@dataclass
class Relations:
    joined_cases: list[str] = field(default_factory=_empty_list)
    referenced_cases: list[str] = field(default_factory=_empty_list)


@dataclass
class ValidationInfo:
    schema_errors: list[str] = field(default_factory=_empty_list)
    business_rule_errors: list[str] = field(default_factory=_empty_list)


@dataclass
class Section:
    heading: str
    slug: str
    text: str
    start_line: int | None = None
    end_line: int | None = None


@dataclass
class MkriCaseRecord:
    schema_version: str = SCHEMA_VERSION
    source: SourceInfo | None = None
    parser: ParserInfo = field(default_factory=ParserInfo)
    document: DocumentInfo = field(default_factory=DocumentInfo)
    sections: list[Section] = field(default_factory=_empty_list)
    parties: Parties = field(default_factory=Parties)
    legal_basis: LegalBasis = field(default_factory=LegalBasis)
    proceedings: list[str] = field(default_factory=_empty_list)
    outcome: Outcome = field(default_factory=Outcome)
    adjudicators: Adjudicators = field(default_factory=Adjudicators)
    relations: Relations = field(default_factory=Relations)
    validation: ValidationInfo = field(default_factory=ValidationInfo)

    def to_dict(self) -> dict[str, Any]:
        def convert(value: Any) -> Any:
            if isinstance(value, list):
                return [convert(item) for item in value]
            if hasattr(value, "__dataclass_fields__"):
                return {key: convert(getattr(value, key)) for key in value.__dataclass_fields__}
            return value

        return convert(self)
