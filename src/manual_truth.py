from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_manual_truth_template(payload: dict[str, Any]) -> dict[str, Any]:
    document = payload.get("document", {})
    parties = payload.get("parties", {})
    outcome = payload.get("outcome", {})
    legal_basis = payload.get("legal_basis", {})

    return {
        "source_file": payload.get("source", {}).get("file_name"),
        "status": "needs_annotation",
        "verified_fields": {
            "document_type": document.get("document_type"),
            "case_number": document.get("case_number"),
            "decision_date": document.get("decision_date"),
            "applicants": [item.get("name") for item in parties.get("applicants", [])],
            "legal_counsels": [item.get("name") for item in parties.get("legal_counsels", [])],
            "respondents": [item.get("name") for item in parties.get("respondents", [])],
            "constitutional_articles": legal_basis.get("constitutional_articles", []),
            "procedural_articles": legal_basis.get("procedural_articles", []),
            "outcome_summary": outcome.get("summary"),
            "outcome_dictum": outcome.get("dictum", []),
        },
        "notes": "",
        "accept_parser_output": False,
    }


def scaffold_manual_truth_file(parsed_json_path: str | Path, output_dir: str | Path = "tests/manual_truth") -> Path:
    parsed_json_path = Path(parsed_json_path)
    payload = json.loads(parsed_json_path.read_text(encoding="utf-8"))
    template = build_manual_truth_template(payload)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / parsed_json_path.name
    out_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
