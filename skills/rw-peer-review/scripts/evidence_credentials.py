#!/usr/bin/env python3
"""Manage hierarchical evidence credentials and bounded context packs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "rw-peer-review-evidence-credentials/v1"
PACK_SCHEMA_VERSION = "rw-peer-review-paper-context-pack/v1"
KINDS = {
    "source", "page", "section", "paragraph", "table", "figure", "caption",
    "legend", "footnote", "supplement", "method_definition", "result", "claim",
}
STATES = {
    "discovered", "extracted", "linked", "verified", "disputed", "needs_input",
    "superseded", "stale", "revoked",
}
INVALIDATING_STATES = {"disputed", "needs_input", "superseded", "stale", "revoked"}
TRANSITIONS = {
    "discovered": {"extracted", "needs_input", "stale", "revoked"},
    "extracted": {"linked", "verified", "disputed", "needs_input", "stale", "revoked"},
    "linked": {"verified", "disputed", "needs_input", "stale", "revoked"},
    "verified": {"disputed", "needs_input", "superseded", "stale", "revoked"},
    "disputed": {"linked", "verified", "needs_input", "stale", "revoked"},
    "needs_input": {"extracted", "linked", "verified", "stale", "revoked"},
    "superseded": {"revoked"},
    "stale": {"extracted", "linked", "revoked"},
    "revoked": set(),
}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def strict_json(text: str) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def constant(value):
        raise ValueError(f"non-finite JSON number: {value}")
    result = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    json.dumps(result, allow_nan=False)
    return result


def input_errors(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["root must be an object"]
    try:
        json.dumps(data, allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        return [f"invalid JSON data: {exc}"]
    return []


def load(path: Path) -> dict[str, Any]:
    data = strict_json(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("root must be an object")
    return data


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temp_name, path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def file_hash(path: Path) -> str:
    if not path.is_file():
        raise OSError(f"source is not a regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def credential_hash(item: dict[str, Any]) -> str:
    mutable = {"status", "updated_at", "content_hash"}
    return canonical_hash({key: value for key, value in item.items() if key not in mutable})


def pack_hash(item: dict[str, Any]) -> str:
    return canonical_hash({key: value for key, value in item.items() if key != "pack_hash"})


def index_credentials(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["id"]: item
        for item in data.get("credentials", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def find_cycle(edges: dict[str, list[str]]) -> list[str] | None:
    # Iterative DFS: depth is not a credential-store capacity limit.
    visited: set[str] = set()
    for root in edges:
        if root in visited:
            continue
        path = [root]
        active = {root: 0}
        stack = [iter(edges.get(root, []))]
        while stack:
            child = next(stack[-1], None)
            if child is None:
                node = path.pop()
                visited.add(node)
                active.pop(node)
                stack.pop()
            elif child in active:
                return path[active[child]:] + [child]
            elif child not in visited:
                active[child] = len(path)
                path.append(child)
                stack.append(iter(edges.get(child, [])))
    return None


def validate(data: dict[str, Any]) -> list[str]:
    errors = input_errors(data)
    if errors:
        return errors
    try:
        return _validate(data)
    except (TypeError, AttributeError, KeyError, RecursionError) as exc:
        return [f"invalid field type or structure: {exc}"]


def _validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ["schema_version", "review_id", "updated_at", "credentials", "audit_log"]
    for field in required:
        if field not in data:
            errors.append(f"missing top-level field: {field}")
    if errors:
        return errors
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not isinstance(data.get("review_id"), str) or not data["review_id"].strip():
        errors.append("review_id must be a non-empty string")
    if not isinstance(data.get("updated_at"), str) or not data["updated_at"].strip():
        errors.append("updated_at must be a non-empty string")
    if not isinstance(data.get("credentials"), list):
        errors.append("credentials must be an array")
    if not isinstance(data.get("audit_log"), list):
        errors.append("audit_log must be an array")
    if errors:
        return errors

    items = data["credentials"]
    identifiers = [item.get("id") for item in items if isinstance(item, dict)]
    seen: set[str] = set()
    for identifier in identifiers:
        if isinstance(identifier, str) and identifier in seen:
            errors.append(f"duplicate credential id: {identifier}")
        if isinstance(identifier, str):
            seen.add(identifier)
    by_id = index_credentials(data)

    dependency_edges: dict[str, list[str]] = {}
    parent_edges: dict[str, list[str]] = {}
    for index, item in enumerate(items):
        prefix = f"credentials[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in [
            "id", "kind", "source_id", "parent_id", "previous_id", "next_id",
            "required_dependencies", "optional_dependencies", "status", "locator",
            "text", "metadata", "created_at", "updated_at", "content_hash",
        ]:
            if field not in item:
                errors.append(f"{prefix} missing field: {field}")
        identifier = item.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
            continue
        if item.get("kind") not in KINDS:
            errors.append(f"{prefix}.kind is invalid")
        if item.get("status") not in STATES:
            errors.append(f"{prefix}.status is invalid")
        for field in ["required_dependencies", "optional_dependencies"]:
            if not string_list(item.get(field)):
                errors.append(f"{prefix}.{field} must be an array of non-empty strings")
        if not isinstance(item.get("locator"), dict):
            errors.append(f"{prefix}.locator must be an object")
        else:
            locator = item["locator"]
            if not isinstance(locator.get("pointer"), str) or not locator["pointer"].strip():
                errors.append(f"{prefix}.locator.pointer must be a non-empty string")
            if "page" in locator and (type(locator["page"]) is not int or locator["page"] < 1):
                errors.append(f"{prefix}.locator.page must be a positive integer")
            if "bbox" in locator:
                bbox = locator["bbox"]
                if (not isinstance(bbox, list) or len(bbox) != 4
                        or not all(type(x) in (int, float) and math.isfinite(x) for x in bbox)
                        or bbox[0] > bbox[2] or bbox[1] > bbox[3]):
                    errors.append(f"{prefix}.locator.bbox must be four finite ordered coordinates")
        if not isinstance(item.get("text"), str):
            errors.append(f"{prefix}.text must be a string")
        if not isinstance(item.get("metadata"), dict):
            errors.append(f"{prefix}.metadata must be an object")
        for field in ["created_at", "updated_at", "content_hash"]:
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")

        source_id = item.get("source_id")
        if item.get("kind") == "source":
            if source_id is not None:
                errors.append(f"{prefix}.source_id must be null for source credentials")
        elif not isinstance(source_id, str) or source_id not in by_id:
            errors.append(f"{prefix}.source_id references missing source: {source_id}")
        elif by_id[source_id].get("kind") != "source":
            errors.append(f"{prefix}.source_id must reference a source credential")

        for field in ["parent_id", "previous_id", "next_id"]:
            reference = item.get(field)
            if reference is not None and (not isinstance(reference, str) or reference not in by_id):
                errors.append(f"{prefix}.{field} references missing credential: {reference}")
            elif isinstance(reference, str):
                referenced = by_id[reference]
                current_root = identifier if item.get("kind") == "source" else item.get("source_id")
                referenced_root = reference if referenced.get("kind") == "source" else referenced.get("source_id")
                if current_root != referenced_root:
                    errors.append(f"{prefix}.{field} crosses source boundary: {reference}")
        previous_id = item.get("previous_id")
        if isinstance(previous_id, str) and previous_id in by_id:
            previous_next = by_id[previous_id].get("next_id")
            if previous_next is not None and previous_next != identifier:
                errors.append(f"{prefix}.previous_id is not reciprocal with {previous_id}.next_id")
        next_id = item.get("next_id")
        if isinstance(next_id, str) and next_id in by_id:
            next_previous = by_id[next_id].get("previous_id")
            if next_previous is not None and next_previous != identifier:
                errors.append(f"{prefix}.next_id is not reciprocal with {next_id}.previous_id")
        for field in ["required_dependencies", "optional_dependencies"]:
            values = item.get(field, []) if isinstance(item.get(field), list) else []
            if len(values) != len(set(values)):
                errors.append(f"{prefix}.{field} contains duplicates")
            for reference in values:
                if reference == identifier:
                    errors.append(f"{prefix}.{field} cannot reference itself")
                elif reference not in by_id:
                    errors.append(f"{prefix}.{field} references missing credential: {reference}")

        if isinstance(item.get("content_hash"), str) and item["content_hash"] != credential_hash(item):
            errors.append(f"{prefix}.content_hash does not match credential content")

        required_dependencies = item.get("required_dependencies", [])
        if isinstance(required_dependencies, list):
            dependency_edges[identifier] = [ref for ref in required_dependencies if ref in by_id]
        parent_id = item.get("parent_id")
        parent_edges[identifier] = [parent_id] if isinstance(parent_id, str) and parent_id in by_id else []

        if item.get("status") == "verified":
            for dependency in dependency_edges.get(identifier, []):
                if by_id[dependency].get("status") != "verified":
                    errors.append(
                        f"{prefix} is verified but required dependency {dependency} is {by_id[dependency].get('status')}"
                    )

    dependency_cycle = find_cycle(dependency_edges)
    if dependency_cycle:
        errors.append(f"required dependency cycle: {' -> '.join(dependency_cycle)}")
    parent_cycle = find_cycle(parent_edges)
    if parent_cycle:
        errors.append(f"parent cycle: {' -> '.join(parent_cycle)}")
    return errors


def append_audit(data: dict[str, Any], action: str, target_id: str, reason: str) -> None:
    timestamp = now()
    data["updated_at"] = timestamp
    data.setdefault("audit_log", []).append(
        {"at": timestamp, "action": action, "target_id": target_id, "reason": reason}
    )


def write_if_valid(path: Path, data: dict[str, Any], message: str) -> int:
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    atomic_write(path, data)
    print(message)
    return 0


def parse_bbox(value: str | None) -> list[float] | None:
    if value is None:
        return None
    parts = value.split(",")
    if len(parts) != 4:
        raise ValueError("bbox must contain x0,y0,x1,y1")
    bbox = [float(part) for part in parts]
    if not all(math.isfinite(value) for value in bbox) or bbox[0] > bbox[2] or bbox[1] > bbox[3]:
        raise ValueError("bbox must be finite and ordered x0 <= x1, y0 <= y1")
    return bbox


def read_metadata(path: str | None) -> dict[str, Any]:
    if path is None:
        return {}
    value = strict_json(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("metadata file must contain an object")
    return value


def command_init(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.exists() and not args.force:
        print(f"refusing to overwrite existing file: {path}")
        return 2
    timestamp = now()
    data = {
        "schema_version": SCHEMA_VERSION,
        "review_id": args.review_id,
        "updated_at": timestamp,
        "credentials": [],
        "audit_log": [
            {"at": timestamp, "action": "store_initialized", "target_id": args.review_id, "reason": "store opened"}
        ],
    }
    return write_if_valid(path, data, f"created {path}")


def command_add(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    if args.id in index_credentials(data):
        print(f"duplicate credential id: {args.id}")
        return 2
    if args.text is not None and args.text_file is not None:
        print("use only one of --text or --text-file")
        return 2
    text = args.text or ""
    if args.text_file is not None:
        text = Path(args.text_file).read_text(encoding="utf-8")
    try:
        bbox = parse_bbox(args.bbox)
        metadata = read_metadata(args.metadata_file)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"invalid credential input: {exc}")
        return 2
    source_file_value = getattr(args, "source_file", None)
    if source_file_value is not None:
        if args.kind != "source":
            print("--source-file is only valid for source credentials")
            return 2
        source_file = Path(source_file_value).resolve()
        try:
            metadata.update({
                "source_path": str(source_file),
                "source_sha256": file_hash(source_file),
                "source_size": source_file.stat().st_size,
            })
        except OSError as exc:
            print(f"cannot hash source file: {exc}")
            return 2
    timestamp = now()
    locator: dict[str, Any] = {"pointer": args.pointer}
    if args.page is not None:
        locator["page"] = args.page
    if bbox is not None:
        locator["bbox"] = bbox
    item = {
        "id": args.id,
        "kind": args.kind,
        "source_id": args.source_id,
        "parent_id": args.parent_id,
        "previous_id": args.previous_id,
        "next_id": args.next_id,
        "required_dependencies": list(dict.fromkeys(args.required_dependency)),
        "optional_dependencies": list(dict.fromkeys(args.optional_dependency)),
        "status": args.status,
        "locator": locator,
        "text": text,
        "metadata": metadata,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    item["content_hash"] = credential_hash(item)
    data.setdefault("credentials", []).append(item)
    append_audit(data, "credential_added", args.id, args.reason)
    return write_if_valid(path, data, f"added {args.id}")


def normalize_import_record(record: dict[str, Any], timestamp: str) -> dict[str, Any]:
    if not isinstance(record.get("id"), str) or not record["id"].strip():
        raise ValueError("every imported credential needs a non-empty id")
    if record.get("kind") not in KINDS:
        raise ValueError(f"credential {record['id']} has invalid kind")
    metadata = record.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError(f"credential {record['id']} metadata must be an object")
    metadata = dict(metadata)
    source_file_value = record.get("source_file")
    if source_file_value is not None:
        if record["kind"] != "source" or not isinstance(source_file_value, str):
            raise ValueError(f"credential {record['id']} has invalid source_file")
        source_file = Path(source_file_value).resolve()
        metadata.update({
            "source_path": str(source_file),
            "source_sha256": file_hash(source_file),
            "source_size": source_file.stat().st_size,
        })
    item = {
        "id": record["id"],
        "kind": record["kind"],
        "source_id": record.get("source_id"),
        "parent_id": record.get("parent_id"),
        "previous_id": record.get("previous_id"),
        "next_id": record.get("next_id"),
        "required_dependencies": record.get("required_dependencies", []),
        "optional_dependencies": record.get("optional_dependencies", []),
        "status": record.get("status", "discovered"),
        "locator": record.get("locator", {}),
        "text": record.get("text", ""),
        "metadata": metadata,
        "created_at": record.get("created_at", timestamp),
        "updated_at": record.get("updated_at", timestamp),
    }
    item["content_hash"] = credential_hash(item)
    return item


def command_import(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    try:
        payload = strict_json(Path(args.input).read_text(encoding="utf-8"))
        records = payload.get("credentials") if isinstance(payload, dict) else payload
        if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
            raise ValueError("import input must be an array or an object with a credentials array")
        timestamp = now()
        normalized = [normalize_import_record(item, timestamp) for item in records]
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"invalid import input: {exc}")
        return 2
    existing_ids = set(index_credentials(data))
    incoming_ids = [item["id"] for item in normalized]
    duplicate_incoming = sorted(identifier for identifier, count in Counter(incoming_ids).items() if count > 1)
    if duplicate_incoming:
        print(f"duplicate imported credential ids: {', '.join(duplicate_incoming)}")
        return 2
    overlap = sorted(existing_ids.intersection(incoming_ids))
    if overlap:
        print(f"import would replace existing credentials: {', '.join(overlap)}")
        return 2
    data.setdefault("credentials", []).extend(normalized)
    append_audit(data, "credentials_imported", args.input, f"{args.reason}; count={len(normalized)}")
    return write_if_valid(path, data, f"imported {len(normalized)} credential(s)")


def command_link(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    target = index_credentials(data).get(args.id)
    if target is None:
        print(f"missing credential: {args.id}")
        return 2
    if target.get("status") in {"verified", "superseded", "revoked"}:
        print(f"credential {args.id} cannot be relinked from status {target.get('status')}")
        return 2
    for field, values in [
        ("required_dependencies", args.required_dependency),
        ("optional_dependencies", args.optional_dependency),
    ]:
        for value in values:
            if value not in target[field]:
                target[field].append(value)
    for field in ["parent_id", "previous_id", "next_id"]:
        value = getattr(args, field)
        if value is not None:
            target[field] = value
    target["status"] = "linked"
    target["updated_at"] = now()
    target["content_hash"] = credential_hash(target)
    append_audit(data, "credential_linked", args.id, args.reason)
    return write_if_valid(path, data, f"linked {args.id}")


def reverse_dependents(data: dict[str, Any]) -> dict[str, set[str]]:
    reverse: dict[str, set[str]] = {}
    for item in data.get("credentials", []):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        identifier = item["id"]
        for dependency in item.get("required_dependencies", []):
            reverse.setdefault(dependency, set()).add(identifier)
    return reverse


def dependent_closure(data: dict[str, Any], root_id: str) -> set[str]:
    reverse = reverse_dependents(data)
    result: set[str] = set()
    stack = list(reverse.get(root_id, set()))
    while stack:
        current = stack.pop()
        if current in result:
            continue
        result.add(current)
        stack.extend(reverse.get(current, set()))
    return result


def command_set_status(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    by_id = index_credentials(data)
    target = by_id.get(args.id)
    if target is None:
        print(f"missing credential: {args.id}")
        return 2
    old_status = target.get("status")
    if args.status != old_status and args.status not in TRANSITIONS.get(old_status, set()):
        print(f"invalid status transition: {old_status} -> {args.status}")
        return 2
    if args.status == "verified":
        missing = [
            dependency for dependency in target.get("required_dependencies", [])
            if by_id.get(dependency, {}).get("status") != "verified"
        ]
        if missing:
            print(f"cannot verify {args.id}; required dependencies not verified: {', '.join(missing)}")
            return 2
    target["status"] = args.status
    target["updated_at"] = now()
    changed = [args.id]
    if args.status in INVALIDATING_STATES and args.propagate:
        affected = dependent_closure(data, args.id)
        if target.get("kind") == "source":
            direct_children = {
                identifier for identifier, item in by_id.items() if item.get("source_id") == args.id
            }
            affected.update(direct_children)
            for child_id in direct_children:
                affected.update(dependent_closure(data, child_id))
        for dependent_id in sorted(affected):
            dependent = by_id[dependent_id]
            if dependent.get("status") not in {"superseded", "revoked", "stale"}:
                dependent["status"] = "stale"
                dependent["updated_at"] = now()
                changed.append(dependent_id)
    append_audit(data, "credential_status_set", args.id, f"{args.reason}; affected={','.join(changed)}")
    return write_if_valid(path, data, f"updated {args.id}; affected {len(changed)} credential(s)")


def required_closure(by_id: dict[str, dict[str, Any]], roots: Iterable[str]) -> set[str]:
    result: set[str] = set()
    stack = list(roots)
    while stack:
        current = stack.pop()
        if current in result:
            continue
        result.add(current)
        item = by_id.get(current)
        if item is None:
            continue
        if item.get("kind") == "source":
            continue
        stack.extend(item.get("required_dependencies", []))
    return result


def source_roots(by_id: dict[str, dict[str, Any]], ids: Iterable[str]) -> set[str]:
    roots: set[str] = set()
    for identifier in ids:
        item = by_id.get(identifier)
        if not item:
            continue
        if item.get("kind") == "source":
            roots.add(identifier)
        elif isinstance(item.get("source_id"), str):
            roots.add(item["source_id"])
    return roots


def gate_sources(data: dict[str, Any], requested_sources: Iterable[str] | None = None) -> tuple[str, list[str]]:
    errors = validate(data)
    if errors:
        return "BLOCK", errors
    by_id = index_credentials(data)
    source_ids = list(requested_sources or [
        identifier for identifier, item in by_id.items() if item.get("kind") == "source"
    ])
    if not source_ids:
        return "REVIEW", ["no source credential registered"]
    reasons: list[str] = []
    for source_id in source_ids:
        source = by_id.get(source_id)
        if source is None or source.get("kind") != "source":
            reasons.append(f"missing source credential: {source_id}")
            continue
        if source.get("status") != "verified":
            reasons.append(f"source {source_id} is {source.get('status')}")
        metadata = source.get("metadata", {})
        source_path = metadata.get("source_path") if isinstance(metadata, dict) else None
        source_sha256 = metadata.get("source_sha256") if isinstance(metadata, dict) else None
        if not isinstance(source_path, str) or not isinstance(source_sha256, str):
            reasons.append(f"source {source_id} has no registered file hash")
        else:
            try:
                current_hash = file_hash(Path(source_path))
            except OSError as exc:
                reasons.append(f"source {source_id} cannot be read: {exc}")
            else:
                if current_hash != source_sha256:
                    reasons.append(f"source {source_id} file hash changed")
        if not source.get("required_dependencies"):
            reasons.append(f"source {source_id} has no declared coverage dependencies")
        for dependency in source.get("required_dependencies", []):
            dependency_item = by_id.get(dependency)
            if dependency_item is None:
                reasons.append(f"source {source_id} missing required credential {dependency}")
            elif dependency_item.get("status") != "verified":
                reasons.append(
                    f"source {source_id} required credential {dependency} is {dependency_item.get('status')}"
                )
    return ("PASS", []) if not reasons else ("BLOCK", reasons)


def project_credential(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "kind": item["kind"],
        "source_id": item["source_id"],
        "parent_id": item["parent_id"],
        "previous_id": item["previous_id"],
        "next_id": item["next_id"],
        "required_dependencies": item["required_dependencies"],
        "optional_dependencies": item["optional_dependencies"],
        "locator": item["locator"],
        "text": item["text"],
        "metadata": item["metadata"],
        "content_hash": item["content_hash"],
    }


def select_pack_ids(by_id, target_ids, include_adjacent, include_parent):
    selected = required_closure(by_id, target_ids)
    context_only = set()
    for identifier in list(selected):
        item = by_id[identifier]
        if include_adjacent:
            context_only.update(item[field] for field in ("previous_id", "next_id") if isinstance(item.get(field), str))
        if include_parent and isinstance(item.get("parent_id"), str):
            context_only.add(item["parent_id"])
    # Context is still evidence: include its necessary dependencies too.
    return selected | required_closure(by_id, context_only)


def build_pack(
    data: dict[str, Any], *, pack_id: str, finding_id: str, target_ids: list[str],
    include_adjacent: bool = True, include_parent: bool = True, max_credentials: int = 40,
    max_estimated_tokens: int = 20000,
) -> tuple[str, dict[str, Any] | None, list[str]]:
    errors = validate(data)
    if errors:
        return "BLOCK", None, errors
    if not string_list(target_ids) or not target_ids or len(set(target_ids)) != len(target_ids):
        return "BLOCK", None, ["target_ids must be a non-empty unique array of strings"]
    if not all(isinstance(value, str) and value.strip() for value in (pack_id, finding_id)):
        return "BLOCK", None, ["pack_id and finding_id must be non-empty strings"]
    if type(include_adjacent) is not bool or type(include_parent) is not bool:
        return "BLOCK", None, ["context inclusion options must be boolean"]
    if any(type(value) is not int or value < 1 for value in (max_credentials, max_estimated_tokens)):
        return "BLOCK", None, ["pack budgets must be positive integers"]
    by_id = index_credentials(data)
    missing_targets = [identifier for identifier in target_ids if identifier not in by_id]
    if missing_targets:
        return "BLOCK", None, [f"missing target credential: {identifier}" for identifier in missing_targets]
    selected = select_pack_ids(by_id, target_ids, include_adjacent, include_parent)
    roots = source_roots(by_id, selected)
    source_gate, source_reasons = gate_sources(data, roots)
    if source_gate != "PASS":
        return "BLOCK", None, source_reasons
    unverified = [identifier for identifier in sorted(selected) if by_id[identifier].get("status") != "verified"]
    if unverified:
        return "BLOCK", None, [
            f"context credential {identifier} is {by_id[identifier].get('status')}" for identifier in unverified
        ]
    if len(selected) > max_credentials:
        return "BLOCK", None, [
            f"dependency closure has {len(selected)} credentials; limit is {max_credentials}; split the Finding"
        ]
    timestamp = now()
    source_records = [
        {
            "id": source_id,
            "locator": by_id[source_id]["locator"],
            "metadata": by_id[source_id]["metadata"],
            "content_hash": by_id[source_id]["content_hash"],
        }
        for source_id in sorted(roots)
    ]
    pack = {
        "schema_version": PACK_SCHEMA_VERSION,
        "pack_id": pack_id,
        "review_id": data["review_id"],
        "finding_id": finding_id,
        "generated_at": timestamp,
        "target_credential_ids": list(dict.fromkeys(target_ids)),
        "credential_ids": sorted(selected),
        "sources": source_records,
        "credentials": [project_credential(by_id[identifier]) for identifier in sorted(selected)],
        "selection": {
            "required_dependency_closure": True,
            "include_adjacent": include_adjacent,
            "include_parent": include_parent,
            "max_credentials": max_credentials,
            "max_estimated_tokens": max_estimated_tokens,
            "truncated": False,
        },
    }
    serialized = json.dumps(pack, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    pack["estimated_token_upper_bound"] = len(serialized.encode("utf-8")) + 512
    if pack["estimated_token_upper_bound"] > max_estimated_tokens:
        return "BLOCK", None, [
            f"estimated token upper bound is {pack['estimated_token_upper_bound']}; "
            f"limit is {max_estimated_tokens}; split the Finding"
        ]
    pack["pack_hash"] = pack_hash(pack)
    return "PASS", pack, []


def validate_pack(pack: dict[str, Any], store: dict[str, Any]) -> list[str]:
    errors = validate(store) + input_errors(pack)
    if errors:
        return errors
    try:
        return _validate_pack(pack, store)
    except (TypeError, AttributeError, KeyError, ValueError, RecursionError) as exc:
        return [f"invalid context pack structure: {exc}"]


def _validate_pack(pack, store):
    errors = []
    if pack.get("schema_version") != PACK_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PACK_SCHEMA_VERSION}")
    if pack.get("review_id") != store.get("review_id"):
        errors.append("pack review_id does not match store")
    for field in ("pack_id", "finding_id", "generated_at"):
        if not isinstance(pack.get(field), str) or not pack[field].strip():
            errors.append(f"{field} must be a non-empty string")
    if pack.get("pack_hash") != pack_hash(pack):
        errors.append("pack_hash does not match pack content")
    targets = pack.get("target_credential_ids")
    listed = pack.get("credential_ids")
    for name, values in (("target_credential_ids", targets), ("credential_ids", listed)):
        if not string_list(values) or not values or len(values) != len(set(values)):
            errors.append(f"{name} must be a non-empty unique array of strings")
    selection = pack.get("selection")
    if not isinstance(selection, dict):
        errors.append("selection must be an object")
        return errors
    if selection.get("required_dependency_closure") is not True or selection.get("truncated") is not False:
        errors.append("selection must preserve the complete required dependency closure")
    for field in ("include_adjacent", "include_parent"):
        if type(selection.get(field)) is not bool:
            errors.append(f"selection.{field} must be boolean")
    limit = selection.get("max_credentials")
    token_limit = selection.get("max_estimated_tokens", 20000)  # Legacy packs used the default budget.
    if any(type(value) is not int or value < 1 for value in (limit, token_limit)):
        errors.append("selection budgets must be positive integers")
    if errors:
        return errors
    by_id = index_credentials(store)
    if any(identifier not in by_id for identifier in targets + listed):
        return errors + ["pack references a credential missing from store"]
    expected = select_pack_ids(by_id, targets, selection["include_adjacent"], selection["include_parent"])
    if set(listed) != expected:
        errors.append("credential_ids do not match the complete selected dependency closure")
    if len(listed) > limit:
        errors.append("credential_ids exceed selection.max_credentials")
    rows = pack.get("credentials")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        return errors + ["credentials must be an array of objects"]
    row_ids = [row.get("id") for row in rows]
    if not string_list(row_ids) or sorted(row_ids) != sorted(listed):
        errors.append("credential_ids do not match credentials")
    for row in rows:
        current = by_id.get(row.get("id"))
        if current is None:
            errors.append("pack credential missing from store")
        elif row != project_credential(current):
            errors.append(f"pack credential {row.get('id')} content changed")
        elif current["status"] != "verified":
            errors.append(f"pack credential {row['id']} is now {current['status']}")
    roots = source_roots(by_id, expected)
    expected_sources = [{"id": root, "locator": by_id[root]["locator"], "metadata": by_id[root]["metadata"],
                         "content_hash": by_id[root]["content_hash"]} for root in sorted(roots)]
    if pack.get("sources") != expected_sources:
        errors.append("sources do not match current complete source projections")
    status, reasons = gate_sources(store, roots)
    if status != "PASS":
        errors.extend(reasons)
    estimate_payload = {key: value for key, value in pack.items() if key not in ("pack_hash", "estimated_token_upper_bound")}
    estimate = len(json.dumps(estimate_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")) + 512
    if type(pack.get("estimated_token_upper_bound")) is not int or pack["estimated_token_upper_bound"] != estimate:
        errors.append("estimated_token_upper_bound does not match content")
    if estimate > token_limit:
        errors.append("context pack exceeds max_estimated_tokens")
    return errors


def command_validate(args: argparse.Namespace) -> int:
    try:
        errors = validate(load(Path(args.path)))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"invalid evidence credential store: {exc}")
        return 2
    if errors:
        print("\n".join(errors))
        return 2
    print("evidence credential store valid")
    return 0


def command_summary(args: argparse.Namespace) -> int:
    data = load(Path(args.path))
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    credentials = data["credentials"]
    result = {
        "review_id": data["review_id"],
        "credentials": len(credentials),
        "kinds": {
            kind: sum(1 for item in credentials if item["kind"] == kind)
            for kind in sorted(KINDS) if any(item["kind"] == kind for item in credentials)
        },
        "states": {
            state: sum(1 for item in credentials if item["status"] == state)
            for state in sorted(STATES) if any(item["status"] == state for item in credentials)
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_gate(args: argparse.Namespace) -> int:
    data = load(Path(args.path))
    status, reasons = gate_sources(data, args.source_id)
    if status == "PASS":
        print("PASS: source coverage and required evidence credentials are verified")
        return 0
    print(f"{status}: " + "; ".join(reasons))
    return 1 if status == "REVIEW" else 2


def command_pack(args: argparse.Namespace) -> int:
    data = load(Path(args.path))
    status, pack, reasons = build_pack(
        data,
        pack_id=args.pack_id,
        finding_id=args.finding_id,
        target_ids=args.credential_id,
        include_adjacent=not args.no_adjacent,
        include_parent=not args.no_parent,
        max_credentials=args.max_credentials,
        max_estimated_tokens=args.max_estimated_tokens,
    )
    if status != "PASS" or pack is None:
        print(f"{status}: " + "; ".join(reasons))
        return 2
    output = Path(args.output)
    store_path = Path(args.path)
    if output.resolve() == store_path.resolve() or (output.exists() and store_path.exists() and output.samefile(store_path)):
        print("BLOCK: context pack output must differ from store")
        return 2
    if output.exists() and not args.force:
        print(f"refusing to overwrite existing file: {output}")
        return 2
    atomic_write(output, pack)
    print(
        f"PASS: wrote {output}; credentials={len(pack['credential_ids'])}; "
        f"estimated_token_upper_bound={pack['estimated_token_upper_bound']}"
    )
    return 0


def command_validate_pack(args: argparse.Namespace) -> int:
    try:
        store = load(Path(args.path))
        pack = load(Path(args.pack))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"invalid context pack input: {exc}")
        return 2
    errors = validate(store) + validate_pack(pack, store)
    if errors:
        print("\n".join(errors))
        return 2
    print("paper context pack valid and current")
    return 0


def command_validate_ledger(args: argparse.Namespace) -> int:
    try:
        store = load(Path(args.path))
        ledger = load(Path(args.ledger))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"invalid ledger context input: {exc}")
        return 2
    errors = validate(store)
    if ledger.get("review_id") != store.get("review_id"):
        errors.append("ledger review_id does not match evidence store")
    findings = ledger.get("findings")
    if not isinstance(findings, list) or any(not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip() for item in findings):
        print("BLOCK: ledger findings must be an array of objects with non-empty ids")
        return 2
    if len({item["id"] for item in findings}) != len(findings):
        errors.append("duplicate finding id in ledger")
    pack_dir = Path(args.pack_dir)
    if not pack_dir.is_dir():
        errors.append("context pack directory is missing")
    packs: dict[str, dict[str, Any]] = {}
    for path in pack_dir.glob("*.json"):
        try:
            pack = load(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid pack {path.name}: {exc}")
            continue
        pack_id = pack.get("pack_id")
        if isinstance(pack_id, str) and pack_id.strip():
            if pack_id in packs:
                errors.append(f"duplicate context pack id: {pack_id}")
            packs[pack_id] = pack
    missing_context: list[str] = []
    for finding in ledger.get("findings", []):
        if not isinstance(finding, dict) or not isinstance(finding.get("id"), str):
            continue
        pack_id = finding.get("context_pack_id")
        evidence_ids = finding.get("evidence_credential_ids")
        if (
            not isinstance(pack_id, str) or not pack_id.strip()
            or not string_list(evidence_ids) or not evidence_ids
        ):
            missing_context.append(finding["id"])
            continue
        pack = packs.get(pack_id)
        if pack is None:
            errors.append(f"finding {finding['id']} references missing context pack: {pack_id}")
            continue
        errors.extend(f"finding {finding['id']}: {error}" for error in validate_pack(pack, store))
        if pack.get("finding_id") != finding["id"]:
            errors.append(f"finding {finding['id']} does not match context pack finding_id")
        pack_ids = set(pack.get("credential_ids", [])) if string_list(pack.get("credential_ids")) else set()
        missing = [identifier for identifier in evidence_ids if identifier not in pack_ids]
        if missing:
            errors.append(
                f"finding {finding['id']} evidence credentials missing from pack: {', '.join(missing)}"
            )
    if errors:
        print("\n".join(errors))
        return 2
    if not findings:
        print("REVIEW: no findings recorded; context completeness is not established")
        return 1
    if missing_context:
        print(f"REVIEW: findings without evidence context: {', '.join(missing_context)}")
        return 1
    print("PASS: every finding has a current evidence credential context pack")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("path")
    init_parser.add_argument("--review-id", required=True)
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=command_init)

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("path")
    add_parser.add_argument("--id", required=True)
    add_parser.add_argument("--kind", choices=sorted(KINDS), required=True)
    add_parser.add_argument("--source-id")
    add_parser.add_argument("--parent-id")
    add_parser.add_argument("--previous-id")
    add_parser.add_argument("--next-id")
    add_parser.add_argument("--required-dependency", action="append", default=[])
    add_parser.add_argument("--optional-dependency", action="append", default=[])
    add_parser.add_argument("--status", choices=sorted(STATES), default="discovered")
    add_parser.add_argument("--pointer", required=True)
    add_parser.add_argument("--page", type=int)
    add_parser.add_argument("--bbox")
    add_parser.add_argument("--text")
    add_parser.add_argument("--text-file")
    add_parser.add_argument("--metadata-file")
    add_parser.add_argument("--source-file")
    add_parser.add_argument("--reason", default="evidence credential added")
    add_parser.set_defaults(func=command_add)

    link_parser = subparsers.add_parser("link")
    link_parser.add_argument("path")
    link_parser.add_argument("--id", required=True)
    link_parser.add_argument("--required-dependency", action="append", default=[])
    link_parser.add_argument("--optional-dependency", action="append", default=[])
    link_parser.add_argument("--parent-id")
    link_parser.add_argument("--previous-id")
    link_parser.add_argument("--next-id")
    link_parser.add_argument("--reason", default="evidence dependencies linked")
    link_parser.set_defaults(func=command_link)

    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("path")
    import_parser.add_argument("--input", required=True)
    import_parser.add_argument("--reason", default="batch evidence credentials imported")
    import_parser.set_defaults(func=command_import)

    status_parser = subparsers.add_parser("set-status")
    status_parser.add_argument("path")
    status_parser.add_argument("--id", required=True)
    status_parser.add_argument("--status", choices=sorted(STATES), required=True)
    status_parser.add_argument("--reason", default="evidence status changed")
    status_parser.add_argument("--propagate", action=argparse.BooleanOptionalAction, default=True)
    status_parser.set_defaults(func=command_set_status)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("path")
    validate_parser.set_defaults(func=command_validate)

    summary_parser = subparsers.add_parser("summary")
    summary_parser.add_argument("path")
    summary_parser.set_defaults(func=command_summary)

    gate_parser = subparsers.add_parser("gate")
    gate_parser.add_argument("path")
    gate_parser.add_argument("--source-id", action="append")
    gate_parser.set_defaults(func=command_gate)

    pack_parser = subparsers.add_parser("pack")
    pack_parser.add_argument("path")
    pack_parser.add_argument("--pack-id", required=True)
    pack_parser.add_argument("--finding-id", required=True)
    pack_parser.add_argument("--credential-id", action="append", required=True)
    pack_parser.add_argument("--output", required=True)
    pack_parser.add_argument("--max-credentials", type=int, default=40)
    pack_parser.add_argument("--max-estimated-tokens", type=int, default=20000)
    pack_parser.add_argument("--no-adjacent", action="store_true")
    pack_parser.add_argument("--no-parent", action="store_true")
    pack_parser.add_argument("--force", action="store_true")
    pack_parser.set_defaults(func=command_pack)

    pack_validate_parser = subparsers.add_parser("validate-pack")
    pack_validate_parser.add_argument("path")
    pack_validate_parser.add_argument("--pack", required=True)
    pack_validate_parser.set_defaults(func=command_validate_pack)

    ledger_parser = subparsers.add_parser("validate-ledger")
    ledger_parser.add_argument("path")
    ledger_parser.add_argument("--ledger", required=True)
    ledger_parser.add_argument("--pack-dir", required=True)
    ledger_parser.set_defaults(func=command_validate_ledger)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        print(f"BLOCK: invalid input: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
