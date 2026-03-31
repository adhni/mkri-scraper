from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Sequence

from .discovery import ingest_decision_url, ingest_tracking_html_file, sync_and_ingest_cases, sync_new_cases
from .inbox import ingest_inbox
from .parser import MkriParser
from .pipeline import ingest_pdf_files, run_pipeline
from .reporting import build_pipeline_report, write_pipeline_report


def _collect_pdfs(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(path.rglob("*.pdf"))


def cmd_parse(args: argparse.Namespace) -> int:
    parser = MkriParser()
    try:
        output = parser.parse_pdf_file_to_json(args.pdf)
    except Exception as exc:
        print(f"parse failed: {exc}")
        return 1
    print(output)
    return 0


def cmd_batch_parse(args: argparse.Namespace) -> int:
    parser = MkriParser()
    root = Path(args.directory)
    pdfs = _collect_pdfs(root)
    failed: list[str] = []
    for pdf_path in pdfs:
        try:
            out = parser.parse_pdf_file_to_json(pdf_path)
            payload = json.loads(out.read_text(encoding="utf-8"))
            if payload.get("parser", {}).get("status") in {"partial", "failed"}:
                failed.append(pdf_path.name)
            print(out)
        except Exception as exc:
            failed.append(f"{pdf_path.name}: {exc}")
    if failed:
        print("FAILED:")
        for item in failed:
            print(item)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    parser = MkriParser()
    root = Path(args.directory)
    files = [root] if root.is_file() else sorted(root.rglob("*.json"))
    for json_path in files:
        try:
            out = parser.validate_json_file(json_path)
        except Exception as exc:
            print(f"validate failed for {json_path.name}: {exc}")
            continue
        print(out)
    return 0


def cmd_scaffold_manual_truth(args: argparse.Namespace) -> int:
    parser = MkriParser()
    created = parser.scaffold_manual_truth(args.directory)
    for path in created:
        print(path)
    return 0


def cmd_run_pipeline(args: argparse.Namespace) -> int:
    result = run_pipeline(
        pdf_input=args.directory,
        parsed_dir=args.parsed_dir,
        validated_dir=args.validated_dir,
        review_dir=args.review_dir,
        manual_truth_dir=args.manual_truth_dir if args.with_manual_truth else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    report = build_pipeline_report(
        parsed_dir=args.parsed_dir,
        validated_dir=args.validated_dir,
        review_dir=args.review_dir,
    )
    if args.output:
        out_path = write_pipeline_report(
            output_path=args.output,
            parsed_dir=args.parsed_dir,
            validated_dir=args.validated_dir,
            review_dir=args.review_dir,
        )
        print(out_path)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_new(args: argparse.Namespace) -> int:
    result = sync_new_cases(
        case_type=args.case_type,
        year=args.year,
        start_sequence=args.start_sequence,
        max_candidates=args.max_candidates,
        max_misses=args.max_misses,
        state_path=args.state_path,
        html_dir=args.html_dir,
        snapshot_dir=args.snapshot_dir,
        pdf_dir=args.pdf_dir,
        download_decisions=args.download_decisions,
        use_browser=args.browser,
        browser_headless=not args.browser_headful,
        browser_storage_state_path=args.browser_storage_state,
        sleep_seconds=args.sleep_seconds,
        timeout=args.timeout,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_and_ingest(args: argparse.Namespace) -> int:
    result = sync_and_ingest_cases(
        case_type=args.case_type,
        year=args.year,
        start_sequence=args.start_sequence,
        max_candidates=args.max_candidates,
        max_misses=args.max_misses,
        state_path=args.state_path,
        html_dir=args.html_dir,
        snapshot_dir=args.snapshot_dir,
        pdf_dir=args.pdf_dir,
        parsed_dir=args.parsed_dir,
        validated_dir=args.validated_dir,
        review_dir=args.review_dir,
        manual_truth_dir=args.manual_truth_dir if args.with_manual_truth else None,
        download_decisions=not args.no_download_decisions,
        use_browser=args.browser,
        browser_headless=not args.browser_headful,
        browser_storage_state_path=args.browser_storage_state,
        sleep_seconds=args.sleep_seconds,
        timeout=args.timeout,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_ingest_tracking_html(args: argparse.Namespace) -> int:
    result = ingest_tracking_html_file(
        html_path=args.html,
        tracking_url=args.tracking_url,
        html_dir=args.html_dir,
        snapshot_dir=args.snapshot_dir,
        pdf_dir=args.pdf_dir,
        parsed_dir=args.parsed_dir,
        validated_dir=args.validated_dir,
        review_dir=args.review_dir,
        manual_truth_dir=args.manual_truth_dir if args.with_manual_truth else None,
        download_decision=not args.no_download_decision,
        use_browser=args.browser,
        browser_headless=not args.browser_headful,
        browser_storage_state_path=args.browser_storage_state,
        timeout=args.timeout,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_ingest_decision_url(args: argparse.Namespace) -> int:
    result = ingest_decision_url(
        case_number=args.case_number,
        decision_url=args.url,
        pdf_dir=args.pdf_dir,
        parsed_dir=args.parsed_dir,
        validated_dir=args.validated_dir,
        review_dir=args.review_dir,
        manual_truth_dir=args.manual_truth_dir if args.with_manual_truth else None,
        use_browser=args.browser,
        browser_headless=not args.browser_headful,
        browser_storage_state_path=args.browser_storage_state,
        timeout=args.timeout,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_ingest_pdf(args: argparse.Namespace) -> int:
    result = ingest_pdf_files(
        pdf_paths=[args.pdf],
        parsed_dir=args.parsed_dir,
        validated_dir=args.validated_dir,
        review_dir=args.review_dir,
        manual_truth_dir=args.manual_truth_dir if args.with_manual_truth else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_ingest_inbox(args: argparse.Namespace) -> int:
    result = ingest_inbox(
        inbox_dir=args.inbox_dir,
        processed_dir=args.processed_dir,
        failed_dir=args.failed_dir,
        manifest_path=args.manifest_path,
        parsed_dir=args.parsed_dir,
        validated_dir=args.validated_dir,
        review_dir=args.review_dir,
        manual_truth_dir=args.manual_truth_dir if args.with_manual_truth else None,
        move_files=not args.no_move,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="mkri-scraper")
    sub = ap.add_subparsers(dest="command", required=True)

    parse_cmd = sub.add_parser("parse", help="Parse one PDF into JSON")
    parse_cmd.add_argument("pdf", type=Path)
    parse_cmd.set_defaults(func=cmd_parse)

    batch_cmd = sub.add_parser("batch-parse", help="Parse all PDFs under a directory")
    batch_cmd.add_argument("directory", type=Path)
    batch_cmd.set_defaults(func=cmd_batch_parse)

    validate_cmd = sub.add_parser("validate", help="Validate parsed JSON files")
    validate_cmd.add_argument("directory", type=Path)
    validate_cmd.set_defaults(func=cmd_validate)

    manual_truth_cmd = sub.add_parser("scaffold-manual-truth", help="Create manual annotation templates from parsed JSON")
    manual_truth_cmd.add_argument("directory", type=Path)
    manual_truth_cmd.set_defaults(func=cmd_scaffold_manual_truth)

    run_pipeline_cmd = sub.add_parser("run-pipeline", help="Run parse, validate, and optional manual-truth scaffold in one command")
    run_pipeline_cmd.add_argument("directory", type=Path)
    run_pipeline_cmd.add_argument("--parsed-dir", type=Path, default=Path("data/parsed_json"))
    run_pipeline_cmd.add_argument("--validated-dir", type=Path, default=Path("data/validated_json"))
    run_pipeline_cmd.add_argument("--review-dir", type=Path, default=Path("data/review_queue"))
    run_pipeline_cmd.add_argument("--manual-truth-dir", type=Path, default=Path("tests/manual_truth"))
    run_pipeline_cmd.add_argument("--with-manual-truth", action="store_true")
    run_pipeline_cmd.set_defaults(func=cmd_run_pipeline)

    report_cmd = sub.add_parser("report", help="Summarize parsed, validated, and review-queue outputs")
    report_cmd.add_argument("--parsed-dir", type=Path, default=Path("data/parsed_json"))
    report_cmd.add_argument("--validated-dir", type=Path, default=Path("data/validated_json"))
    report_cmd.add_argument("--review-dir", type=Path, default=Path("data/review_queue"))
    report_cmd.add_argument("--output", type=Path)
    report_cmd.set_defaults(func=cmd_report)

    sync_cmd = sub.add_parser("sync-new", help="Discover new MKRI tracking cases and optionally download decision PDFs")
    sync_cmd.add_argument("--case-type", default="PUU")
    sync_cmd.add_argument("--year", type=int, default=date.today().year)
    sync_cmd.add_argument("--start-sequence", type=int, default=1)
    sync_cmd.add_argument("--max-candidates", type=int, default=50)
    sync_cmd.add_argument("--max-misses", type=int, default=20)
    sync_cmd.add_argument("--state-path", type=Path)
    sync_cmd.add_argument("--html-dir", type=Path, default=Path("data/discovery/raw_html"))
    sync_cmd.add_argument("--snapshot-dir", type=Path, default=Path("data/discovery/tracking_cases"))
    sync_cmd.add_argument("--pdf-dir", type=Path, default=Path("data/raw_pdfs"))
    sync_cmd.add_argument("--download-decisions", action="store_true")
    sync_cmd.add_argument("--browser", action="store_true")
    sync_cmd.add_argument("--browser-headful", action="store_true")
    sync_cmd.add_argument("--browser-storage-state", type=Path, default=Path("data/discovery/browser_state.json"))
    sync_cmd.add_argument("--sleep-seconds", type=float, default=0.2)
    sync_cmd.add_argument("--timeout", type=float, default=20.0)
    sync_cmd.add_argument("--force", action="store_true")
    sync_cmd.set_defaults(func=cmd_sync_new)

    sync_ingest_cmd = sub.add_parser("sync-and-ingest", help="Discover new MKRI cases, download decisions, parse PDFs, and validate JSON")
    sync_ingest_cmd.add_argument("--case-type", default="PUU")
    sync_ingest_cmd.add_argument("--year", type=int, default=date.today().year)
    sync_ingest_cmd.add_argument("--start-sequence", type=int, default=1)
    sync_ingest_cmd.add_argument("--max-candidates", type=int, default=50)
    sync_ingest_cmd.add_argument("--max-misses", type=int, default=20)
    sync_ingest_cmd.add_argument("--state-path", type=Path)
    sync_ingest_cmd.add_argument("--html-dir", type=Path, default=Path("data/discovery/raw_html"))
    sync_ingest_cmd.add_argument("--snapshot-dir", type=Path, default=Path("data/discovery/tracking_cases"))
    sync_ingest_cmd.add_argument("--pdf-dir", type=Path, default=Path("data/raw_pdfs"))
    sync_ingest_cmd.add_argument("--parsed-dir", type=Path, default=Path("data/parsed_json"))
    sync_ingest_cmd.add_argument("--validated-dir", type=Path, default=Path("data/validated_json"))
    sync_ingest_cmd.add_argument("--review-dir", type=Path, default=Path("data/review_queue"))
    sync_ingest_cmd.add_argument("--manual-truth-dir", type=Path, default=Path("tests/manual_truth"))
    sync_ingest_cmd.add_argument("--with-manual-truth", action="store_true")
    sync_ingest_cmd.add_argument("--no-download-decisions", action="store_true")
    sync_ingest_cmd.add_argument("--browser", action="store_true")
    sync_ingest_cmd.add_argument("--browser-headful", action="store_true")
    sync_ingest_cmd.add_argument("--browser-storage-state", type=Path, default=Path("data/discovery/browser_state.json"))
    sync_ingest_cmd.add_argument("--sleep-seconds", type=float, default=0.2)
    sync_ingest_cmd.add_argument("--timeout", type=float, default=20.0)
    sync_ingest_cmd.add_argument("--force", action="store_true")
    sync_ingest_cmd.set_defaults(func=cmd_sync_and_ingest)

    ingest_html_cmd = sub.add_parser("ingest-tracking-html", help="Ingest one local tracking HTML snapshot, optionally download its decision PDF, then parse and validate it")
    ingest_html_cmd.add_argument("html", type=Path)
    ingest_html_cmd.add_argument("--tracking-url")
    ingest_html_cmd.add_argument("--html-dir", type=Path, default=Path("data/discovery/raw_html"))
    ingest_html_cmd.add_argument("--snapshot-dir", type=Path, default=Path("data/discovery/tracking_cases"))
    ingest_html_cmd.add_argument("--pdf-dir", type=Path, default=Path("data/raw_pdfs"))
    ingest_html_cmd.add_argument("--parsed-dir", type=Path, default=Path("data/parsed_json"))
    ingest_html_cmd.add_argument("--validated-dir", type=Path, default=Path("data/validated_json"))
    ingest_html_cmd.add_argument("--review-dir", type=Path, default=Path("data/review_queue"))
    ingest_html_cmd.add_argument("--manual-truth-dir", type=Path, default=Path("tests/manual_truth"))
    ingest_html_cmd.add_argument("--with-manual-truth", action="store_true")
    ingest_html_cmd.add_argument("--no-download-decision", action="store_true")
    ingest_html_cmd.add_argument("--browser", action="store_true")
    ingest_html_cmd.add_argument("--browser-headful", action="store_true")
    ingest_html_cmd.add_argument("--browser-storage-state", type=Path, default=Path("data/discovery/browser_state.json"))
    ingest_html_cmd.add_argument("--timeout", type=float, default=30.0)
    ingest_html_cmd.add_argument("--force", action="store_true")
    ingest_html_cmd.set_defaults(func=cmd_ingest_tracking_html)

    ingest_url_cmd = sub.add_parser("ingest-decision-url", help="Download one decision PDF by URL, then parse and validate it")
    ingest_url_cmd.add_argument("url")
    ingest_url_cmd.add_argument("--case-number", required=True)
    ingest_url_cmd.add_argument("--pdf-dir", type=Path, default=Path("data/raw_pdfs"))
    ingest_url_cmd.add_argument("--parsed-dir", type=Path, default=Path("data/parsed_json"))
    ingest_url_cmd.add_argument("--validated-dir", type=Path, default=Path("data/validated_json"))
    ingest_url_cmd.add_argument("--review-dir", type=Path, default=Path("data/review_queue"))
    ingest_url_cmd.add_argument("--manual-truth-dir", type=Path, default=Path("tests/manual_truth"))
    ingest_url_cmd.add_argument("--with-manual-truth", action="store_true")
    ingest_url_cmd.add_argument("--browser", action="store_true")
    ingest_url_cmd.add_argument("--browser-headful", action="store_true")
    ingest_url_cmd.add_argument("--browser-storage-state", type=Path, default=Path("data/discovery/browser_state.json"))
    ingest_url_cmd.add_argument("--timeout", type=float, default=30.0)
    ingest_url_cmd.add_argument("--force", action="store_true")
    ingest_url_cmd.set_defaults(func=cmd_ingest_decision_url)

    ingest_pdf_cmd = sub.add_parser("ingest-pdf", help="Parse and validate one local PDF so it appears in the website data pipeline")
    ingest_pdf_cmd.add_argument("pdf", type=Path)
    ingest_pdf_cmd.add_argument("--parsed-dir", type=Path, default=Path("data/parsed_json"))
    ingest_pdf_cmd.add_argument("--validated-dir", type=Path, default=Path("data/validated_json"))
    ingest_pdf_cmd.add_argument("--review-dir", type=Path, default=Path("data/review_queue"))
    ingest_pdf_cmd.add_argument("--manual-truth-dir", type=Path, default=Path("tests/manual_truth"))
    ingest_pdf_cmd.add_argument("--with-manual-truth", action="store_true")
    ingest_pdf_cmd.set_defaults(func=cmd_ingest_pdf)

    ingest_inbox_cmd = sub.add_parser("ingest-inbox", help="Process only new PDFs from an inbox folder, archive them by status, and update website JSON outputs")
    ingest_inbox_cmd.add_argument("inbox_dir", type=Path, nargs="?", default=Path("data/inbox_pdfs"))
    ingest_inbox_cmd.add_argument("--processed-dir", type=Path, default=Path("data/raw_pdfs/processed"))
    ingest_inbox_cmd.add_argument("--failed-dir", type=Path, default=Path("data/raw_pdfs/failed"))
    ingest_inbox_cmd.add_argument("--manifest-path", type=Path, default=Path("data/pipeline_state/inbox_manifest.json"))
    ingest_inbox_cmd.add_argument("--parsed-dir", type=Path, default=Path("data/parsed_json"))
    ingest_inbox_cmd.add_argument("--validated-dir", type=Path, default=Path("data/validated_json"))
    ingest_inbox_cmd.add_argument("--review-dir", type=Path, default=Path("data/review_queue"))
    ingest_inbox_cmd.add_argument("--manual-truth-dir", type=Path, default=Path("tests/manual_truth"))
    ingest_inbox_cmd.add_argument("--with-manual-truth", action="store_true")
    ingest_inbox_cmd.add_argument("--no-move", action="store_true")
    ingest_inbox_cmd.add_argument("--force", action="store_true")
    ingest_inbox_cmd.set_defaults(func=cmd_ingest_inbox)
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
