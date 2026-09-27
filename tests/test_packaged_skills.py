"""Collect all bundled Skill unittest suites; import failures are real failures."""
import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LocalPathSuite(unittest.TestSuite):
    """Keep a Skill's scripts importable while its tests actually execute."""

    def __init__(self, suite, directory):
        super().__init__([suite])
        self.directory = directory

    def run(self, result, debug=False):
        original = sys.path[:]
        try:
            sys.path.insert(0, str(self.directory))
            return super().run(result, debug)
        finally:
            sys.path[:] = original


def load_tests(loader, tests, pattern):
    paths = set((ROOT / "skills").glob("*/tests/test*.py")) | set((ROOT / "skills").glob("*/scripts/test_*.py"))
    for path in sorted(paths):
        name = "packaged_" + hashlib.sha256(str(path).encode()).hexdigest()[:16]
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        original_path = sys.path[:]
        try:
            sys.path.insert(0, str(path.parent))
            sys.modules[name] = module
            spec.loader.exec_module(module)
            tests.addTest(LocalPathSuite(loader.loadTestsFromModule(module), path.parent))
        finally:
            sys.path[:] = original_path
    return tests
