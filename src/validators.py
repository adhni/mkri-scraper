from __future__ import annotations

from pathlib import Path
from typing import Any


def load_schema(schema_path: str | Path) -> dict[str, Any]:
    import json

    return json.loads(Path(schema_path).read_text(encoding="utf-8"))


def validate_schema(payload: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return _validate_schema_fallback(payload, schema)

    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.path)):
        path = "/".join(str(item) for item in error.path)
        errors.append(f"{path or '<root>'}: {error.message}")
    return errors


def _resolve_ref(schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported ref: {ref}")
    node: Any = schema
    for part in ref[2:].split("/"):
        node = node[part]
    if not isinstance(node, dict):
        raise TypeError("resolved ref must be a schema object")
    return node


def _schema_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def _validate_node(value: Any, node: dict[str, Any], path: list[str], root: dict[str, Any], errors: list[str]) -> None:
    if "$ref" in node:
        _validate_node(value, _resolve_ref(root, node["$ref"]), path, root, errors)
        return
    schema_type = node.get("type")
    if isinstance(schema_type, list):
        if not any(_schema_type_matches(value, item) for item in schema_type):
            errors.append(f"{'/'.join(path) or '<root>'}: expected one of {schema_type}")
            return
    elif isinstance(schema_type, str) and not _schema_type_matches(value, schema_type):
        errors.append(f"{'/'.join(path) or '<root>'}: expected {schema_type}")
        return
    if "enum" in node and value not in node["enum"]:
        errors.append(f"{'/'.join(path) or '<root>'}: value {value!r} not in enum")
        return
    if isinstance(value, dict):
        required = node.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{'/'.join(path + [key])}: missing required property")
        properties = node.get("properties", {})
        for key, child_schema in properties.items():
            if key in value:
                _validate_node(value[key], child_schema, path + [key], root, errors)
    if isinstance(value, list):
        items_schema = node.get("items")
        if items_schema:
            for index, item in enumerate(value):
                _validate_node(item, items_schema, path + [str(index)], root, errors)


def _validate_schema_fallback(payload: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _validate_node(payload, schema, [], schema, errors)
    return errors


def validate_business_rules(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    document = payload.get("document", {})
    parser = payload.get("parser", {})
    if not document.get("case_number"):
        errors.append("document.case_number is required by business rules")
    if not document.get("document_type"):
        errors.append("document.document_type could not be inferred")
    if parser.get("status") not in {"ok", "partial", "failed"}:
        errors.append("parser.status must be ok, partial, or failed")
    if parser.get("status") == "failed" and not parser.get("warnings"):
        errors.append("failed parses must include warnings")
    parties = payload.get("parties", {})
    if not any(parties.get(key) for key in ["applicants", "legal_counsels", "respondents", "experts", "witnesses", "amicus_curiae"]):
        errors.append("at least one party or participant should be detected")
    if not payload.get("outcome", {}).get("dictum"):
        errors.append("outcome.dictum should not be empty")
    return errors


def collect_review_flags(payload: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    document = payload.get("document", {})
    parties = payload.get("parties", {})
    outcome = payload.get("outcome", {})
    adjudicators = payload.get("adjudicators", {})
    legal_basis = payload.get("legal_basis", {})
    sections = payload.get("sections", [])

    applicants = parties.get("applicants", [])
    respondents = parties.get("respondents", [])
    legal_counsels = parties.get("legal_counsels", [])
    experts = parties.get("experts", [])
    witnesses = parties.get("witnesses", [])
    amici = parties.get("amicus_curiae", [])

    if len(sections) < 3:
        flags.append("too_few_sections_detected")
    if not document.get("decision_date"):
        flags.append("decision_date_missing")
    if not adjudicators.get("judges"):
        flags.append("judges_not_extracted")
    if len(applicants) == 0:
        flags.append("applicants_missing")
    if len(applicants) > 15:
        flags.append("applicant_count_high")
    if len(respondents) > 4:
        flags.append("respondent_count_high")
    if len(legal_counsels) > 8:
        flags.append("legal_counsel_count_high")
    if len(experts) > 5:
        flags.append("expert_count_high")
    if len(witnesses) > 5:
        flags.append("witness_count_high")
    if len(amici) > 3:
        flags.append("amicus_count_high")

    suspicious_party_markers = [
        "alamat",
        "pekerjaan",
        "menimbang",
        "membaca",
        "mendengar",
        "rapat permusyawaratan hakim",
    ]
    for group_name in ["applicants", "legal_counsels", "respondents", "experts", "witnesses", "amicus_curiae"]:
        for item in parties.get(group_name, []):
            name = (item.get("name") or "").lower()
            if not name:
                flags.append(f"{group_name}_contains_empty_name")
                continue
            if len(name) > 120:
                flags.append(f"{group_name}_contains_very_long_name")
                break
            if any(marker in name for marker in suspicious_party_markers):
                flags.append(f"{group_name}_contains_suspicious_text")
                break

    outcome_summary = (outcome.get("summary") or "").strip()
    normalized_outcome = outcome_summary.lower()
    allowed_outcome_prefixes = (
        "mengabulkan",
        "menolak",
        "menyatakan",
        "menerima",
        "memerintahkan",
        "menetapkan",
    )
    if not normalized_outcome:
        flags.append("outcome_summary_missing")
    elif not normalized_outcome.startswith(allowed_outcome_prefixes):
        flags.append("outcome_summary_not_in_amar_style")
    if len(outcome.get("dictum", [])) == 1 and len(outcome_summary) > 160:
        flags.append("outcome_summary_too_long")

    if document.get("document_type") == "putusan" and not legal_basis.get("constitutional_articles"):
        flags.append("constitutional_articles_missing_for_putusan")

    return list(dict.fromkeys(flags))
