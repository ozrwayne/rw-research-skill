#!/usr/bin/env python3
"""Offline tests for rw-search-strategy."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


SEARCH = load_module("search_strategy", ROOT / "scripts/search_strategy.py")
IMPORTER = load_module("vocabulary_import", ROOT / "scripts/vocabulary_import.py")


def sample_strategy() -> dict:
    return {
        "question": "Do digital interventions improve depression?",
        "language": "English",
        "framework": "PICO",
        "concepts": [
            {
                "id": "condition",
                "label": "Depression",
                "free_text": ["depress*", "major depression"],
                "headings": {
                    "mesh": [
                        {
                            "label": "Depressive Disorder",
                            "identifier": "D003866",
                            "status": "verified_by_public_api",
                            "source": "NLM MeSH RDF API",
                            "verified_at": "2026-07-23",
                            "explode": True,
                        }
                    ],
                    "emtree": [{"label": "depression", "status": "candidate"}],
                    "cinahl": [],
                    "apa": [],
                },
            },
            {
                "id": "intervention",
                "label": "Digital intervention",
                "free_text": ["digital intervention*", "mobile app*"],
                "headings": {"mesh": [], "emtree": [], "cinahl": [], "apa": []},
            },
        ],
    }


class RenderTests(unittest.TestCase):
    def test_pubmed_uses_mesh_and_tiab(self):
        row = SEARCH.render_platform(sample_strategy(), "pubmed")
        self.assertIn('"Depressive Disorder"[Mesh]', row["query"])
        self.assertIn("depress*[tiab]", row["query"])
        self.assertIn(" AND ", row["query"])

    def test_ovid_medline_has_ovid_fields(self):
        row = SEARCH.render_platform(sample_strategy(), "ovid_medline")
        self.assertIn('exp "Depressive Disorder"/', row["query"])
        self.assertIn(".ti,ab,kf.", row["query"])
        self.assertNotIn("[Mesh]", row["query"])

    def test_ovid_exploded_focus_places_star_on_heading(self):
        row = {"label": "Depressive Disorder", "explode": True, "focus": True}
        self.assertEqual(
            SEARCH.render_controlled("ovid_medline", row),
            'exp *"Depressive Disorder"/',
        )

    def test_unverified_emtree_is_excluded(self):
        row = SEARCH.render_platform(sample_strategy(), "embase_com")
        self.assertNotIn("'depression'/exp", row["query"])
        self.assertEqual(row["excluded_unverified_headings"][0]["status"], "candidate")
        self.assertTrue(row["requires_platform_validation"])

    def test_candidates_can_be_rendered_as_draft(self):
        row = SEARCH.render_platform(sample_strategy(), "embase_com", include_candidates=True)
        self.assertIn("'depression'/exp", row["query"])

    def test_psycinfo_platforms_use_distinct_syntax(self):
        strategy = sample_strategy()
        strategy["concepts"][0]["headings"]["apa"] = [
            {
                "label": "Major Depression",
                "status": "user_confirmed",
                "source": "User platform record",
                "verified_at": "2026-07-23",
            }
        ]
        ebsco = SEARCH.render_platform(strategy, "ebsco_psycinfo")["query"]
        ovid = SEARCH.render_platform(strategy, "ovid_psycinfo")["query"]
        proquest = SEARCH.render_platform(strategy, "proquest_psycinfo")["query"]
        self.assertIn('DE "Major Depression"', ebsco)
        self.assertIn('exp "Major Depression"/', ovid)
        self.assertIn('MAINSUBJECT.EXACT.EXPLODE("Major Depression")', proquest)

    def test_proprietary_public_api_status_is_rejected(self):
        strategy = sample_strategy()
        strategy["concepts"][0]["headings"]["apa"] = [
            {"label": "Depression", "status": "verified_by_public_api"}
        ]
        self.assertIn("cannot use verified_by_public_api", ";".join(SEARCH.validate_strategy(strategy)))

    def test_markdown_contains_each_query(self):
        result = SEARCH.render_strategy(sample_strategy(), ["pubmed", "ovid_medline"], False)
        report = SEARCH.markdown_report(result)
        self.assertIn("### pubmed", report)
        self.assertIn("### ovid_medline", report)

    def test_mesh_lookup_parses_compact_json_ld(self):
        responses = [
            [{"resource": "http://id.nlm.nih.gov/mesh/D003866", "label": "Depressive Disorder"}],
            {"descriptor": "http://id.nlm.nih.gov/mesh/D003866", "terms": []},
            {
                "@id": "http://id.nlm.nih.gov/mesh/D003866",
                "http://id.nlm.nih.gov/mesh/vocab#active": True,
                "treeNumber": "http://id.nlm.nih.gov/mesh/F03.600.300",
                "dateIntroduced": "1981-01-01",
                "annotation": {"@language": "en", "@value": "scope note"},
            },
        ]
        with patch.object(SEARCH, "http_json", side_effect=responses):
            result = SEARCH.mesh_lookup("Depressive Disorder", "exact", 1, "current", 30)
        row = result["results"][0]
        self.assertTrue(row["active"])
        self.assertEqual(row["tree_numbers"], ["F03.600.300"])
        self.assertEqual(row["annotation"], "scope note")


class ImportTests(unittest.TestCase):
    def test_verified_subscription_record_is_merged(self):
        record = {
            "concept_id": "condition",
            "vocabulary": "emtree",
            "label": "depression",
            "identifier": "emt-001",
            "status": "verified_in_subscribed_platform",
            "source": "Embase.com thesaurus",
            "verified_at": "2026-07-23",
        }
        merged, report = IMPORTER.merge(sample_strategy(), [record])
        self.assertEqual(report["accepted"], 1)
        self.assertEqual(report["rejected"], 0)
        self.assertEqual(
            merged["concepts"][0]["headings"]["emtree"][-1]["status"],
            "verified_in_subscribed_platform",
        )

    def test_verified_record_requires_source_and_date(self):
        record = {
            "concept_id": "condition",
            "vocabulary": "cinahl",
            "label": "Depression",
            "status": "verified_in_subscribed_platform",
        }
        _, report = IMPORTER.merge(sample_strategy(), [record])
        self.assertEqual(report["rejected"], 1)
        self.assertIn("verified record requires source", report["failures"][0]["errors"])

    def test_cli_template_is_valid_json(self):
        data = json.loads((ROOT / "assets/search-strategy-template.json").read_text(encoding="utf-8"))
        self.assertEqual(data["framework"], "PICO")
        self.assertEqual(len(data["targets"]), 8)

    def test_output_can_be_serialized(self):
        result = SEARCH.render_strategy(sample_strategy(), ["pubmed"], False)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "result.json"
            SEARCH.dump_json(result, str(path))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["platforms"][0]["platform"], "pubmed")


if __name__ == "__main__":
    unittest.main()
