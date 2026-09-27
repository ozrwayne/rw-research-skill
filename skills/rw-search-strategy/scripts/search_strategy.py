#!/usr/bin/env python3
"""Render and verify multi-database literature search strategies."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


VERIFIED_STATUSES = {
    "verified_by_public_api",
    "verified_in_subscribed_platform",
    "user_confirmed",
}
HEADING_STATUSES = VERIFIED_STATUSES | {"candidate", "unverified", "rejected"}
VOCABULARIES = ("mesh", "emtree", "cinahl", "apa")
VOCABULARY_SET = set(VOCABULARIES)
PLATFORMS = {
    "pubmed",
    "ovid_medline",
    "embase_com",
    "ovid_embase",
    "ebsco_cinahl",
    "ebsco_psycinfo",
    "ovid_psycinfo",
    "proquest_psycinfo",
}
PLATFORM_VOCABULARY = {
    "pubmed": "mesh",
    "ovid_medline": "mesh",
    "embase_com": "emtree",
    "ovid_embase": "emtree",
    "ebsco_cinahl": "cinahl",
    "ebsco_psycinfo": "apa",
    "ovid_psycinfo": "apa",
    "proquest_psycinfo": "apa",
}


def load_json(path: str) -> dict[str, Any]:
    return strict_json(Path(path).read_text(encoding="utf-8"))


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f"non-finite JSON constant: {value}")


def strict_json(text):
    value = json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
    json.dumps(value, allow_nan=False)
    return value


def dump_json(value: Any, output: str | None = None) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if output:
        write_text_atomic(Path(output), text)
    else:
        sys.stdout.write(text)


def ensure_distinct_paths(inputs: list[Path], outputs: list[Path]) -> None:
    for index, output in enumerate(outputs):
        if output.is_symlink():
            raise ValueError("output paths must not be symlinks")
        for other in inputs + outputs[:index]:
            if output.resolve() == other.resolve() or (output.exists() and other.exists() and output.samefile(other)):
                raise ValueError("output/report paths must be distinct from one another and from inputs")


def write_text_atomic(output: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=output.parent, delete=False) as handle:
        temp = Path(handle.name)
        try:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp, output)
    finally:
        temp.unlink(missing_ok=True)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def http_json(url: str, timeout: int = 30) -> Any:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "rw-search-strategy/0.10"})
    with urlopen(request, timeout=timeout) as response:
        return json.load(response, object_pairs_hook=unique_object, parse_constant=reject_constant)


def normalize_heading(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return {"label": value, "status": "candidate", "explode": True, "focus": False}
    if not isinstance(value, dict):
        raise ValueError("heading must be a string or object")
    row = dict(value)
    row.setdefault("status", "candidate")
    row.setdefault("explode", True)
    row.setdefault("focus", False)
    return row


def quote_double(value: str) -> str:
    return value.replace('"', '\\"')


def quote_single(value: str) -> str:
    return value.replace("'", "''")


def ovid_term(value: str) -> str:
    return value if re.fullmatch(r"[\w*?-]+", value) else f'"{quote_double(value)}"'


def free_terms(concept: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    for value in concept.get("free_text", []):
        term = value.get("term", "") if isinstance(value, dict) else str(value)
        term = term.strip()
        if term and term not in rows:
            rows.append(term)
    return rows


def eligible_headings(concept: dict[str, Any], vocabulary: str, include_candidates: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for value in concept.get("headings", {}).get(vocabulary, []):
        row = normalize_heading(value)
        if row["status"] in VERIFIED_STATUSES or (include_candidates and row["status"] in {"candidate", "unverified"}):
            selected.append(row)
        else:
            excluded.append(row)
    return selected, excluded


def render_controlled(platform: str, row: dict[str, Any]) -> str:
    label = str(row["label"]).strip()
    explode = bool(row.get("explode", True))
    focus = bool(row.get("focus", False))
    if platform == "pubmed":
        field = "Majr" if focus else "Mesh"
        return f'"{quote_double(label)}"[{field}:noexp]' if not explode else f'"{quote_double(label)}"[{field}]'
    if platform in {"ovid_medline", "ovid_embase", "ovid_psycinfo"}:
        prefix = "*" if focus else ""
        return f"exp {prefix}{ovid_term(label)}/" if explode else f"{prefix}{ovid_term(label)}/"
    if platform == "embase_com":
        suffix = "/exp/mj" if focus and explode else "/mj" if focus else "/exp" if explode else "/de"
        return f"'{quote_single(label)}'{suffix}"
    if platform == "ebsco_cinahl":
        field = "MM" if focus else "MH"
        plus = "+" if explode else ""
        return f'{field} "{quote_double(label)}{plus}"'
    if platform == "ebsco_psycinfo":
        return f'DE "{quote_double(label)}"'
    if platform == "proquest_psycinfo":
        operator = "MAINSUBJECT.EXACT.EXPLODE" if explode else "MAINSUBJECT.EXACT"
        return f'{operator}("{quote_double(label)}")'
    raise ValueError(f"unsupported platform: {platform}")


def render_free(platform: str, term: str) -> str:
    if platform == "pubmed":
        return f"{term}[tiab]" if re.fullmatch(r"[\w*?-]+", term) else f'"{quote_double(term)}"[tiab]'
    if platform in {"ovid_medline", "ovid_embase"}:
        return f"{ovid_term(term)}.ti,ab,kf."
    if platform == "ovid_psycinfo":
        return f"{ovid_term(term)}.ti,ab,id."
    if platform == "embase_com":
        return f"'{quote_single(term)}':ti,ab,kw"
    if platform in {"ebsco_cinahl", "ebsco_psycinfo"}:
        escaped = quote_double(term)
        return f'(TI "{escaped}" OR AB "{escaped}")'
    if platform == "proquest_psycinfo":
        return f'TI,AB("{quote_double(term)}")'
    raise ValueError(f"unsupported platform: {platform}")


def render_platform(strategy: dict[str, Any], platform: str, include_candidates: bool = False) -> dict[str, Any]:
    errors = validate_strategy(strategy)
    if errors:
        raise ValueError("; ".join(errors))
    if platform not in PLATFORMS:
        raise ValueError(f"unsupported platform: {platform}")
    vocabulary = PLATFORM_VOCABULARY[platform]
    blocks: list[dict[str, Any]] = []
    excluded_candidates: list[dict[str, Any]] = []
    missing_concepts: list[str] = []
    warnings: list[str] = []
    for concept in strategy.get("concepts", []):
        headings, excluded = eligible_headings(concept, vocabulary, include_candidates)
        controlled = [render_controlled(platform, row) for row in headings]
        free = [render_free(platform, term) for term in free_terms(concept)]
        if platform == "pubmed":
            for term in free_terms(concept):
                if any(len(word.split("*", 1)[0]) < 4 for word in term.split() if "*" in word):
                    warnings.append(f"{concept['id']}: PubMed wildcard prefixes need at least four characters: {term}")
        clauses = controlled + free
        if not clauses:
            missing_concepts.append(concept["id"])
        else:
            blocks.append(
            {
                "concept_id": concept.get("id"),
                "label": concept.get("label"),
                "controlled_count": len(controlled),
                "free_text_count": len(free),
                "query": "(" + " OR ".join(clauses) + ")",
            }
            )
        for row in excluded:
            excluded_candidates.append(
                {
                    "concept_id": concept.get("id"),
                    "vocabulary": vocabulary,
                    "label": row.get("label"),
                    "status": row.get("status"),
                }
            )
    draft_query = " AND ".join(block["query"] for block in blocks)
    return {
        "platform": platform,
        "vocabulary": vocabulary,
        "query": "" if missing_concepts else draft_query,
        "draft_query": draft_query,
        "missing_concepts": missing_concepts,
        "status": "incomplete" if missing_concepts else "draft" if include_candidates else "ready_for_platform_validation",
        "concept_blocks": blocks,
        "excluded_unverified_headings": excluded_candidates,
        "requires_platform_validation": True,
        "warnings": warnings,
    }


def heading_audit(strategy: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for concept in strategy.get("concepts", []):
        for vocabulary in VOCABULARIES:
            for value in concept.get("headings", {}).get(vocabulary, []):
                row = normalize_heading(value)
                rows.append(
                    {
                        "concept_id": concept.get("id"),
                        "concept_label": concept.get("label"),
                        "vocabulary": vocabulary,
                        "label": row.get("label"),
                        "identifier": row.get("identifier"),
                        "status": row.get("status"),
                        "verified": row.get("status") in VERIFIED_STATUSES,
                        "source": row.get("source"),
                        "verified_at": row.get("verified_at"),
                        "explode": row.get("explode"),
                        "focus": row.get("focus"),
                    }
                )
    return rows


def validate_strategy(strategy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(strategy, dict):
        return ["strategy must be an object"]
    if not isinstance(strategy.get("question"), str) or not strategy["question"].strip():
        errors.append("question is required")
    concepts = strategy.get("concepts", [])
    if not isinstance(concepts, list) or not concepts:
        return errors + ["at least one concept is required in an array"]
    targets = strategy.get("targets")
    if targets is not None and (not isinstance(targets, list) or not targets or any(not isinstance(t, str) or t not in PLATFORMS for t in targets)):
        errors.append("targets must be a non-empty array of supported platforms")
    seen: set[str] = set()
    for index, concept in enumerate(concepts, 1):
        if not isinstance(concept, dict):
            errors.append(f"concept {index} must be an object")
            continue
        concept_id = concept.get("id", "")
        if not isinstance(concept_id, str):
            errors.append(f"concept {index} id must be a string")
            continue
        concept_id = concept_id.strip()
        if not concept_id:
            errors.append(f"concept {index} has no id")
        elif concept_id in seen:
            errors.append(f"duplicate concept id: {concept_id}")
        seen.add(concept_id)
        terms = concept.get("free_text", [])
        if not isinstance(terms, list):
            errors.append(f"{concept_id} free_text must be an array")
        else:
            for term in terms:
                term = term.get("term") if isinstance(term, dict) else term
                if not isinstance(term, str) or not term.strip() or any(ord(c) < 32 for c in term):
                    errors.append(f"{concept_id} free_text terms must be non-empty single-line strings")
                elif any(c in term for c in ('"', '[', ']', '\\')):
                    errors.append(f"{concept_id} free_text must contain terms, not query syntax")
        headings = concept.get("headings", {})
        if not isinstance(headings, dict):
            errors.append(f"{concept_id} headings must be an object")
            continue
        for vocabulary, values in headings.items():
            if vocabulary not in VOCABULARY_SET:
                errors.append(f"unsupported vocabulary: {vocabulary}")
            if not isinstance(values, list):
                errors.append(f"{concept_id}/{vocabulary} headings must be an array")
                continue
            for value in values:
                try:
                    row = normalize_heading(value)
                except ValueError as exc:
                    errors.append(f"{concept_id}/{vocabulary}: {exc}")
                    continue
                if not isinstance(row.get("label"), str) or not row["label"].strip():
                    errors.append(f"{concept_id}/{vocabulary} heading has no label")
                elif any(ord(c) < 32 or c in ('"', '[', ']', '\\') for c in row["label"]):
                    errors.append(f"{concept_id}/{vocabulary} heading must not contain query syntax")
                status = row.get("status")
                if not isinstance(status, str) or status not in HEADING_STATUSES:
                    errors.append(f"{concept_id}/{vocabulary} invalid heading status")
                    continue
                for flag in ("explode", "focus"):
                    if not isinstance(row[flag], bool):
                        errors.append(f"{concept_id}/{vocabulary} {flag} must be boolean")
                if status in VERIFIED_STATUSES:
                    for field in ("source", "verified_at"):
                        if not isinstance(row.get(field), str) or not row[field].strip():
                            errors.append(f"{concept_id}/{vocabulary} verified heading requires {field}")
                    try:
                        datetime.fromisoformat(row.get("verified_at", "").replace("Z", "+00:00"))
                    except (ValueError, TypeError, AttributeError):
                        errors.append(f"{concept_id}/{vocabulary} verified_at must be an ISO date or datetime")
                if vocabulary != "mesh" and row.get("status") == "verified_by_public_api":
                    errors.append(f"{concept_id}/{vocabulary} cannot use verified_by_public_api")
    return errors


def render_strategy(strategy: dict[str, Any], targets: list[str] | None, include_candidates: bool) -> dict[str, Any]:
    errors = validate_strategy(strategy)
    if errors:
        raise ValueError("; ".join(errors))
    selected_targets = targets or strategy.get("targets") or sorted(PLATFORMS)
    unknown = set(selected_targets) - PLATFORMS
    if unknown:
        raise ValueError("unsupported targets: " + ", ".join(sorted(unknown)))
    return {
        "schema_version": "1.0",
        "question": strategy["question"],
        "language": strategy.get("language", "unspecified"),
        "framework": strategy.get("framework", "open"),
        "generated_at": now_utc(),
        "include_candidates": include_candidates,
        "heading_audit": heading_audit(strategy),
        "platforms": [
            render_platform(strategy, platform, include_candidates)
            for platform in selected_targets
        ],
        "status_note": (
            "Candidate headings were rendered and still require platform validation."
            if include_candidates
            else "Unverified headings were excluded from executable queries."
        ),
    }


def markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# Search strategy",
        "",
        f"- Question: {result['question']}",
        f"- Language: {result['language']}",
        f"- Framework: {result['framework']}",
        f"- Generated: {result['generated_at']}",
        "",
        "## Platform queries",
        "",
    ]
    for row in result["platforms"]:
        lines += [
            f"### {row['platform']}",
            "",
            "```text",
            row["query"] or "[no executable terms]",
            "```",
            "",
        ]
        if row["excluded_unverified_headings"]:
            labels = ", ".join(item["label"] for item in row["excluded_unverified_headings"])
            lines += [f"- Excluded unverified headings: {labels}", ""]
        if row.get("missing_concepts"):
            lines += ["- INCOMPLETE: no eligible terms for concepts: " + ", ".join(row["missing_concepts"]), ""]
        for warning in row.get("warnings", []):
            lines += ["- Warning: " + warning, ""]
    lines += ["## Controlled vocabulary audit", "", "| Concept | Vocabulary | Heading | Status | Source |", "|---|---|---|---|---|"]
    for row in result["heading_audit"]:
        lines.append(
            f"| {row['concept_id']} | {row['vocabulary']} | {row['label']} | {row['status']} | {row['source'] or ''} |"
        )
    return "\n".join(lines) + "\n"


def mesh_lookup(label: str, match: str, limit: int, year: str, timeout: int) -> dict[str, Any]:
    if not isinstance(label, str) or not label.strip() or not isinstance(year, str) or not re.fullmatch(r"current|\d{4}", year):
        raise ValueError("MeSH requires a label and a current or four-digit year")
    if type(limit) is not int or limit <= 0 or type(timeout) is not int or timeout <= 0:
        raise ValueError("limit and timeout must be positive integers")
    params = urlencode({"label": label, "match": match, "limit": limit, "year": year})
    matches = http_json(f"https://id.nlm.nih.gov/mesh/lookup/descriptor?{params}", timeout)
    if not isinstance(matches, list):
        raise ValueError("MeSH lookup did not return an array")
    output: list[dict[str, Any]] = []
    for match_row in matches:
        if not isinstance(match_row, dict):
            raise ValueError("invalid MeSH lookup row")
        resource = str(match_row.get("resource", ""))
        descriptor_id = resource.rstrip("/").rsplit("/", 1)[-1]
        if not re.fullmatch(r"D\d+", descriptor_id):
            raise ValueError("invalid MeSH descriptor identifier")
        detail_params = urlencode({"descriptor": descriptor_id, "includes": "terms,qualifiers,seealso"})
        details = http_json(f"https://id.nlm.nih.gov/mesh/lookup/details?{detail_params}", timeout)
        resource_url = (
            f"https://id.nlm.nih.gov/mesh/{descriptor_id}.json"
            if year == "current"
            else f"https://id.nlm.nih.gov/mesh/{year}/{descriptor_id}.json"
        )
        resource_data = http_json(resource_url, timeout)
        graph = resource_data.get("@graph", []) if isinstance(resource_data, dict) else resource_data
        if isinstance(resource_data, dict) and not graph:
            graph = [resource_data]
        if not isinstance(graph, list):
            raise ValueError("invalid MeSH descriptor graph")
        descriptor = next((node for node in graph if isinstance(node, dict) and str(node.get("@id", "")).rstrip("/").rsplit("/", 1)[-1] == descriptor_id), None)
        if descriptor is None:
            raise ValueError("MeSH graph does not contain the requested descriptor")
        active = mesh_literal(descriptor.get("active", descriptor.get("http://id.nlm.nih.gov/mesh/vocab#active")))
        tree_numbers = descriptor.get("treeNumber", [])
        if isinstance(tree_numbers, str):
            tree_numbers = [tree_numbers]
        output.append(
            {
                "label": match_row.get("label"),
                "identifier": descriptor_id,
                "resource": resource,
                "tree_numbers": [str(value).rstrip("/").rsplit("/", 1)[-1] for value in tree_numbers],
                "active": active,
                "date_introduced": descriptor.get("dateIntroduced"),
                "last_updated": descriptor.get("lastUpdated"),
                "annotation": mesh_literal(descriptor.get("annotation")),
                "details": details,
                "details_year": "current",
                "status": "rejected" if active is False or active == "false" else "verified_by_public_api",
                "source": "NLM MeSH RDF API",
                "verified_at": now_utc(),
                "year": year,
            }
        )
    return {"query": label, "match": match, "year": year, "results": output}


def pubmed_check(query: str, timeout: int) -> dict[str, Any]:
    params = urlencode({"db": "pubmed", "term": query, "retmode": "json", "retmax": 0, "usehistory": "n"})
    data = http_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}", timeout)
    if not isinstance(data, dict) or data.get("error"):
        raise ValueError("PubMed returned an error or invalid response")
    result = data.get("esearchresult")
    if not isinstance(result, dict) or result.get("error") or result.get("errorlist") or "count" not in result:
        raise ValueError("PubMed search failed or omitted count")
    count = result["count"]
    if isinstance(count, bool) or not re.fullmatch(r"\d+", str(count)):
        raise ValueError("PubMed count must be a non-negative integer")
    return {
        "query": query,
        "count": int(count),
        "query_translation": result.get("querytranslation"),
        "warning_list": result.get("warninglist", {}),
        "checked_at": now_utc(),
        "source": "NCBI PubMed ESearch",
    }


def mesh_literal(value: Any) -> Any:
    if isinstance(value, dict) and "@value" in value:
        return value["@value"]
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    render = sub.add_parser("render", help="Render database-specific strategies.")
    render.add_argument("--input", required=True)
    render.add_argument("--output")
    render.add_argument("--target", action="append", choices=sorted(PLATFORMS))
    render.add_argument("--include-candidates", action="store_true")
    render.add_argument("--format", choices=["json", "markdown"], default="json")

    mesh = sub.add_parser("mesh-lookup", help="Verify descriptors with the NLM MeSH RDF API.")
    mesh.add_argument("--label", required=True)
    mesh.add_argument("--match", choices=["exact", "contains", "startswith"], default="contains")
    mesh.add_argument("--limit", type=int, default=10)
    mesh.add_argument("--year", default="current")
    mesh.add_argument("--timeout", type=int, default=30)
    mesh.add_argument("--output")

    pubmed = sub.add_parser("pubmed-check", help="Check a PubMed query with NCBI ESearch.")
    pubmed.add_argument("--query", required=True)
    pubmed.add_argument("--timeout", type=int, default=30)
    pubmed.add_argument("--output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "render":
            ensure_distinct_paths([Path(args.input)], [Path(args.output)] if args.output else [])
            result = render_strategy(load_json(args.input), args.target, args.include_candidates)
            if args.format == "markdown":
                text = markdown_report(result)
                if args.output:
                    write_text_atomic(Path(args.output), text)
                else:
                    sys.stdout.write(text)
            else:
                dump_json(result, args.output)
        elif args.command == "mesh-lookup":
            dump_json(mesh_lookup(args.label, args.match, args.limit, args.year, args.timeout), args.output)
        elif args.command == "pubmed-check":
            dump_json(pubmed_check(args.query, args.timeout), args.output)
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
