#!/usr/bin/env python3
"""Audit common citation identity and reference-list consistency problems."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


REFERENCE_HEADING = re.compile(r"^#{1,6}\s+(references|bibliography)\s*$", re.I | re.M)
REF_AUTHOR_YEAR = re.compile(
    r"^\s*([A-Z][A-Za-z'’\-]+),\s*([A-Z])\.[\s\S]{0,500}?\((\d{4}[a-z]?)\)"
)
DOI = re.compile(r"(?:https?://doi\.org/|doi:\s*)?(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.I)
PAREN_CITATION = re.compile(r"\(([^()]*?\b\d{4}[a-z]?[^()]*)\)")
AUTHOR_YEAR = re.compile(r"\b([A-Z][A-Za-z'’\-]+)(?:\s+(?:et\s+al\.|(?:&|and)\s+[A-Z][A-Za-z'’\-]+))?\s*,\s*(\d{4}[a-z]?)")
NARRATIVE = re.compile(r"\b([A-Z][A-Za-z'’\-]+)(?:\s+(?:et\s+al\.|(?:&|and)\s+[A-Z][A-Za-z'’\-]+))?\s*\((\d{4}[a-z]?)\)")


def split_document(text: str) -> tuple[str, str]:
    match = REFERENCE_HEADING.search(text)
    if not match:
        return text, ""
    return text[: match.start()], text[match.end() :]


def reference_blocks(text: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def normalize_doi(value: str) -> str:
    value = value.rstrip(".,;").lower()
    while value.endswith(")") and value.count(")") > value.count("("):
        value = value[:-1]
    return value


def parse_references(text: str) -> list[dict]:
    rows: list[dict] = []
    for index, block in enumerate(reference_blocks(text), 1):
        author = REF_AUTHOR_YEAR.search(block)
        doi = DOI.search(block)
        rows.append(
            {
                "index": index,
                "text": " ".join(block.split()),
                "surname": author.group(1) if author else None,
                "initial": author.group(2) if author else None,
                "year": author.group(3) if author else None,
                "doi": normalize_doi(doi.group(1)) if doi else None,
            }
        )
    return rows


def body_citations(text: str) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for group in PAREN_CITATION.findall(text):
        found.update(AUTHOR_YEAR.findall(group))
    found.update(NARRATIVE.findall(text))
    return found


def issue(level: str, code: str, message: str, **details: object) -> dict:
    row = {"level": level, "code": code, "message": message}
    row.update(details)
    return row


def audit(path: Path, style: str) -> dict:
    if style not in ("generic", "apa7"):
        raise ValueError("unsupported citation style")
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    body, reference_text = split_document(text)
    issues: list[dict] = []
    if not reference_text.strip():
        issues.append(issue("BLOCK", "NO_REFERENCE_SECTION", "No References or Bibliography heading was found."))
        refs: list[dict] = []
    else:
        refs = parse_references(reference_text)

    by_surname: dict[str, set[str]] = defaultdict(set)
    for row in refs:
        if row["surname"] and row["initial"]:
            by_surname[row["surname"]].add(row["initial"])
    collisions = {surname: sorted(initials) for surname, initials in by_surname.items() if len(initials) > 1}

    if style == "apa7":
        for surname, initials in collisions.items():
            bare = re.compile(rf"(?<!\b[A-Z]\.\s)\b{re.escape(surname)}(?:\s+et\s+al\.)?(?=\s*[,(&]|\s+and\b)")
            if bare.search(body):
                issues.append(
                    issue(
                        "BLOCK",
                        "APA_SAME_SURNAME_INITIAL",
                        f"{surname} has different first-author initials in the reference list, but a citation without first-author initials occurs in the text.",
                        surname=surname,
                        initials=initials,
                    )
                )

    doi_rows: dict[str, list[int]] = defaultdict(list)
    for row in refs:
        if row["doi"]:
            doi_rows[row["doi"]].append(row["index"])
    for doi, indexes in doi_rows.items():
        if len(indexes) > 1:
            issues.append(issue("BLOCK", "DUPLICATE_DOI", f"DOI occurs in more than one reference entry: {doi}", entries=indexes))

    reference_keys = {(row["surname"], row["year"]) for row in refs if row["surname"] and row["year"]}
    citation_keys = body_citations(body)
    for surname, year in sorted(citation_keys - reference_keys):
        issues.append(issue("BLOCK", "CITATION_WITHOUT_REFERENCE", f"In-text citation has no parsed reference entry: {surname}, {year}."))
    for surname, year in sorted(reference_keys - citation_keys):
        issues.append(issue("REVIEW", "REFERENCE_NOT_CITED", f"Reference entry was not found in parsed in-text citations: {surname}, {year}."))

    duplicate_keys: dict[tuple[str, str], list[int]] = defaultdict(list)
    for row in refs:
        if row["surname"] and row["year"]:
            duplicate_keys[(row["surname"], row["year"])].append(row["index"])
    for (surname, year), indexes in duplicate_keys.items():
        if len(indexes) > 1:
            issues.append(
                issue(
                    "REVIEW",
                    "SAME_FIRST_AUTHOR_YEAR",
                    f"Multiple references share parsed first author and year: {surname}, {year}; check style-specific disambiguation.",
                    entries=indexes,
                )
            )

    unparsed = [row["index"] for row in refs if not row["surname"] or not row["year"]]
    if unparsed:
        issues.append(issue("REVIEW", "UNPARSED_REFERENCE", "Some references require manual identity review.", entries=unparsed))

    levels = {row["level"] for row in issues}
    structural_status = "BLOCK" if "BLOCK" in levels else "REVIEW" if "REVIEW" in levels else "PASS"
    # A regex match does not verify author identity, DOI existence or publication metadata.
    issues.append(issue("REVIEW", "IDENTITY_NOT_VERIFIED", "Local syntax checks do not verify author identities or publication metadata against original sources."))
    if style == "generic":
        issues.append(issue("REVIEW", "STYLE_NOT_SPECIFIED", "A required citation style has not been supplied."))
    status = "BLOCK" if structural_status == "BLOCK" else "REVIEW"
    return {
        "schema_version": "rw-citation-audit/v1",
        "document": str(path),
        "document_sha256": hashlib.sha256(raw).hexdigest(),
        "audit_scope": "local_author_year_syntax_only",
        "structural_status": structural_status,
        "identity_verification": "NOT_CHECKED",
        "style": style,
        "status": status,
        "reference_count": len(refs),
        "parsed_citation_count": len(citation_keys),
        "surname_collisions": collisions,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("document", type=Path)
    parser.add_argument("--style", choices=("generic", "apa7"), default="generic")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.output:
        if args.output.resolve() == args.document.resolve() or (args.output.exists() and args.document.exists() and args.output.samefile(args.document)):
            print("BLOCK: audit output must differ from the input document")
            return 2
        if args.output.exists() and not args.force:
            print("BLOCK: output already exists; use --force")
            return 2
    result = audit(args.document, args.style)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return {"PASS": 0, "REVIEW": 1, "BLOCK": 2}[result["status"]]


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, TypeError) as exc:
        print(f"BLOCK: {exc}")
        raise SystemExit(2)
