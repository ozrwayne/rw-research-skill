#!/usr/bin/env python3
"""Read an optional Research Lab tool registry without making it a dependency."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path


REQUIRED_COLUMNS = {
    "id",
    "name",
    "version",
    "license",
    "runtime",
    "last_test_date",
    "last_test_level",
    "last_test_result",
    "rw_skills",
    "source",
}


def read_registry(path: Path, as_of: dt.date, stale_after_days: int = 90, names: set[str] | None = None) -> dict:
    if not path.is_file():
        return {"path": str(path), "rows": [], "warnings": ["registry file not found"]}

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - fieldnames)
        rows = []
        warnings = []
        for raw in reader:
            name = (raw.get("name") or "").strip()
            if names and name not in names:
                continue
            record = {key: (raw.get(key) or "").strip() for key in sorted(REQUIRED_COLUMNS)}
            date_text = record["last_test_date"]
            try:
                test_date = dt.date.fromisoformat(date_text)
            except ValueError:
                record.update({"freshness": "UNKNOWN", "age_days": None})
                if date_text:
                    warnings.append(f"{name or '<unnamed>'}: invalid last_test_date {date_text}")
            else:
                age_days = (as_of - test_date).days
                record.update({"freshness": "STALE" if age_days > stale_after_days else "CURRENT", "age_days": age_days})
            rows.append(record)

    if missing:
        warnings.append("missing required columns: " + ", ".join(missing))
    return {
        "path": str(path),
        "as_of": as_of.isoformat(),
        "stale_after_days": stale_after_days,
        "required_columns": sorted(REQUIRED_COLUMNS),
        "missing_columns": missing,
        "row_count": len(rows),
        "rows": rows,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--as-of", default=dt.date.today().isoformat())
    parser.add_argument("--stale-after-days", type=int, default=90)
    parser.add_argument("--name", action="append", dest="names")
    args = parser.parse_args()
    try:
        as_of = dt.date.fromisoformat(args.as_of)
    except ValueError as exc:
        parser.error(f"invalid --as-of date: {exc}")
    result = read_registry(args.path, as_of, args.stale_after_days, set(args.names or []))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("missing_columns") or result.get("warnings") == ["registry file not found"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
