from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .parser import MkriParser
from .pipeline import run_pipeline
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
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
