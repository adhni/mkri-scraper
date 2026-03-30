from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    parsed_dir = Path("data/parsed_json")
    failed: list[str] = []
    for path in sorted(parsed_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        status = payload.get("parser", {}).get("status")
        if status in {"partial", "failed"}:
            failed.append(path.name)
    for item in failed:
        print(item)


if __name__ == "__main__":
    main()
