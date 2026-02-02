from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from verifier2.validate import format_user_friendly_report, validate_standard_for_production_date


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Validate a food production date against GB standard info JSON.")
    p.add_argument(
        "--production-date",
        dest="production_date",
        required=True,
        help='Food production date (e.g. "2025-5-26" or "2025-05-26").',
    )
    p.add_argument(
        "--standard-info",
        dest="standard_info_path",
        default=str(Path("artifacts") / "standard_info.json"),
        help='Path to standard_info.json (default: "artifacts/standard_info.json").',
    )
    return p


def main(argv: list[str] | None = None) -> int:
    # Best-effort: make Chinese output readable on Windows terminals.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    args = build_arg_parser().parse_args(argv)

    p = Path(args.standard_info_path)
    if not p.exists():
        print(f"standard_info.json not found: {p}", file=sys.stderr)
        return 2

    try:
        standard_info = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to read JSON: {p} ({e})", file=sys.stderr)
        return 2

    if not isinstance(standard_info, dict):
        print(f"Invalid standard_info.json format (expected object): {p}", file=sys.stderr)
        return 2

    try:
        result = validate_standard_for_production_date(production_date=args.production_date, standard_info=standard_info)
    except Exception as e:
        print(f"Validation error: {e}", file=sys.stderr)
        return 2

    print(format_user_friendly_report(standard_info=standard_info, result=result))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())


