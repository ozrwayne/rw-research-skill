import csv
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "rw-research-lab-router" / "scripts"))
from read_tool_registry import read_registry  # noqa: E402


class ToolRegistryTests(unittest.TestCase):
    def test_registry_marks_old_rows_stale(self):
        columns = [
            "id", "scope", "category", "name", "path", "purpose", "role", "version",
            "license", "runtime", "inputs", "outputs", "network", "last_test_date",
            "last_test_level", "last_test_result", "rw_skills", "source",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tool-registry.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                writer.writeheader()
                writer.writerow({"id": "project:demo", "name": "demo", "version": "1.0", "license": "MIT", "runtime": "Python", "last_test_date": "2026-01-01", "last_test_level": "unit", "last_test_result": "passed", "rw_skills": "rw-research-router", "source": "local"})
            result = read_registry(path, date(2026, 7, 31), stale_after_days=90)
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["rows"][0]["freshness"], "STALE")

    def test_missing_registry_is_reported_without_dependency_failure(self):
        result = read_registry(Path("/does/not/exist.csv"), date(2026, 7, 31))
        self.assertEqual(result["rows"], [])
        self.assertIn("registry file not found", result["warnings"])


if __name__ == "__main__":
    unittest.main()
