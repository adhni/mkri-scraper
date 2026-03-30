from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .parser import MkriParser


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
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
