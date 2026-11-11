#!/usr/bin/env python3
"""Run the deterministic suite and fail closed when no tests are collected."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    sys.path.insert(0, str(ROOT))
    suite = unittest.TestLoader().discover(str(ROOT / "tests"))
    count = suite.countTestCases()
    if count == 0:
        print("No deterministic tests collected", file=sys.stderr)
        return 1
    print(f"Collected {count} deterministic tests", flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
