from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from .pipeline import ingest_pdf_files
from .scrapers.mkri_tracking import (
    TrackingCaseSnapshot,
    build_case_number,
    build_tracking_url,
    download_binary,
    extract_tracking_case,
    fetch_url_text,
    slugify_case_number,
)


@dataclass
class DiscoveryState:
    case_type: str
    year: int
    next_sequence: int = 1
    last_checked_sequence: int = 0
    consecutive_misses: int = 0
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_type": self.case_type,
            "year": self.year,
            "next_sequence": self.next_sequence,
            "last_checked_sequence": self.last_checked_sequence,
            "consecutive_misses": self.consecutive_misses,
            "updated_at": self.updated_at,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_state(path: Path, case_type: str, year: int, start_sequence: int) -> DiscoveryState:
    if not path.exists():
        return DiscoveryState(case_type=case_type, year=year, next_sequence=start_sequence)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return DiscoveryState(
        case_type=payload.get("case_type", case_type),
        year=int(payload.get("year", year)),
        next_sequence=int(payload.get("next_sequence", start_sequence)),
        last_checked_sequence=int(payload.get("last_checked_sequence", 0)),
        consecutive_misses=int(payload.get("consecutive_misses", 0)),
        updated_at=payload.get("updated_at"),
    )


def _save_state(path: Path, state: DiscoveryState) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_snapshot(snapshot: TrackingCaseSnapshot, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _pick_decision_link(snapshot: TrackingCaseSnapshot) -> str | None:
    for link in snapshot.document_links:
        if link.category == "decision":
            return link.url
    return None


def sync_new_cases(
    *,
    case_type: str,
    year: int,
    start_sequence: int = 1,
    max_candidates: int = 50,
    max_misses: int = 20,
    state_path: str | Path | None = None,
    html_dir: str | Path = "data/discovery/raw_html",
    snapshot_dir: str | Path = "data/discovery/tracking_cases",
    pdf_dir: str | Path = "data/raw_pdfs",
    download_decisions: bool = False,
    sleep_seconds: float = 0.2,
    timeout: float = 20.0,
    force: bool = False,
) -> dict[str, Any]:
    state_path = Path(state_path or Path("data/discovery/checkpoints") / f"{case_type.lower()}_{year}.json")
    html_dir = Path(html_dir)
    snapshot_dir = Path(snapshot_dir)
    pdf_dir = Path(pdf_dir)

    state = _load_state(state_path, case_type=case_type, year=year, start_sequence=start_sequence)
    current_sequence = max(start_sequence, state.next_sequence)

    found_cases: list[str] = []
    new_cases: list[str] = []
    downloaded_pdfs: list[str] = []
    failures: list[str] = []
    checked_urls: list[str] = []
    last_checked_sequence = state.last_checked_sequence
    consecutive_misses = 0

    for sequence in range(current_sequence, current_sequence + max_candidates):
        case_number = build_case_number(sequence, case_type, year)
        tracking_url = build_tracking_url(case_number)
        checked_urls.append(tracking_url)
        last_checked_sequence = sequence

        try:
            html = fetch_url_text(tracking_url, timeout=timeout)
        except HTTPError as exc:
            if exc.code == 404:
                consecutive_misses += 1
                if consecutive_misses >= max_misses:
                    break
                continue
            failures.append(f"{case_number}: HTTP {exc.code}")
            consecutive_misses += 1
            if consecutive_misses >= max_misses:
                break
            continue
        except URLError as exc:
            failures.append(f"{case_number}: {exc.reason}")
            break
        except Exception as exc:
            failures.append(f"{case_number}: {exc}")
            break

        snapshot = extract_tracking_case(html, tracking_url)
        if snapshot is None:
            consecutive_misses += 1
            if consecutive_misses >= max_misses:
                break
            continue

        consecutive_misses = 0
        slug = slugify_case_number(snapshot.case_number)
        html_path = html_dir / f"{slug}.html"
        snapshot_path = snapshot_dir / f"{slug}.json"
        existed_before = snapshot_path.exists()

        if force or not html_path.exists():
            html_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.write_text(html, encoding="utf-8")
        _write_snapshot(snapshot, snapshot_path)

        found_cases.append(snapshot.case_number)
        if not existed_before:
            new_cases.append(snapshot.case_number)

        if download_decisions:
            decision_url = _pick_decision_link(snapshot)
            if decision_url:
                pdf_path = pdf_dir / f"{slug}.pdf"
                if force or not pdf_path.exists():
                    try:
                        download_binary(decision_url, pdf_path, timeout=max(timeout, 30.0))
                        downloaded_pdfs.append(str(pdf_path))
                    except Exception as exc:
                        failures.append(f"{snapshot.case_number} decision download: {exc}")
                else:
                    downloaded_pdfs.append(str(pdf_path))

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    state.next_sequence = last_checked_sequence + 1
    state.last_checked_sequence = last_checked_sequence
    state.consecutive_misses = consecutive_misses
    state.updated_at = _now_iso()
    _save_state(state_path, state)

    return {
        "case_type": case_type,
        "year": year,
        "checked_count": len(checked_urls),
        "checked_urls": checked_urls,
        "found_cases": found_cases,
        "new_cases": new_cases,
        "downloaded_pdfs": downloaded_pdfs,
        "failures": failures,
        "state_path": str(state_path),
        "next_sequence": state.next_sequence,
        "last_checked_sequence": state.last_checked_sequence,
        "consecutive_misses": state.consecutive_misses,
    }


def sync_and_ingest_cases(
    *,
    case_type: str,
    year: int,
    start_sequence: int = 1,
    max_candidates: int = 50,
    max_misses: int = 20,
    state_path: str | Path | None = None,
    html_dir: str | Path = "data/discovery/raw_html",
    snapshot_dir: str | Path = "data/discovery/tracking_cases",
    pdf_dir: str | Path = "data/raw_pdfs",
    parsed_dir: str | Path = "data/parsed_json",
    validated_dir: str | Path = "data/validated_json",
    review_dir: str | Path = "data/review_queue",
    manual_truth_dir: str | Path | None = None,
    download_decisions: bool = True,
    sleep_seconds: float = 0.2,
    timeout: float = 20.0,
    force: bool = False,
) -> dict[str, Any]:
    discovery_result = sync_new_cases(
        case_type=case_type,
        year=year,
        start_sequence=start_sequence,
        max_candidates=max_candidates,
        max_misses=max_misses,
        state_path=state_path,
        html_dir=html_dir,
        snapshot_dir=snapshot_dir,
        pdf_dir=pdf_dir,
        download_decisions=download_decisions,
        sleep_seconds=sleep_seconds,
        timeout=timeout,
        force=force,
    )

    pdf_dir = Path(pdf_dir)
    pdf_inputs: list[Path] = []
    for case_number in discovery_result["new_cases"]:
        candidate = pdf_dir / f"{slugify_case_number(case_number)}.pdf"
        if candidate.exists():
            pdf_inputs.append(candidate)

    ingest_result = ingest_pdf_files(
        pdf_paths=pdf_inputs,
        parsed_dir=parsed_dir,
        validated_dir=validated_dir,
        review_dir=review_dir,
        manual_truth_dir=manual_truth_dir,
    )

    return {
        "discovery": discovery_result,
        "ingest": ingest_result,
    }
