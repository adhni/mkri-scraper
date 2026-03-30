from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SOURCE_PRIORITY = ["review_queue", "validated_json", "parsed_json"]


@dataclass
class CaseRecord:
    case_id: str
    source: str
    path: Path
    payload: dict[str, Any]
    available_sources: dict[str, str]


def _iter_json_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(item for item in path.glob("*.json") if item.is_file())


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_case_catalog(
    parsed_dir: str | Path = "data/parsed_json",
    validated_dir: str | Path = "data/validated_json",
    review_dir: str | Path = "data/review_queue",
) -> list[CaseRecord]:
    directories = {
        "parsed_json": Path(parsed_dir),
        "validated_json": Path(validated_dir),
        "review_queue": Path(review_dir),
    }
    grouped: dict[str, dict[str, Path]] = {}
    for source, root in directories.items():
        for json_path in _iter_json_files(root):
            grouped.setdefault(json_path.stem, {})[source] = json_path

    records: list[CaseRecord] = []
    for case_id, source_map in sorted(grouped.items()):
        chosen_source = next(source for source in SOURCE_PRIORITY if source in source_map)
        chosen_path = source_map[chosen_source]
        records.append(
            CaseRecord(
                case_id=case_id,
                source=chosen_source,
                path=chosen_path,
                payload=_load_json(chosen_path),
                available_sources={name: str(path) for name, path in source_map.items()},
            )
        )
    return records


def summarize_case(record: CaseRecord) -> dict[str, Any]:
    payload = record.payload
    document = payload.get("document", {})
    parties = payload.get("parties", {})
    parser_info = payload.get("parser", {})
    validation = payload.get("validation", {})
    outcome = payload.get("outcome", {})
    return {
        "case_id": record.case_id,
        "source": record.source,
        "file_name": payload.get("source", {}).get("file_name", f"{record.case_id}.json"),
        "document_type": document.get("document_type"),
        "case_number": document.get("case_number"),
        "decision_date": document.get("decision_date"),
        "title": document.get("title"),
        "status": parser_info.get("status"),
        "needs_manual_review": validation.get("needs_manual_review", False),
        "review_flags": validation.get("review_flags", []),
        "applicant_count": len(parties.get("applicants", [])),
        "respondent_count": len(parties.get("respondents", [])),
        "outcome_summary": outcome.get("summary"),
        "available_sources": record.available_sources,
    }


def filter_case_summaries(
    summaries: list[dict[str, Any]],
    query: str = "",
    status: str = "",
    document_type: str = "",
    source: str = "",
    review_flag: str = "",
    review_only: bool = False,
) -> list[dict[str, Any]]:
    normalized_query = query.strip().lower()
    out: list[dict[str, Any]] = []
    for item in summaries:
        if status and item.get("status") != status:
            continue
        if document_type and item.get("document_type") != document_type:
            continue
        if source and item.get("source") != source:
            continue
        if review_flag and review_flag not in item.get("review_flags", []):
            continue
        if review_only and not item.get("needs_manual_review"):
            continue
        if normalized_query:
            haystack = " ".join(
                str(item.get(key, "") or "")
                for key in ["case_number", "title", "outcome_summary", "file_name", "document_type"]
            ).lower()
            if normalized_query not in haystack:
                continue
        out.append(item)
    return out


def build_dashboard_stats(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    document_type_counts: dict[str, int] = {}
    review_flag_counts: dict[str, int] = {}
    for item in summaries:
        status = item.get("status") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        doc_type = item.get("document_type") or "unknown"
        document_type_counts[doc_type] = document_type_counts.get(doc_type, 0) + 1
        for flag in item.get("review_flags", []):
            review_flag_counts[flag] = review_flag_counts.get(flag, 0) + 1
    return {
        "total_cases": len(summaries),
        "needs_review": sum(1 for item in summaries if item.get("needs_manual_review")),
        "status_counts": status_counts,
        "document_type_counts": document_type_counts,
        "review_flag_counts": dict(sorted(review_flag_counts.items(), key=lambda pair: pair[1], reverse=True)),
    }


def get_case_record(
    case_id: str,
    parsed_dir: str | Path = "data/parsed_json",
    validated_dir: str | Path = "data/validated_json",
    review_dir: str | Path = "data/review_queue",
) -> CaseRecord | None:
    for record in build_case_catalog(parsed_dir=parsed_dir, validated_dir=validated_dir, review_dir=review_dir):
        if record.case_id == case_id:
            return record
    return None
