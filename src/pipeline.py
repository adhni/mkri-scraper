from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .parser import MkriParser


def _iter_json_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(item for item in path.rglob("*.json") if item.is_file())


def _iter_pdf_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(item for item in path.rglob("*.pdf") if item.is_file())


def _resolve_json_inputs(path_or_paths: str | Path | list[Path]) -> tuple[str, list[Path]]:
    if isinstance(path_or_paths, list):
        files = [item for item in path_or_paths if item.is_file()]
        return "<explicit-list>", sorted(files)
    root = Path(path_or_paths)
    return str(root), _iter_json_files(root)


def summarize_json_directory(path: str | Path | list[Path]) -> dict[str, Any]:
    root_label, files = _resolve_json_inputs(path)
    status_counter: Counter[str] = Counter()
    document_type_counter: Counter[str] = Counter()
    review_flag_counter: Counter[str] = Counter()
    failed_extractors_counter: Counter[str] = Counter()
    files_needing_review: list[str] = []
    files_with_failures: list[str] = []

    for json_path in files:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        parser_info = payload.get("parser", {})
        validation = payload.get("validation", {})
        document = payload.get("document", {})

        status = parser_info.get("status", "unknown")
        status_counter[status] += 1

        document_type = document.get("document_type") or "unknown"
        document_type_counter[document_type] += 1

        for flag in validation.get("review_flags", []):
            review_flag_counter[flag] += 1
        for extractor in parser_info.get("failed_extractors", []):
            failed_extractors_counter[extractor] += 1

        if validation.get("needs_manual_review"):
            files_needing_review.append(json_path.name)
        if status == "failed":
            files_with_failures.append(json_path.name)

    return {
        "root": root_label,
        "file_count": len(files),
        "status_counts": dict(status_counter),
        "document_type_counts": dict(document_type_counter),
        "review_flag_counts": dict(review_flag_counter.most_common()),
        "failed_extractor_counts": dict(failed_extractors_counter.most_common()),
        "files_needing_review": files_needing_review,
        "files_with_failures": files_with_failures,
    }


def run_pipeline(
    pdf_input: str | Path,
    parsed_dir: str | Path = "data/parsed_json",
    validated_dir: str | Path = "data/validated_json",
    review_dir: str | Path = "data/review_queue",
    manual_truth_dir: str | Path | None = None,
) -> dict[str, Any]:
    parser = MkriParser()
    pdf_input = Path(pdf_input)
    parsed_dir = Path(parsed_dir)
    validated_dir = Path(validated_dir)
    review_dir = Path(review_dir)

    parse_failures: list[str] = []
    parse_outputs: list[str] = []
    for pdf_path in _iter_pdf_files(pdf_input):
        try:
            out_path = parser.parse_pdf_file_to_json(pdf_path, output_dir=parsed_dir)
            parse_outputs.append(str(out_path))
        except Exception as exc:
            parse_failures.append(f"{pdf_path.name}: {exc}")

    validate_outputs: list[str] = []
    review_outputs: list[str] = []
    parsed_json_paths = [Path(item) for item in parse_outputs]
    for json_path in parsed_json_paths:
        try:
            out_path = parser.validate_json_file(json_path, output_dir=validated_dir, review_dir=review_dir)
            validate_outputs.append(str(out_path))
            if Path(out_path).parent == review_dir:
                review_outputs.append(str(out_path))
        except Exception as exc:
            parse_failures.append(f"{json_path.name}: {exc}")

    manual_truth_outputs: list[str] = []
    if manual_truth_dir is not None:
        manual_truth_outputs = [
            str(item) for item in parser.scaffold_manual_truth([Path(item) for item in review_outputs], output_dir=manual_truth_dir)
        ]

    return {
        "parse_outputs": parse_outputs,
        "validate_outputs": validate_outputs,
        "manual_truth_outputs": manual_truth_outputs,
        "failures": parse_failures,
        "parsed_summary": summarize_json_directory(parsed_json_paths) if parsed_json_paths else {},
        "review_summary": summarize_json_directory([Path(item) for item in review_outputs]) if review_outputs else {},
        "validated_summary": summarize_json_directory([Path(item) for item in validate_outputs]) if validate_outputs else {},
    }


def ingest_pdf_files(
    pdf_paths: list[str | Path],
    parsed_dir: str | Path = "data/parsed_json",
    validated_dir: str | Path = "data/validated_json",
    review_dir: str | Path = "data/review_queue",
    manual_truth_dir: str | Path | None = None,
) -> dict[str, Any]:
    parser = MkriParser()
    parsed_dir = Path(parsed_dir)
    validated_dir = Path(validated_dir)
    review_dir = Path(review_dir)

    parse_failures: list[str] = []
    parse_outputs: list[str] = []
    for pdf_path in [Path(item) for item in pdf_paths]:
        if not pdf_path.is_file():
            parse_failures.append(f"{pdf_path}: file not found")
            continue
        try:
            out_path = parser.parse_pdf_file_to_json(pdf_path, output_dir=parsed_dir)
            parse_outputs.append(str(out_path))
        except Exception as exc:
            parse_failures.append(f"{pdf_path.name}: {exc}")

    validate_outputs: list[str] = []
    review_outputs: list[str] = []
    parsed_json_paths = [Path(item) for item in parse_outputs]
    for json_path in parsed_json_paths:
        try:
            out_path = parser.validate_json_file(json_path, output_dir=validated_dir, review_dir=review_dir)
            validate_outputs.append(str(out_path))
            if Path(out_path).parent == review_dir:
                review_outputs.append(str(out_path))
        except Exception as exc:
            parse_failures.append(f"{json_path.name}: {exc}")

    manual_truth_outputs: list[str] = []
    if manual_truth_dir is not None:
        manual_truth_outputs = [
            str(item) for item in parser.scaffold_manual_truth([Path(item) for item in review_outputs], output_dir=manual_truth_dir)
        ]

    return {
        "pdf_inputs": [str(Path(item)) for item in pdf_paths],
        "parse_outputs": parse_outputs,
        "validate_outputs": validate_outputs,
        "manual_truth_outputs": manual_truth_outputs,
        "failures": parse_failures,
        "parsed_summary": summarize_json_directory(parsed_json_paths) if parsed_json_paths else {},
        "review_summary": summarize_json_directory([Path(item) for item in review_outputs]) if review_outputs else {},
        "validated_summary": summarize_json_directory([Path(item) for item in validate_outputs]) if validate_outputs else {},
    }
