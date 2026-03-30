from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .pipeline import summarize_json_directory


def build_pipeline_report(
    parsed_dir: str | Path = "data/parsed_json",
    validated_dir: str | Path = "data/validated_json",
    review_dir: str | Path = "data/review_queue",
) -> dict[str, Any]:
    parsed = summarize_json_directory(parsed_dir)
    validated = summarize_json_directory(validated_dir)
    review = summarize_json_directory(review_dir)
    return {
        "parsed": parsed,
        "validated": validated,
        "review_queue": review,
    }


def write_pipeline_report(
    output_path: str | Path,
    parsed_dir: str | Path = "data/parsed_json",
    validated_dir: str | Path = "data/validated_json",
    review_dir: str | Path = "data/review_queue",
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = build_pipeline_report(parsed_dir=parsed_dir, validated_dir=validated_dir, review_dir=review_dir)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
