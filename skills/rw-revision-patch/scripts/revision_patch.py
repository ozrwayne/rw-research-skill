#!/usr/bin/env python3
"""Anchor Markdown blocks and apply hash-checked replacement patches."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MANIFEST_VERSION = "rw-revision-manifest/v1"
PATCH_VERSION = "rw-revision-patch/v1"
MARKER_RE = re.compile(r"^<!--rw-block:(B\d{4,})-->\r?\n", re.MULTILINE)
ANY_MARKER_RE = re.compile(r"<!--rw-block:B\d{4,}-->")


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Block:
    block_id: str
    text: str

    @property
    def block_hash(self) -> str:
        return digest(self.text)


def read_text_exact(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"input must be a regular file: {path}")
    return path.read_bytes().decode("utf-8")


def split_preamble(text: str) -> tuple[str, str]:
    # Preserve a leading YAML front matter block before HTML markers.
    front = re.match(r"\A(?:\ufeff)?---[ \t]*\r?\n.*?^(?:---|\.\.\.)[ \t]*(?:\r?\n|$)", text, re.MULTILINE | re.DOTALL)
    return (text[:front.end()], text[front.end():]) if front else ("", text)


def split_unanchored(text: str) -> list[str]:
    """Insert markers only between blocks; retain exact whitespace and fenced code."""
    if not text.strip():
        raise ValueError("document is empty")
    parts = []
    lines = text.splitlines(keepends=True)
    current = []
    fence = None
    for index, line in enumerate(lines):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if marker:
            run, suffix = marker.groups()
            if fence is None:
                fence = (run[0], len(run))
            elif run[0] == fence[0] and len(run) >= fence[1] and not suffix.strip():
                fence = None
        current.append(line)
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        # Keep indented/list continuation and blank runs inside their original block.
        if (not line.strip() and next_line.strip() and fence is None
                and not next_line.startswith((" ", "\t")) and any(row.strip() for row in current)):
            parts.append("".join(current))
            current = []
    if current:
        parts.append("".join(current))
    return parts


def parse_anchored(text: str) -> list[Block]:
    matches = list(MARKER_RE.finditer(text))
    if not matches:
        raise ValueError("document has no RW block markers")
    prefix = text[: matches[0].start()]
    _, prefix_content = split_preamble(prefix)
    if prefix_content.strip():
        raise ValueError("content appears before first RW block marker")
    blocks: list[Block] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip("\r\n")
        if not body.strip():
            raise ValueError(f"empty block: {match.group(1)}")
        blocks.append(Block(match.group(1), body))
    if len({block.block_id for block in blocks}) != len(blocks):
        raise ValueError("duplicate block ids in document")
    return blocks


def render(blocks: list[Block]) -> str:
    return "\n\n".join(f"<!--rw-block:{block.block_id}-->\n{block.text}" for block in blocks) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def constant(value):
        raise ValueError(f"non-finite JSON number: {value}")
    data = json.loads(read_text_exact(path), object_pairs_hook=pairs, parse_constant=constant)
    json.dumps(data, allow_nan=False)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def refuse_same(input_path: Path, output_path: Path) -> None:
    if (input_path.resolve() == output_path.resolve()
            or (input_path.exists() and output_path.exists() and input_path.samefile(output_path))):
        raise ValueError("output must differ from input; original files are not overwritten")


def distinct_paths(*paths: Path) -> None:
    for index, path in enumerate(paths):
        for other in paths[index + 1:]:
            refuse_same(path, other)


def write_outputs(outputs: dict[Path, str]) -> None:
    """Stage all outputs before replacement; restore prior bytes on handled write failures."""
    staged = {}
    originals = {}
    replaced = []
    try:
        for path, text in outputs.items():
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise ValueError(f"output must be a regular file, not a symlink: {path}")
            originals[path] = path.read_bytes() if path.exists() else None
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            staged[path] = Path(name)
            with os.fdopen(fd, "wb") as stream:
                stream.write(text.encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
        for path, temp in staged.items():
            os.replace(temp, path)
            replaced.append(path)
    except Exception:
        for path in reversed(replaced):
            if originals[path] is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(originals[path])
        raise
    finally:
        for temp in staged.values():
            temp.unlink(missing_ok=True)


def command_anchor(args: argparse.Namespace) -> int:
    source = Path(args.input)
    output = Path(args.output)
    manifest_path = Path(args.manifest)
    distinct_paths(source, output, manifest_path)
    if not args.force and (output.exists() or manifest_path.exists()):
        print("refusing to overwrite existing output or manifest; use --force")
        return 2
    raw = read_text_exact(source)
    if ANY_MARKER_RE.search(raw):
        blocks = parse_anchored(raw)
        anchored = raw
    else:
        preamble, body = split_preamble(raw)
        anchored = preamble + "".join(f"<!--rw-block:B{index:04d}-->\n{part}" for index, part in enumerate(split_unanchored(body), start=1))
        blocks = parse_anchored(anchored)
    manifest = {
        "schema_version": MANIFEST_VERSION,
        "source_path": str(source.resolve()),
        "anchored_path": str(output.resolve()),
        "base_document_hash": digest(anchored),
        "blocks": [
            {"block_id": block.block_id, "block_hash": block.block_hash, "first_line": block.text.splitlines()[0][:120]}
            for block in blocks
        ],
    }
    write_outputs({output: anchored, manifest_path: json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"})
    print(f"anchored {len(blocks)} blocks")
    return 0


def validate_inputs(document: Path, manifest_path: Path, patch_path: Path, allow_large_patch: bool) -> tuple[list[Block], dict[str, Any], dict[str, Any], list[str]]:
    errors: list[str] = []
    document_text = read_text_exact(document)
    blocks = parse_anchored(document_text)
    manifest = read_json(manifest_path)
    patch = read_json(patch_path)
    if manifest.get("schema_version") != MANIFEST_VERSION:
        errors.append("invalid manifest schema_version")
    if patch.get("schema_version") != PATCH_VERSION:
        errors.append("invalid patch schema_version")
    current_hash = digest(document_text)
    if manifest.get("base_document_hash") != current_hash:
        errors.append("manifest base_document_hash does not match document")
    if patch.get("base_document_hash") != current_hash:
        errors.append("patch base_document_hash does not match document")
    rows = manifest.get("blocks")
    if not isinstance(rows, list) or any(not isinstance(item, dict) or not isinstance(item.get("block_id"), str) or not isinstance(item.get("block_hash"), str) for item in rows):
        return blocks, manifest, patch, errors + ["manifest.blocks must contain block ids and hashes"]
    manifest_blocks = {item["block_id"]: item["block_hash"] for item in rows}
    if len(rows) != len(manifest_blocks) or set(manifest_blocks) != {block.block_id for block in blocks}:
        errors.append("manifest block ids must exactly match document without duplicates")
    current_blocks = {block.block_id: block for block in blocks}
    for block in blocks:
        if manifest_blocks.get(block.block_id) != block.block_hash:
            errors.append(f"manifest hash mismatch for {block.block_id}")
    operations = patch.get("operations")
    if not isinstance(operations, list) or not operations:
        errors.append("patch operations must be a non-empty array")
        return blocks, manifest, patch, errors
    seen: set[str] = set()
    for index, operation in enumerate(operations):
        prefix = f"operations[{index}]"
        if not isinstance(operation, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if operation.get("op") != "replace":
            errors.append(f"{prefix}.op must be replace")
        block_id = operation.get("block_id")
        if not isinstance(block_id, str) or block_id not in current_blocks:
            errors.append(f"{prefix}.block_id does not exist")
            continue
        if block_id in seen:
            errors.append(f"duplicate operation for {block_id}")
        seen.add(block_id)
        if operation.get("expected_hash") != current_blocks[block_id].block_hash:
            errors.append(f"{prefix}.expected_hash mismatch for {block_id}")
        new_text = operation.get("new_text")
        if not isinstance(new_text, str) or not new_text.strip():
            errors.append(f"{prefix}.new_text must be non-empty")
        elif ANY_MARKER_RE.search(new_text):
            errors.append(f"{prefix}.new_text must not contain RW block markers")
        if not isinstance(operation.get("reason"), str) or not operation["reason"].strip():
            errors.append(f"{prefix}.reason must be non-empty")
        issue_ids = operation.get("issue_ids")
        if not isinstance(issue_ids, list) or not issue_ids or not all(isinstance(value, str) and value.strip() for value in issue_ids):
            errors.append(f"{prefix}.issue_ids must be an array of strings")
    touched_ratio = len(seen) / len(blocks)
    if touched_ratio > 0.60 and not allow_large_patch:
        errors.append(f"patch touches {touched_ratio:.1%} of blocks; explicit --allow-large-patch required above 60%")
    return blocks, manifest, patch, errors


def command_check(args: argparse.Namespace) -> int:
    try:
        blocks, _, _, errors = validate_inputs(Path(args.document), Path(args.manifest), Path(args.patch), args.allow_large_patch)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"check failed: {exc}")
        return 2
    if errors:
        print("\n".join(errors))
        return 2
    print(f"patch valid for {len(blocks)} blocks")
    print("patch_sha256=" + hashlib.sha256(Path(args.patch).read_bytes()).hexdigest())
    return 0


def command_apply(args: argparse.Namespace) -> int:
    document = Path(args.document)
    output = Path(args.output)
    report_path = Path(args.report)
    manifest_path = Path(args.manifest)
    patch_path = Path(args.patch)
    distinct_paths(document, manifest_path, patch_path, output, report_path)
    expected_confirmation = hashlib.sha256(patch_path.read_bytes()).hexdigest()
    if getattr(args, "confirm_patch_sha256", None) != expected_confirmation:
        print("apply requires --confirm-patch-sha256 matching the approved patch bytes")
        return 2
    if not args.force and (output.exists() or report_path.exists()):
        print("refusing to overwrite existing output or report; use --force")
        return 2
    try:
        blocks, manifest, patch, errors = validate_inputs(document, manifest_path, patch_path, args.allow_large_patch)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"apply failed: {exc}")
        return 2
    if errors:
        print("\n".join(errors))
        return 2
    source_path = manifest.get("source_path")
    if isinstance(source_path, str):
        source = Path(source_path)
        if not source.is_absolute():
            source = manifest_path.parent / source
        refuse_same(source, output)
        refuse_same(source, report_path)
    original_text = read_text_exact(document)
    if digest(original_text) != patch["base_document_hash"] or hashlib.sha256(patch_path.read_bytes()).hexdigest() != expected_confirmation:
        print("input changed after validation")
        return 2
    operations = {operation["block_id"]: operation for operation in patch["operations"]}
    revised: list[Block] = []
    changes: list[dict[str, Any]] = []
    for block in blocks:
        operation = operations.get(block.block_id)
        if operation is None:
            revised.append(block)
            continue
        new_block = Block(block.block_id, operation["new_text"].strip("\r\n"))
        revised.append(new_block)
        changes.append({
            "block_id": block.block_id,
            "old_hash": block.block_hash,
            "new_hash": new_block.block_hash,
            "reason": operation["reason"],
            "issue_ids": operation["issue_ids"],
        })
    # Splice only approved body ranges. Marker lines, prefixes, blank lines and
    # every untouched block remain byte-for-byte unchanged.
    matches = list(MARKER_RE.finditer(original_text))
    revised_text = original_text
    for index in range(len(matches) - 1, -1, -1):
        match = matches[index]
        operation = operations.get(match.group(1))
        if operation is None:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(original_text)
        raw_body = original_text[start:end]
        leading = len(raw_body) - len(raw_body.lstrip("\r\n"))
        trailing = len(raw_body) - len(raw_body.rstrip("\r\n"))
        body_end = end - trailing if trailing else end
        revised_text = revised_text[:start + leading] + operation["new_text"].strip("\r\n") + revised_text[body_end:]
    preserved = len(blocks) - len(changes)
    report = {
        "schema_version": "rw-revision-report/v1",
        "base_document_hash": digest(original_text),
        "approved_patch_sha256": expected_confirmation,
        "revised_document_hash": digest(revised_text),
        "total_blocks": len(blocks),
        "changed_blocks": len(changes),
        "preserved_blocks": preserved,
        "preserved_ratio": preserved / len(blocks),
        "changes": changes,
    }
    write_outputs({output: revised_text, report_path: json.dumps(report, ensure_ascii=False, indent=2) + "\n"})
    print(f"applied {len(changes)} changes; preserved {preserved}/{len(blocks)} blocks")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    anchor = subparsers.add_parser("anchor")
    anchor.add_argument("input")
    anchor.add_argument("--output", required=True)
    anchor.add_argument("--manifest", required=True)
    anchor.add_argument("--force", action="store_true")
    anchor.set_defaults(func=command_anchor)
    for name, function in [("check", command_check), ("apply", command_apply)]:
        sub = subparsers.add_parser(name)
        sub.add_argument("document")
        sub.add_argument("--manifest", required=True)
        sub.add_argument("--patch", required=True)
        sub.add_argument("--allow-large-patch", action="store_true")
        if name == "apply":
            sub.add_argument("--output", required=True)
            sub.add_argument("--report", required=True)
            sub.add_argument("--force", action="store_true")
            sub.add_argument("--confirm-patch-sha256", required=True)
        sub.set_defaults(func=function)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"BLOCK: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
