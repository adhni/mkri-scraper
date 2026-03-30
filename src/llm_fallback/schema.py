from __future__ import annotations

FALLBACK_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {"type": ["string", "null"]},
        "case_number": {"type": ["string", "null"]},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
}
