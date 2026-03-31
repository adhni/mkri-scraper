from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pipeline import ingest_pdf_files


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"files": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"files": {}}
    if not isinstance(payload, dict):
        return {"files": {}}
    payload.setdefault("files", {})
    return payload


def _save_manifest(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _iter_pdf_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() == ".pdf" else []
    return sorted(item for item in path.rglob("*.pdf") if item.is_file())


def _safe_archive_path(destination_dir: Path, original_name: str) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    candidate = destination_dir / original_name
    if not candidate.exists():
        return candidate

    stem = Path(original_name).stem
    suffix = Path(original_name).suffix
    counter = 2
    while True:
        candidate = destination_dir / f"{stem}__{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def ingest_inbox(
    *,
    inbox_dir: str | Path = "data/inbox_pdfs",
    processed_dir: str | Path = "data/raw_pdfs/processed",
    failed_dir: str | Path = "data/raw_pdfs/failed",
    manifest_path: str | Path = "data/pipeline_state/inbox_manifest.json",
    parsed_dir: str | Path = "data/parsed_json",
    validated_dir: str | Path = "data/validated_json",
    review_dir: str | Path = "data/review_queue",
    manual_truth_dir: str | Path | None = None,
    move_files: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    inbox_dir = Path(inbox_dir)
    processed_dir = Path(processed_dir)
    failed_dir = Path(failed_dir)
    manifest_path = Path(manifest_path)
    manifest = _load_manifest(manifest_path)

    pdfs = _iter_pdf_files(inbox_dir)
    skipped: list[str] = []
    processed: list[dict[str, Any]] = []
    failures: list[str] = []
    success_count = 0
    review_count = 0
    failed_count = 0

    for pdf_path in pdfs:
        file_hash = _hash_file(pdf_path)
        existing = manifest["files"].get(file_hash)
        if existing and not force:
            skipped.append(str(pdf_path))
            continue

        ingest_result = ingest_pdf_files(
            pdf_paths=[pdf_path],
            parsed_dir=parsed_dir,
            validated_dir=validated_dir,
            review_dir=review_dir,
            manual_truth_dir=manual_truth_dir,
        )

        target_dir = processed_dir
        status = "processed"
        if ingest_result["failures"] or not ingest_result["parse_outputs"]:
            target_dir = failed_dir
            status = "failed"
            failed_count += 1
            failures.extend(ingest_result["failures"])
        else:
            review_outputs = [Path(item) for item in ingest_result["validate_outputs"] if Path(item).parent == Path(review_dir)]
            if review_outputs:
                status = "review"
                review_count += 1
            else:
                success_count += 1

        archived_path = pdf_path
        if move_files:
            archived_path = _safe_archive_path(target_dir, pdf_path.name)
            shutil.move(str(pdf_path), str(archived_path))

        record = {
            "source_name": pdf_path.name,
            "source_path": str(pdf_path),
            "archived_path": str(archived_path),
            "status": status,
            "hash": file_hash,
            "parse_outputs": ingest_result["parse_outputs"],
            "validate_outputs": ingest_result["validate_outputs"],
            "manual_truth_outputs": ingest_result["manual_truth_outputs"],
            "failures": ingest_result["failures"],
            "updated_at": _now_iso(),
        }
        manifest["files"][file_hash] = record
        processed.append(record)

    _save_manifest(manifest_path, manifest)
    return {
        "inbox_dir": str(inbox_dir),
        "manifest_path": str(manifest_path),
        "checked_count": len(pdfs),
        "processed_count": len(processed),
        "skipped_count": len(skipped),
        "success_count": success_count,
        "review_count": review_count,
        "failed_count": failed_count,
        "processed": processed,
        "skipped": skipped,
        "failures": failures,
    }
