from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SOURCE_PRIORITY = ["review_queue", "validated_json", "parsed_json"]
OUTCOME_LABELS = {
    "granted_partly": "Dikabulkan sebagian",
    "granted": "Dikabulkan",
    "rejected": "Ditolak",
    "inadmissible": "Tidak dapat diterima",
    "withdrawn": "Ditarik kembali",
    "dismissed": "Gugur",
    "unknown": "Belum teridentifikasi",
}


@dataclass
class CaseRecord:
    case_id: str
    source: str
    path: Path
    payload: dict[str, Any]
    available_sources: dict[str, str]


def _iter_json_files(path: Path) -> list[Path]:
    return sorted(path.glob("*.json")) if path.exists() else []


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_case_catalog(
    parsed_dir: str | Path = "data/parsed_json",
    validated_dir: str | Path = "data/validated_json",
    review_dir: str | Path = "data/review_queue",
    editorial_path: str | Path | None = None,
) -> list[CaseRecord]:
    directories = {"parsed_json": Path(parsed_dir), "validated_json": Path(validated_dir), "review_queue": Path(review_dir)}
    # Separate editorial notes survive re-parsing. Never overwrite source facts.
    notes_path = Path(editorial_path) if editorial_path is not None else Path(parsed_dir).parent / "editorial" / "cases.json"
    notes = _load_json(notes_path) if notes_path.is_file() else {}
    grouped: dict[str, dict[str, Path]] = {}
    for source, root in directories.items():
        for json_path in _iter_json_files(root):
            if json_path.is_file():
                grouped.setdefault(json_path.stem, {})[source] = json_path
    records = []
    for case_id, source_map in sorted(grouped.items()):
        chosen_source = next(source for source in SOURCE_PRIORITY if source in source_map)
        chosen_path = source_map[chosen_source]
        payload = _load_json(chosen_path)
        payload["editorial"] = notes.get(payload.get("document", {}).get("case_number"), {})
        records.append(CaseRecord(case_id, chosen_source, chosen_path, payload, {k: str(v) for k, v in source_map.items()}))
    return records


def classify_outcome(summary: str | None) -> str:
    text = (summary or "").casefold()
    if "penarikan" in text or "ditarik kembali" in text or "dicabut" in text:
        return "withdrawn"
    if "gugur" in text:
        return "dismissed"
    if "tidak dapat diterima" in text:
        return "inadmissible"
    if text.startswith("mengabulkan"):
        return "granted_partly" if "sebagian" in text else "granted"
    if text.startswith("menolak"):
        return "rejected"
    return "unknown"


def summarize_case(record: CaseRecord) -> dict[str, Any]:
    payload = record.payload
    document = payload.get("document", {})
    parties = payload.get("parties", {})
    parser_info = payload.get("parser", {})
    validation = payload.get("validation", {})
    outcome = payload.get("outcome", {})
    editorial = payload.get("editorial", {})
    law = editorial.get("law") or "; ".join(payload.get("legal_basis", {}).get("object_of_review", [])[:1])
    title = editorial.get("title") or document.get("title")
    if not title or title.upper() in {"PUTUSAN", "KETETAPAN", "SALINAN", "SALINA N"}:
        title = law or "Perkara " + str(document.get("case_number") or record.case_id)
    outcome_key = classify_outcome(outcome.get("summary"))
    date = document.get("decision_date")
    fields = {
        "case_id": record.case_id,
        "source": record.source,
        "file_name": payload.get("source", {}).get("file_name", f"{record.case_id}.json"),
        "document_type": document.get("document_type"),
        "case_number": document.get("case_number"),
        "decision_date": date,
        "year": date[:4] if date else "",
        "title": title,
        "description": editorial.get("summary") or document.get("summary") or outcome.get("summary"),
        "topics": editorial.get("topics", []),
        "law": law,
        "editorial": bool(editorial),
        "status": parser_info.get("status"),
        "needs_manual_review": validation.get("needs_manual_review", False),
        "review_flags": validation.get("review_flags", []),
        "applicant_count": len(parties.get("applicants", [])),
        "respondent_count": len(parties.get("respondents", [])),
        "outcome_summary": outcome.get("summary"),
        "outcome_key": outcome_key,
        "outcome_label": OUTCOME_LABELS[outcome_key],
        "available_sources": record.available_sources,
    }
    names = [person.get("name", "") for group in parties.values() if isinstance(group, list) for person in group if isinstance(person, dict)]
    text = " ".join(str(fields.get(key) or "") for key in ["case_number", "title", "description", "law", "file_name", "document_type", "outcome_summary"])
    text += " " + " ".join(names + fields["topics"])
    text += " " + " ".join(f"{s.get('heading', '')} {s.get('text', '')}" for s in payload.get("sections", []))
    fields["_search_text"] = " ".join(text.casefold().split())
    return fields


def public_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in summary.items() if not key.startswith("_")}


def filter_case_summaries(
    summaries: list[dict[str, Any]], query: str = "", status: str = "", document_type: str = "",
    source: str = "", review_flag: str = "", review_only: bool = False,
    topic: str = "", year: str = "", outcome: str = "",
) -> list[dict[str, Any]]:
    terms = query.casefold().split()
    out = []
    for item in summaries:
        if any(value and item.get(key) != value for key, value in [
            ("status", status), ("document_type", document_type), ("source", source), ("year", year), ("outcome_key", outcome),
        ]):
            continue
        if topic and topic not in item.get("topics", []):
            continue
        if review_flag and review_flag not in item.get("review_flags", []):
            continue
        if review_only and not item.get("needs_manual_review"):
            continue
        haystack = item.get("_search_text") or " ".join(str(item.get(key) or "") for key in ["case_number", "title", "outcome_summary", "file_name", "document_type"]).casefold()
        if terms and not all(term in haystack for term in terms):
            continue
        out.append(item)
    return out


def build_dashboard_stats(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    document_type_counts: dict[str, int] = {}
    review_flag_counts: dict[str, int] = {}
    topic_counts: dict[str, int] = {}
    years = set()
    for item in summaries:
        status = item.get("status") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        doc_type = item.get("document_type") or "unknown"
        document_type_counts[doc_type] = document_type_counts.get(doc_type, 0) + 1
        for flag in item.get("review_flags", []):
            review_flag_counts[flag] = review_flag_counts.get(flag, 0) + 1
        for topic in item.get("topics", []):
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        if item.get("year"):
            years.add(item["year"])
    return {
        "total_cases": len(summaries),
        "needs_review": sum(1 for item in summaries if item.get("needs_manual_review")),
        "status_counts": status_counts,
        "document_type_counts": document_type_counts,
        "review_flag_counts": dict(sorted(review_flag_counts.items(), key=lambda pair: pair[1], reverse=True)),
        "topic_counts": dict(sorted(topic_counts.items())),
        "years": sorted(years, reverse=True),
    }


def get_case_record(
    case_id: str, parsed_dir: str | Path = "data/parsed_json",
    validated_dir: str | Path = "data/validated_json", review_dir: str | Path = "data/review_queue",
) -> CaseRecord | None:
    return next((record for record in build_case_catalog(parsed_dir, validated_dir, review_dir) if record.case_id == case_id), None)
