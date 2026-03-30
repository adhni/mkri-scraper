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
