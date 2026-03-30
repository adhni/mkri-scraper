from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .extractors import (
    extract_adjudicators,
    detect_document_info,
    extract_legal_basis,
    extract_outcome,
    extract_parties,
    extract_proceedings,
    extract_relations,
)
from .manual_truth import scaffold_manual_truth_file
from .models import MkriCaseRecord, ParserInfo, Section, SourceInfo
from .pdf_text import extract_pdf_text
from .section_splitter import split_sections
from .validators import collect_review_flags, load_schema, validate_business_rules, validate_schema


class MkriParser:
    def __init__(self, schema_path: str | Path = "schemas/mkri_case.schema.json") -> None:
        self.schema_path = Path(schema_path)
        self.schema = load_schema(self.schema_path)

    def parse_pdf(self, pdf_path: str | Path) -> MkriCaseRecord:
        pdf_path = Path(pdf_path)
        extracted = extract_pdf_text(pdf_path)
        return self.parse_text(
            text=extracted.text,
            source=SourceInfo(
                pdf_path=str(pdf_path),
                file_name=pdf_path.name,
                page_count=extracted.page_count,
                text_extraction_engine=extracted.engine,
            ),
        )

    def parse_text(self, text: str, source: SourceInfo) -> MkriCaseRecord:
        record = MkriCaseRecord(source=source)
        warnings: list[str] = []
        failed_extractors: list[str] = []
        try:
            sections = split_sections(text)
            record.sections = sections
        except Exception as exc:  # pragma: no cover - defensive.
            warnings.append(f"section splitter failed: {exc}")
            failed_extractors.append("section_splitter")
            sections = [Section(heading="pembuka", slug="pembuka", text=text)]
            record.sections = sections

        def guarded(name: str, fn):
            try:
                return fn()
            except Exception as exc:  # pragma: no cover - defensive.
                warnings.append(f"{name} failed: {exc}")
                failed_extractors.append(name)
                return None

        doc = guarded("document", lambda: detect_document_info(text)) or {}
        record.document.document_type = doc.get("document_type")
        record.document.case_type = doc.get("case_type")
        record.document.case_number = doc.get("case_number")
        record.document.related_case_numbers = doc.get("related_case_numbers", [])
        record.document.title = doc.get("title")
        record.document.decision_date = doc.get("decision_date")
        record.document.decision_date_raw = doc.get("decision_date_raw")

        record.parties = guarded("parties", lambda: extract_parties(sections, text)) or record.parties
        record.legal_basis = guarded("legal_basis", lambda: extract_legal_basis(sections, text)) or record.legal_basis
        record.proceedings = guarded("proceedings", lambda: extract_proceedings(sections, text)) or record.proceedings
        record.outcome = guarded("outcome", lambda: extract_outcome(sections, text, record.document.document_type)) or record.outcome
        record.adjudicators = guarded("adjudicators", lambda: extract_adjudicators(sections, text)) or record.adjudicators
        record.relations = guarded("relations", lambda: extract_relations(sections, text)) or record.relations

        payload = record.to_dict()
        schema_errors = validate_schema(payload, self.schema)
        business_errors = validate_business_rules(payload)
        review_flags = collect_review_flags(payload)
        record.validation.schema_errors = schema_errors
        record.validation.business_rule_errors = business_errors
        record.validation.review_flags = review_flags
        record.validation.needs_manual_review = bool(schema_errors or business_errors or review_flags)
        warnings.extend(schema_errors)
        warnings.extend(business_errors)
        warnings.extend(f"review:{flag}" for flag in review_flags)
        record.parser.warnings = warnings
        record.parser.failed_extractors = failed_extractors
        if failed_extractors:
            record.parser.status = "partial" if warnings else "failed"
        elif schema_errors or business_errors or review_flags:
            record.parser.status = "partial"
        else:
            record.parser.status = "ok"
        if record.parser.status == "ok" and warnings:
            record.parser.status = "partial"
        return record

    def parse_pdf_file_to_json(self, pdf_path: str | Path, output_dir: str | Path = "data/parsed_json") -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        record = self.parse_pdf(pdf_path)
        output_path = output_dir / f"{Path(pdf_path).stem}.json"
        output_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return output_path

    def validate_json_file(self, json_path: str | Path, output_dir: str | Path = "data/validated_json", review_dir: str | Path = "data/review_queue") -> Path:
        import json

        json_path = Path(json_path)
        output_dir = Path(output_dir)
        review_dir = Path(review_dir)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        schema_errors = validate_schema(payload, self.schema)
        business_errors = validate_business_rules(payload)
        review_flags = collect_review_flags(payload)
        payload.setdefault("validation", {})
        payload["validation"]["schema_errors"] = schema_errors
        payload["validation"]["business_rule_errors"] = business_errors
        payload["validation"]["review_flags"] = review_flags
        payload["validation"]["needs_manual_review"] = bool(schema_errors or business_errors or review_flags)

        target_dir = output_dir if not (schema_errors or business_errors or review_flags) else review_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        sibling_dir = review_dir if target_dir == output_dir else output_dir
        sibling_path = sibling_dir / json_path.name
        if sibling_path.exists():
            sibling_path.unlink()
        out_path = target_dir / json_path.name
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out_path

    def scaffold_manual_truth(self, input_path: str | Path | list[Path], output_dir: str | Path = "tests/manual_truth") -> list[Path]:
        if isinstance(input_path, list):
            json_files = [item for item in input_path if item.is_file()]
        else:
            input_path = Path(input_path)
            json_files = [input_path] if input_path.is_file() else sorted(input_path.rglob("*.json"))
        created: list[Path] = []
        for json_path in json_files:
            created.append(scaffold_manual_truth_file(json_path, output_dir=output_dir))
        return created
