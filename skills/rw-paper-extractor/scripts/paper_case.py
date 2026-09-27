#!/usr/bin/env python3
"""Build and validate an experimental RW Paper Case from one user-provided PDF."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from io import BytesIO
from pathlib import Path
from typing import Any

import fitz
from PIL import Image


SCHEMA = "rw-paper-case/v0-experimental"
CONFIG = {
    "text_backend": "pymupdf-layout-profile-v2",
    "visual_backend": "pymupdf-rendered-regions-v2",
    "heading_rules_version": "2026-07-23.2",
    "table_stitch_version": "2026-07-23.1",
    "min_visual_area_ratio": 0.012,
    "max_visual_area_ratio": 0.82,
    "render_scale": 2.0,
    "heading_size_delta": 1.0,
    "heading_bold_ratio": 0.6,
    "table_bottom_ratio": 0.84,
    "continuation_top_ratio": 0.34,
    "continuation_min_rows": 2,
}
STAGES = (
    "source_fixed",
    "content_located",
    "research_structure",
    "visual_evidence",
    "claim_candidates",
    "report_assembled",
    "claim_gate",
)
REPORT_STAGES = (
    ("01-question.md", "研究问题与论文身份", "只记录题名、稳定标识、研究问题、研究设计和对应 locator。"),
    ("02-methods.md", "方法", "记录样本、分组、干预或暴露、测量、分析方法及对应 locator。"),
    ("03-results-and-visuals.md", "结果与视觉证据", "分开记录主要、次要和安全结果；审核每个图表候选。"),
    ("04-limits.md", "限制与适用边界", "区分作者报告的限制、当前推断和不能外推的人群。"),
    ("05-conclusion.md", "结论", "只汇总前四阶段已有证据，不增加新事实。"),
)
AUDIT_VERDICTS = {"VERIFIED", "PARTIAL", "DISTORTED", "UNSUPPORTED", "UNVERIFIABLE_ACCESS", "NOT_CHECKED", "NOT_APPLICABLE"}
ARTIFACTS = {
    "text_units": "evidence/text-units.jsonl",
    "section_map": "evidence/section-map.json",
    "visual_evidence": "evidence/visual-evidence.jsonl",
    "claim_candidates": "evidence/claim-candidates.jsonl",
    "report": "report.md",
    "claim_audit": "audit/claim-audit.json",
    "litnet_preview": "litnet-writeback-preview.json",
}
EXTRACTION_KEYS = ("text_units", "section_map", "visual_evidence")


def strict_json(text):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError(f"non-finite JSON constant: {value}")
    value = json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
    json.dumps(value, allow_nan=False)
    return value


def case_path(root: Path, relative: str) -> Path:
    """Manifest paths are data, never authority to read/write outside a case."""
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("artifact path must be relative and stay inside the Paper Case")
    path = root / relative
    cursor = path
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError("Paper Case artifact paths must not contain symlinks")
        cursor = cursor.parent
    path.resolve().relative_to(root.resolve())
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def paper_id(doi: str, source_hash: str, zotero_library_id: int | None, zotero_key: str) -> str:
    if zotero_library_id is not None and zotero_key:
        return f"zotero-{zotero_library_id}-{zotero_key}"
    if doi:
        safe_doi = re.sub(r"[^a-z0-9._-]+", "-", doi.casefold()).strip("-")
        return f"doi-{safe_doi}"
    return f"sha256-{source_hash[:16]}"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temp = Path(handle.name)
        try:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


SECTION_TERMS = {
    "abstract",
    "background",
    "objective",
    "objectives",
    "aim",
    "aims",
    "introduction",
    "method",
    "methods",
    "materials and methods",
    "patients and methods",
    "results",
    "findings",
    "discussion",
    "conclusion",
    "conclusions",
    "limitations",
    "references",
    "acknowledgments",
    "acknowledgements",
    "funding",
    "conflicts of interest",
    "data availability",
}
STRUCTURE_START_TERMS = {"abstract", "background", "introduction", "method", "methods", "materials and methods", "patients and methods", "results"}
METADATA_PREFIX = re.compile(
    r"^(publication date|published|received|accepted|doi|pmid|keywords?|key words)(?:\s*[:：])?(?:\s|$)",
    re.I,
)
CAPTION_PREFIX = re.compile(r"^(table|fig(?:ure)?\.?)\s*(?:s?\d+|[ivxlcdm]+)\b", re.I)


def body_font_size(document: fitz.Document) -> float:
    counts: Counter[float] = Counter()
    for page in document:
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = normalized(str(span.get("text", "")))
                    size = round(float(span.get("size", 0.0)), 1)
                    if text and 7.0 <= size <= 16.0:
                        counts[size] += len(text)
    return counts.most_common(1)[0][0] if counts else 11.0


def block_profile(block: dict[str, Any]) -> tuple[str, float, float]:
    spans = [span for line in block.get("lines", []) for span in line.get("spans", [])]
    text = normalized(" ".join(str(span.get("text", "")) for span in spans))
    visible = [(span, len(normalized(str(span.get("text", ""))))) for span in spans]
    total_chars = sum(length for _, length in visible) or 1
    bold_chars = sum(
        length
        for span, length in visible
        if "bold" in str(span.get("font", "")).lower() or int(span.get("flags", 0)) & 16
    )
    max_size = max((float(span.get("size", 0.0)) for span in spans), default=0.0)
    return text, max_size, bold_chars / total_chars


def heading_profile(text: str, max_size: float, bold_ratio: float, body_size: float) -> dict[str, Any] | None:
    line = normalized(text)
    if not line or len(line) > 110:
        return None
    if METADATA_PREFIX.match(line) or CAPTION_PREFIX.match(line):
        return None
    canonical = re.sub(r"[:：]$", "", line).strip().casefold()
    if canonical in SECTION_TERMS:
        return {"basis": "section_term", "confidence": 0.99, "term": canonical}
    if re.search(r"[.!?;。！？；]$", line) or re.search(r"\b\d+\s*/\s*\d+\b", line):
        return None
    typographic = max_size >= body_size + CONFIG["heading_size_delta"] and bold_ratio >= CONFIG["heading_bold_ratio"]
    numbered = bool(re.match(r"^\d+(?:\.\d+)*(?:[.)])?\s+\S", line))
    word_count = len(line.split())
    if typographic and word_count <= 14:
        return {
            "basis": "numbered_typography" if numbered else "typography",
            "confidence": 0.96 if numbered else 0.9,
        }
    return None


def extract_text_units(document: fitz.Document) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    units: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    body_size = body_font_size(document)
    structure_started = False
    for page_index, page in enumerate(document, start=1):
        blocks = page.get_text("dict", sort=True).get("blocks", [])
        text_index = 0
        for block in blocks:
            if int(block.get("type", 0)) != 0:
                continue
            text, max_size, bold_ratio = block_profile(block)
            if not text:
                continue
            text_index += 1
            unit_id = f"p{page_index:03d}-t{text_index:03d}"
            bbox = [round(float(value), 2) for value in block.get("bbox", (0, 0, 0, 0))]
            heading = heading_profile(text, max_size, bold_ratio, body_size)
            if heading and heading.get("term") in STRUCTURE_START_TERMS:
                structure_started = True
            if heading and heading["basis"] != "section_term" and not structure_started:
                heading = None
            if CAPTION_PREFIX.match(text):
                kind = "caption"
            else:
                kind = "heading" if heading else "paragraph"
            row = {
                "id": unit_id,
                "kind": kind,
                "page": page_index,
                "bbox": bbox,
                "text": text,
                "locator": f"p. {page_index}, text unit {unit_id}",
            }
            if heading:
                row["heading_basis"] = heading["basis"]
                row["heading_confidence"] = heading["confidence"]
            units.append(row)
            if kind == "heading":
                sections.append(
                    {
                        "text_unit_id": unit_id,
                        "page": page_index,
                        "heading": text,
                        "basis": heading["basis"],
                        "confidence": heading["confidence"],
                    }
                )
    return units, sections


def bbox_iou(first: fitz.Rect, second: fitz.Rect) -> float:
    overlap = first & second
    if overlap.is_empty:
        return 0.0
    union = first.get_area() + second.get_area() - overlap.get_area()
    return overlap.get_area() / union if union else 0.0


def caption_for(page: fitz.Page, target: fitz.Rect) -> str:
    candidates: list[tuple[float, str]] = []
    for block in page.get_text("blocks", sort=True):
        if len(block) < 7 or int(block[6]) != 0:
            continue
        text = normalized(str(block[4]))
        if not re.match(r"^(fig(?:ure)?\.?|table)\s*\d+", text, re.I):
            continue
        rect = fitz.Rect(block[:4])
        vertical = min(abs(rect.y0 - target.y1), abs(target.y0 - rect.y1))
        horizontal_overlap = max(0.0, min(rect.x1, target.x1) - max(rect.x0, target.x0))
        if vertical <= 90 and horizontal_overlap > 0:
            candidates.append((vertical, text))
    return min(candidates, default=(0.0, ""), key=lambda item: item[0])[1]


def visual_candidates(page: fitz.Page) -> list[tuple[str, fitz.Rect, str]]:
    candidates: list[tuple[str, fitz.Rect, str]] = []
    page_area = page.rect.get_area() or 1.0

    try:
        tables = page.find_tables()
    except Exception:
        tables = []
    for table in tables:
        rect = fitz.Rect(table.bbox)
        ratio = rect.get_area() / page_area
        if CONFIG["min_visual_area_ratio"] <= ratio <= CONFIG["max_visual_area_ratio"]:
            candidates.append(("table", rect, caption_for(page, rect)))

    try:
        images = page.get_image_info(xrefs=True)
    except Exception:
        images = []
    for info in images:
        rect = fitz.Rect(info.get("bbox", (0, 0, 0, 0)))
        ratio = rect.get_area() / page_area
        if rect.width < 70 or rect.height < 55:
            continue
        if not CONFIG["min_visual_area_ratio"] <= ratio <= CONFIG["max_visual_area_ratio"]:
            continue
        if any(bbox_iou(rect, existing[1]) >= 0.8 for existing in candidates):
            continue
        candidates.append(("figure", rect, caption_for(page, rect)))
    return candidates


def horizontal_overlap_ratio(first: fitz.Rect, second: fitz.Rect) -> float:
    overlap = max(0.0, min(first.x1, second.x1) - max(first.x0, second.x0))
    return overlap / min(first.width, second.width) if min(first.width, second.width) else 0.0


def continuation_bbox_from_words(page: fitz.Page, previous: fitz.Rect, col_count: int) -> fitz.Rect | None:
    groups: dict[int, list[tuple[Any, ...]]] = defaultdict(list)
    for word in page.get_text("words", sort=True):
        if len(word) >= 8:
            groups[int(word[5])].append(word)

    candidates: list[fitz.Rect] = []
    required_columns = max(3, min(5, col_count - 1))
    for words in groups.values():
        rect = fitz.Rect(
            min(float(word[0]) for word in words),
            min(float(word[1]) for word in words),
            max(float(word[2]) for word in words),
            max(float(word[3]) for word in words),
        )
        if rect.y0 > page.rect.height * CONFIG["continuation_top_ratio"]:
            continue
        if horizontal_overlap_ratio(rect, previous) < 0.72:
            continue
        columns = len({int(word[6]) for word in words})
        numeric_tokens = sum(bool(re.search(r"\d", str(word[4]))) for word in words)
        if columns >= required_columns and numeric_tokens >= required_columns - 1:
            candidates.append(rect)

    candidates.sort(key=lambda rect: rect.y0)
    if len(candidates) < CONFIG["continuation_min_rows"]:
        return None
    if candidates[0].y0 > page.rect.height * 0.22:
        return None

    run = [candidates[0]]
    for rect in candidates[1:]:
        if rect.y0 - run[-1].y1 > 58:
            break
        run.append(rect)
    if len(run) < CONFIG["continuation_min_rows"]:
        return None
    return fitz.Rect(previous.x0, max(0.0, run[0].y0 - 4), previous.x1, min(page.rect.y1, run[-1].y1 + 4))


def page_tables(page: fitz.Page) -> list[dict[str, Any]]:
    try:
        finder = page.find_tables()
        tables = list(finder.tables)
    except Exception:
        tables = []
    rows = []
    page_area = page.rect.get_area() or 1.0
    for table in tables:
        rect = fitz.Rect(table.bbox)
        ratio = rect.get_area() / page_area
        if CONFIG["min_visual_area_ratio"] <= ratio <= CONFIG["max_visual_area_ratio"]:
            rows.append({"rect": rect, "caption": caption_for(page, rect), "col_count": int(table.col_count)})
    return rows


def collect_table_visuals(document: fitz.Document) -> tuple[list[dict[str, Any]], set[tuple[int, int]]]:
    tables_by_page = [page_tables(page) for page in document]
    consumed: set[tuple[int, int]] = set()
    visuals: list[dict[str, Any]] = []
    for page_zero, tables in enumerate(tables_by_page):
        for table_index, table in enumerate(tables):
            if (page_zero, table_index) in consumed:
                continue
            segments = [{"page": page_zero + 1, "rect": table["rect"]}]
            current_page = page_zero
            current_rect = table["rect"]
            col_count = table["col_count"]
            while current_page + 1 < len(document):
                if current_rect.y1 < document[current_page].rect.height * CONFIG["table_bottom_ratio"]:
                    break
                next_page = current_page + 1
                match_index = None
                for candidate_index, candidate in enumerate(tables_by_page[next_page]):
                    if (next_page, candidate_index) in consumed:
                        continue
                    if candidate["rect"].y0 <= document[next_page].rect.height * 0.22 and horizontal_overlap_ratio(current_rect, candidate["rect"]) >= 0.72:
                        match_index = candidate_index
                        break
                if match_index is not None:
                    candidate = tables_by_page[next_page][match_index]
                    consumed.add((next_page, match_index))
                    current_rect = candidate["rect"]
                    col_count = candidate["col_count"]
                else:
                    continuation = continuation_bbox_from_words(document[next_page], current_rect, col_count)
                    if continuation is None:
                        break
                    current_rect = continuation
                segments.append({"page": next_page + 1, "rect": current_rect})
                current_page = next_page
            visuals.append({"kind": "table", "caption": table["caption"], "segments": segments})
    return visuals, consumed


def render_segments(document: fitz.Document, segments: list[dict[str, Any]], image_path: Path) -> None:
    rendered: list[Image.Image] = []
    matrix = fitz.Matrix(CONFIG["render_scale"], CONFIG["render_scale"])
    for segment in segments:
        pixmap = document[int(segment["page"]) - 1].get_pixmap(matrix=matrix, clip=segment["rect"], alpha=False)
        with Image.open(BytesIO(pixmap.tobytes("png"))) as image:
            rendered.append(image.convert("RGB").copy())
    if len(rendered) == 1:
        rendered[0].save(image_path)
        return
    seam = 8
    width = max(image.width for image in rendered)
    height = sum(image.height for image in rendered) + seam * (len(rendered) - 1)
    stitched = Image.new("RGB", (width, height), "white")
    y = 0
    for index, image in enumerate(rendered):
        stitched.paste(image, (0, y))
        y += image.height
        if index < len(rendered) - 1:
            stitched.paste((176, 176, 176), (0, y, width, y + seam))
            y += seam
    stitched.save(image_path)


def extract_visual_evidence(document: fitz.Document, output_dir: Path) -> list[dict[str, Any]]:
    visuals_dir = output_dir / "visuals"
    visuals_dir.mkdir(parents=True, exist_ok=True)
    table_visuals, _ = collect_table_visuals(document)
    candidates = list(table_visuals)
    table_segments = [segment for visual in table_visuals for segment in visual["segments"]]
    for page_index, page in enumerate(document, start=1):
        for kind, rect, caption in visual_candidates(page):
            if kind == "table":
                continue
            if any(segment["page"] == page_index and bbox_iou(segment["rect"], rect) >= 0.8 for segment in table_segments):
                continue
            candidates.append({"kind": kind, "caption": caption, "segments": [{"page": page_index, "rect": rect}]})
    candidates.sort(key=lambda item: (item["segments"][0]["page"], item["segments"][0]["rect"].y0))

    rows: list[dict[str, Any]] = []
    counters: Counter[int] = Counter()
    for candidate in candidates:
        segments = candidate["segments"]
        first_page = int(segments[0]["page"])
        counters[first_page] += 1
        visual_id = f"p{first_page:03d}-v{counters[first_page]:02d}"
        page_suffix = f"-p{int(segments[-1]['page']):03d}" if len(segments) > 1 else ""
        image_path = visuals_dir / f"{visual_id}{page_suffix}-{candidate['kind']}.png"
        render_segments(document, segments, image_path)
        segment_rows = []
        locators = []
        for segment in segments:
            rect = segment["rect"]
            page_number = int(segment["page"])
            bbox = [round(value, 2) for value in (rect.x0, rect.y0, rect.x1, rect.y1)]
            locator = f"p. {page_number}, bbox {rect.x0:.1f},{rect.y0:.1f},{rect.x1:.1f},{rect.y1:.1f}"
            segment_rows.append({"page": page_number, "bbox": bbox, "locator": locator})
            locators.append(locator)
        first = segment_rows[0]
        rows.append(
            {
                "id": visual_id,
                "kind": candidate["kind"],
                "page": first["page"],
                "pages": [segment["page"] for segment in segment_rows],
                "bbox": first["bbox"],
                "segments": segment_rows,
                "caption": candidate["caption"],
                "image": image_path.relative_to(output_dir).as_posix(),
                "image_sha256": sha256_file(image_path),
                "locator": "; ".join(locators),
                "cross_page": len(segment_rows) > 1,
                "review_status": "needs_human_review",
            }
        )
    return rows


def build_case(args: argparse.Namespace) -> int:
    pdf = args.pdf.expanduser().resolve()
    destination = args.output.expanduser().absolute()
    if destination.is_symlink():
        raise ValueError("output must not be a symlink")
    destination = destination.resolve()
    if not pdf.is_file():
        raise FileNotFoundError(pdf)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("output must be a new or empty directory; preserve the existing Paper Case")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".paper-case-", dir=destination.parent) as temp:
        output = Path(temp) / "case"
        output.mkdir()
        result = _build_case(args, pdf, output)
        # A concurrent writer must not be replaced after the initial preflight.
        if destination.exists() and any(destination.iterdir()):
            raise ValueError("output became non-empty during build")
        os.replace(output, destination)
    return result


def _build_case(args: argparse.Namespace, pdf: Path, output: Path) -> int:

    source_hash = sha256_file(pdf)
    config_hash = json_hash(CONFIG)
    with fitz.open(pdf) as document:
        if not document.is_pdf or document.needs_pass or document.page_count < 1:
            raise ValueError("source must be a readable, unencrypted PDF with pages")
        text_units, sections = extract_text_units(document)
        visuals = extract_visual_evidence(document, output)
        page_count = document.page_count
    if sha256_file(pdf) != source_hash:
        raise ValueError("source PDF changed during extraction")

    source_manifest: dict[str, Any] = {
        "schema": "rw-paper-source/v0-experimental",
        "pdf_path": str(pdf),
        "pdf_sha256": source_hash,
        "pages": page_count,
        "title": args.title,
        "doi": args.doi,
        "access": "user-provided-file",
    }
    if args.zotero_library_id is not None or args.zotero_key or args.zotero_attachment_key:
        source_manifest["optional_zotero"] = {
            "library_id": args.zotero_library_id,
            "item_key": args.zotero_key,
            "attachment_key": args.zotero_attachment_key,
        }
    case = {
        "schema": SCHEMA,
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "paper_id": paper_id(args.doi, source_hash, args.zotero_library_id, args.zotero_key),
        "source_hash": source_hash,
        "config_hash": config_hash,
        "source_manifest": "source-manifest.json",
        "artifacts": dict(ARTIFACTS),
        "counts": {"text_units": len(text_units), "sections": len(sections), "visuals": len(visuals)},
        "privacy": {"external_model_called": False, "pdf_copied": False},
    }
    stage_state = {
        "schema": "rw-paper-stage-state/v0-experimental",
        "source_hash": source_hash,
        "config_hash": config_hash,
        "stages": {
            stage: {
                "status": "complete" if stage in {"source_fixed", "content_located", "visual_evidence"} else "pending",
                "source_hash": source_hash,
                "config_hash": config_hash,
            }
            for stage in STAGES
        },
    }

    write_json(output / "source-manifest.json", source_manifest)
    write_json(output / "case.json", case)
    write_json(output / "stage-state.json", stage_state)
    write_json(output / "evidence" / "section-map.json", {"sections": sections})
    write_jsonl(output / "evidence" / "text-units.jsonl", text_units)
    write_jsonl(output / "evidence" / "visual-evidence.jsonl", visuals)
    write_jsonl(output / "evidence" / "claim-candidates.jsonl", [])
    case["extraction_hashes"] = {key: sha256_file(output / ARTIFACTS[key]) for key in EXTRACTION_KEYS}
    write_json(output / "case.json", case)
    (output / "audit").mkdir(exist_ok=True)
    print(json.dumps(case["counts"], ensure_ascii=False))
    return 0


def scaffold_command(args: argparse.Namespace) -> int:
    output = args.output.expanduser().resolve()
    problems = validate_case(output)
    if problems:
        raise ValueError("cannot scaffold an invalid or stale case: " + "; ".join(problems))
    case = strict_json((output / "case.json").read_text(encoding="utf-8"))
    source = strict_json((output / "source-manifest.json").read_text(encoding="utf-8"))
    stages_dir = case_path(output, "stages")
    # Validate the full write set before replacing even the first stage.
    destinations = [case_path(output, f"stages/{filename}") for filename, _, _ in REPORT_STAGES]
    destinations.append(case_path(output, "report.md"))
    if any(path.exists() and not path.is_file() for path in destinations):
        raise ValueError("scaffold destinations must be regular files or absent")
    stages_dir.mkdir(exist_ok=True)
    created: list[str] = []
    for filename, heading, instruction in REPORT_STAGES:
        path = case_path(output, f"stages/{filename}")
        if path.exists() and not args.force:
            continue
        path.write_text(
            f"# {heading}\n\n"
            f"论文：{source.get('title', '')}\n\n"
            f"Paper Case：`{case['paper_id']}`\n\n"
            f"来源 hash：`{case['source_hash']}`\n\n"
            f"## 写作约束\n\n{instruction}\n\n"
            "## 内容\n\n［待填写］\n\n"
            "## 证据定位\n\n［填写 text unit、page、table、figure 或 supplement locator］\n",
            encoding="utf-8",
        )
        created.append(path.relative_to(output).as_posix())
    report = case_path(output, "report.md")
    if not report.exists() or args.force:
        sections = "\n".join(
            f"## {index}．{heading}\n\n见 `stages/{filename}`。\n"
            for index, (filename, heading, _) in enumerate(REPORT_STAGES, start=1)
        )
        report.write_text(
            f"# {source.get('title', '')}｜分阶段精读报告\n\n"
            "> 状态：草稿。阶段文件完成并通过 Claim Audit 前，不进入已验证结论。\n\n"
            + sections,
            encoding="utf-8",
        )
        created.append("report.md")
    print(json.dumps({"paper_id": case["paper_id"], "created": created}, ensure_ascii=False))
    return 0


def mark_stage_command(args: argparse.Namespace) -> int:
    output = args.output.expanduser().resolve()
    problems = validate_case(output, include_stages=False)
    if problems:
        raise ValueError("cannot mark an invalid or stale case: " + "; ".join(problems))
    artifact = case_path(output, args.artifact)
    try:
        artifact_relative = artifact.relative_to(output)
    except ValueError as exc:
        raise ValueError("stage artifact must stay inside the Paper Case") from exc
    if not artifact.is_file():
        raise FileNotFoundError(artifact)
    state_path = case_path(output, "stage-state.json")
    if artifact == state_path:
        raise ValueError("stage artifact cannot be stage-state.json itself")
    state = strict_json(state_path.read_text(encoding="utf-8"))
    upstream_artifacts = []
    for value in args.upstream:
        path = case_path(output, value)
        if path == state_path:
            raise ValueError("stage-state.json cannot be its own upstream")
        try:
            relative = path.relative_to(output)
        except ValueError as exc:
            raise ValueError("upstream artifact must stay inside the Paper Case") from exc
        if not path.is_file():
            raise FileNotFoundError(path)
        upstream_artifacts.append({"path": relative.as_posix(), "sha256": sha256_file(path)})
    if args.stage == "report_assembled":
        required = {f"stages/{filename}" for filename, _, _ in REPORT_STAGES}
        if artifact_relative.as_posix() != ARTIFACTS["report"] or not required.issubset({row["path"] for row in upstream_artifacts}):
            raise ValueError("report_assembled requires report.md and all five stage files as upstream artifacts")
    if args.stage == "claim_gate":
        audit = strict_json(artifact.read_text(encoding="utf-8"))
        errors = validate_claim_audit(audit)
        if errors:
            raise ValueError("invalid claim audit: " + "; ".join(errors))
        _audit_report_binding(output, audit, artifact)
        expected = claim_gate(audit)[0].lower()
        if args.status != expected:
            raise ValueError(f"claim_gate status must be {expected}")
    state["stages"][args.stage] = {
        "status": args.status,
        "source_hash": state["source_hash"],
        "config_hash": state["config_hash"],
        "artifact": artifact_relative.as_posix(),
        "artifact_sha256": sha256_file(artifact),
        "upstream_artifacts": upstream_artifacts,
    }
    write_json(state_path, state)
    print(json.dumps({"stage": args.stage, "status": args.status, "artifact": artifact_relative.as_posix()}, ensure_ascii=False))
    return 0


def claim_gate(audit: dict[str, Any]) -> tuple[str, dict[str, int]]:
    if validate_claim_audit(audit):
        return "BLOCK", {}
    blocking = {"DISTORTED", "UNSUPPORTED"}
    review = {"PARTIAL", "UNVERIFIABLE_ACCESS", "NOT_CHECKED"}
    counts: Counter[str] = Counter(str(claim.get("verdict", "NOT_CHECKED")) for claim in audit.get("claims", []))
    verdicts = set(counts)
    if verdicts & blocking:
        return "BLOCK", dict(sorted(counts.items()))
    if not audit.get("claims") or verdicts & review or "VERIFIED" not in verdicts:
        return "REVIEW", dict(sorted(counts.items()))
    for claim in audit["claims"]:
        if claim["verdict"] in {"VERIFIED", "PARTIAL", "DISTORTED"}:
            if any(not ref.get("source_path") or not isinstance(ref.get("source_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", ref["source_sha256"]) for ref in claim["source_refs"]):
                return "REVIEW", dict(sorted(counts.items()))
    return "PASS", dict(sorted(counts.items()))


def validate_claim_audit(audit: dict[str, Any]) -> list[str]:
    """Mirror the rw-claim-audit/v1 structural contract without a Skill dependency.

    Live document/source hashes are checked separately by _audit_report_binding.
    Keep this boundary fail-closed: a malformed upstream audit is never certified
    as an audited Paper Case merely because its verdict string says VERIFIED.
    """
    problems: list[str] = []
    if not isinstance(audit, dict):
        return ["claim audit must be an object"]
    try:
        json.dumps(audit, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        return [f"claim audit contains invalid JSON data: {exc}"]
    required = ("schema_version", "document_id", "document_path", "document_hash", "audited_at", "claims")
    for field in required:
        if field not in audit:
            problems.append(f"claim audit missing top-level field: {field}")
    if problems:
        return problems
    if audit["schema_version"] != "rw-claim-audit/v1":
        problems.append("claim audit schema must be rw-claim-audit/v1")
    for field in ("document_id", "document_path", "document_hash", "audited_at"):
        if not isinstance(audit[field], str) or not audit[field].strip():
            problems.append(f"claim audit {field} must be a non-empty string")
    if not isinstance(audit["document_hash"], str) or not re.fullmatch(r"[0-9a-f]{64}", audit["document_hash"]):
        problems.append("claim audit document_hash must be a lowercase SHA-256 digest")
    claims = audit["claims"]
    if not isinstance(claims, list):
        return problems + ["claim audit claims must be an array"]
    claim_types = ("quantitative", "categorical", "trend", "comparative", "causal", "method", "interpretive", "other")
    ids: set[str] = set()
    for index, claim in enumerate(claims):
        prefix = f"claim {index}"
        if not isinstance(claim, dict):
            problems.append(f"{prefix} must be an object")
            continue
        for field in ("id", "text", "location", "claim_type", "source_refs", "verdict", "notes"):
            if field not in claim:
                problems.append(f"{prefix} missing field: {field}")
        for field in ("id", "text", "location"):
            if not isinstance(claim.get(field), str) or not claim[field].strip():
                problems.append(f"{prefix} requires non-empty {field}")
        claim_id = claim.get("id")
        if isinstance(claim_id, str):
            if claim_id in ids:
                problems.append(f"duplicate claim id: {claim_id}")
            ids.add(claim_id)
        if not isinstance(claim.get("claim_type"), str) or claim["claim_type"] not in claim_types:
            problems.append(f"{prefix} has an invalid claim_type")
        if not isinstance(claim.get("notes"), str):
            problems.append(f"{prefix} notes must be a string")
        verdict = claim.get("verdict")
        if not isinstance(verdict, str) or verdict not in AUDIT_VERDICTS:
            problems.append(f"{prefix} has an invalid verdict")
        if verdict == "NOT_APPLICABLE" and (not isinstance(claim.get("notes"), str) or not claim["notes"].strip()):
            problems.append(f"{prefix} NOT_APPLICABLE requires notes")
        refs = claim.get("source_refs")
        if not isinstance(refs, list):
            problems.append(f"{prefix} source_refs must be an array")
            continue
        if verdict in ("VERIFIED", "PARTIAL", "DISTORTED", "UNVERIFIABLE_ACCESS") and not refs:
            problems.append(f"{prefix} verdict {verdict} requires source_refs")
        ref_ids: set[str] = set()
        for ref_index, ref in enumerate(refs):
            ref_prefix = f"{prefix} source_ref {ref_index}"
            if not isinstance(ref, dict):
                problems.append(f"{ref_prefix} must be an object")
                continue
            for field in ("id", "source_pointer", "locator", "support_note"):
                if not isinstance(ref.get(field), str) or not ref[field].strip():
                    problems.append(f"{ref_prefix} requires non-empty {field}")
            ref_id = ref.get("id")
            if isinstance(ref_id, str):
                if ref_id in ref_ids:
                    problems.append(f"{prefix} contains duplicate source_ref id: {ref_id}")
                ref_ids.add(ref_id)
            if "source_path" in ref or "source_sha256" in ref:
                if not isinstance(ref.get("source_path"), str) or not ref["source_path"].strip():
                    problems.append(f"{ref_prefix} source_path must be a non-empty string")
                if not isinstance(ref.get("source_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", ref["source_sha256"]):
                    problems.append(f"{ref_prefix} source_sha256 must be a lowercase SHA-256 digest")
    return problems

def _audit_report_binding(output: Path, audit: dict[str, Any], audit_path: Path) -> Path:
    if audit_path.resolve() == case_path(output, ARTIFACTS["litnet_preview"]).resolve():
        raise ValueError("claim audit path must differ from preview output")
    document = Path(str(audit.get("document_path", "")))
    if not document.is_absolute():
        document = audit_path.parent / document
    report = case_path(output, ARTIFACTS["report"])
    if document.resolve() != report.resolve():
        raise ValueError("claim audit must bind to this Paper Case report.md")
    if not document.is_file() or sha256_file(document) != audit.get("document_hash"):
        raise ValueError("claim audit document is missing or changed")
    for claim in audit.get("claims", []):
        for ref in claim.get("source_refs", []):
            if "source_path" not in ref and "source_sha256" not in ref:
                continue
            if not isinstance(ref.get("source_path"), str) or not ref["source_path"].strip() or not isinstance(ref.get("source_sha256"), str) or not re.fullmatch(r"[0-9a-fA-F]{64}", ref["source_sha256"]):
                raise ValueError("claim source snapshot requires path and SHA256")
            snapshot = Path(ref["source_path"])
            if not snapshot.is_absolute():
                snapshot = audit_path.parent / snapshot
            preview = case_path(output, ARTIFACTS["litnet_preview"])
            if snapshot.resolve() == preview.resolve() or (snapshot.exists() and preview.exists() and snapshot.samefile(preview)):
                raise ValueError("claim source snapshot must differ from preview output")
            if not snapshot.is_file() or sha256_file(snapshot) != ref["source_sha256"]:
                raise ValueError("claim source snapshot is missing or changed")
    return report


def litnet_preview_command(args: argparse.Namespace) -> int:
    output = args.output.expanduser().resolve()
    problems = validate_case(output)
    if problems:
        raise ValueError("cannot preview an invalid or stale case: " + "; ".join(problems))
    audit_path = args.claim_audit.expanduser().resolve()
    if not audit_path.is_file():
        raise FileNotFoundError(audit_path)
    audit = strict_json(audit_path.read_text(encoding="utf-8"))
    if not isinstance(audit, dict) or audit.get("schema_version") != "rw-claim-audit/v1":
        raise ValueError("claim audit schema must be rw-claim-audit/v1")
    audit_problems = validate_claim_audit(audit)
    if audit_problems:
        raise ValueError("invalid claim audit: " + "; ".join(audit_problems))
    _audit_report_binding(output, audit, audit_path)
    gate, verdicts = claim_gate(audit)
    if gate == "BLOCK":
        raise ValueError("BLOCK claim audit cannot enter a LitNet preview")
    state = strict_json(case_path(output, "stage-state.json").read_text(encoding="utf-8"))
    assembled = state["stages"]["report_assembled"]
    required = {f"stages/{filename}" for filename, _, _ in REPORT_STAGES}
    if assembled.get("status") != "complete" or assembled.get("artifact") != ARTIFACTS["report"] or not required.issubset({row["path"] for row in assembled.get("upstream_artifacts", [])}):
        raise ValueError("report_assembled must record the report and all five upstream stages before preview")
    case = strict_json((output / "case.json").read_text(encoding="utf-8"))
    preview = {
        "schema": "rw-litnet-paper-case-preview/v1",
        "mode": "preview_only",
        "paper_case": case["paper_id"],
        "source_sha256": case["source_hash"],
        "deep_read_status": "audited" if gate == "PASS" else "review_required",
        "claim_gate": gate,
        "claim_verdicts": verdicts,
        "verified_claim_count": verdicts.get("VERIFIED", 0),
        "target_work": args.litnet_work,
        "target_zotero_record": args.zotero_record,
        "proposed_links": {
            "report": case["artifacts"]["report"],
            "claim_audit": str(audit_path),
            "visual_evidence": case["artifacts"]["visual_evidence"],
        },
        "write_performed": False,
    }
    preview_path = case_path(output, case["artifacts"]["litnet_preview"])
    write_json(preview_path, preview)
    print(json.dumps({"preview": str(preview_path), "claim_gate": gate}, ensure_ascii=False))
    return 0


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [strict_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_case(output: Path, include_stages: bool = True) -> list[str]:
    try:
        return _validate_case(output.resolve(), include_stages)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return [f"invalid Paper Case data: {exc}"]


def _validate_case(output: Path, include_stages: bool) -> list[str]:
    problems: list[str] = []
    case_file = case_path(output, "case.json")
    source_file = case_path(output, "source-manifest.json")
    if not case_file.is_file() or not source_file.is_file():
        return ["missing case.json or source-manifest.json"]
    case = strict_json(case_file.read_text(encoding="utf-8"))
    source = strict_json(source_file.read_text(encoding="utf-8"))
    if not isinstance(case, dict) or case.get("schema") != SCHEMA:
        return ["invalid Paper Case schema"]
    if not isinstance(source, dict) or source.get("schema") != "rw-paper-source/v0-experimental":
        return ["invalid source manifest schema"]
    if case.get("source_manifest") != "source-manifest.json" or case.get("artifacts") != ARTIFACTS:
        return ["artifact mapping must match the Paper Case schema"]
    for relative in ARTIFACTS.values():
        case_path(output, relative)
    pdf = Path(source["pdf_path"])
    if not pdf.is_file():
        problems.append("source PDF is missing")
    elif sha256_file(pdf) != case.get("source_hash"):
        problems.append("source PDF hash changed; case is STALE")
    if source.get("pdf_sha256") != case.get("source_hash"):
        problems.append("source manifest hash disagrees with case")
    if json_hash(CONFIG) != case.get("config_hash"):
        problems.append("extractor config changed; case is STALE")
    pages = source.get("pages")
    if type(pages) is not int or pages < 1:
        return problems + ["pages must be a positive integer"]
    snapshots = case.get("extraction_hashes")
    if not isinstance(snapshots, dict) or set(snapshots) != set(EXTRACTION_KEYS):
        problems.append("missing extraction hashes; rebuild into a new directory")
        snapshots = {}
    for key in (*EXTRACTION_KEYS, "claim_candidates"):
        path = case_path(output, ARTIFACTS[key])
        if not path.is_file():
            problems.append(f"missing evidence artifact: {key}")
        elif key in EXTRACTION_KEYS and sha256_file(path) != snapshots.get(key):
            problems.append(f"evidence artifact changed; case is STALE: {key}")
    if problems:
        return sorted(set(problems))

    def locator(row: Any, label: str) -> None:
        if not isinstance(row, dict):
            problems.append(f"invalid {label} record")
            return
        page = row.get("page")
        bbox = row.get("bbox")
        if type(page) is not int or not 1 <= page <= pages:
            problems.append(f"invalid {label} page")
        if not isinstance(bbox, list) or len(bbox) != 4 or any(type(x) not in (int, float) or not math.isfinite(x) for x in bbox) or bbox[0] > bbox[2] or bbox[1] > bbox[3]:
            problems.append(f"invalid {label} bbox")
        if not isinstance(row.get("locator"), str) or not row["locator"].strip():
            problems.append(f"invalid {label} locator")

    units = load_jsonl(case_path(output, ARTIFACTS["text_units"]))
    visuals = load_jsonl(case_path(output, ARTIFACTS["visual_evidence"]))
    sections = strict_json(case_path(output, ARTIFACTS["section_map"]).read_text(encoding="utf-8"))["sections"]
    if not isinstance(sections, list):
        problems.append("sections must be an array")
        sections = []
    expected_counts = {"text_units": len(units), "visuals": len(visuals), "sections": len(sections)}
    if case.get("counts") != expected_counts:
        problems.append("evidence counts disagree with case")
    ids: set[str] = set()
    for row in units:
        locator(row, "text")
        if not isinstance(row, dict):
            continue
        identifier = row.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            problems.append("invalid or duplicate text id")
        else:
            ids.add(identifier)
        if not isinstance(row.get("text"), str) or not row["text"].strip():
            problems.append("empty text unit")
    for section in sections:
        if not isinstance(section, dict) or section.get("text_unit_id") not in ids:
            problems.append("section points to missing text unit")
    visual_ids: set[str] = set()
    for row in visuals:
        locator(row, "visual")
        if not isinstance(row, dict):
            continue
        identifier = row.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in visual_ids:
            problems.append("invalid or duplicate visual id")
        else:
            visual_ids.add(identifier)
        image = case_path(output, row.get("image", ""))
        if not image.is_file():
            problems.append(f"missing visual image: {identifier}")
        elif sha256_file(image) != row.get("image_sha256"):
            problems.append(f"visual hash changed: {identifier}")
        segments = row.get("segments")
        if not isinstance(segments, list) or not segments:
            problems.append(f"visual has no source segments: {identifier}")
            continue
        for segment in segments:
            locator(segment, "visual segment")
        if type(row.get("cross_page")) is not bool or row["cross_page"] != (len(segments) > 1):
            problems.append(f"visual cross-page flag mismatch: {identifier}")

    state_file = case_path(output, "stage-state.json")
    if not state_file.is_file():
        return problems + ["missing stage-state.json"]
    state = strict_json(state_file.read_text(encoding="utf-8"))
    if state.get("schema") != "rw-paper-stage-state/v0-experimental" or any(state.get(key) != case[key] for key in ("source_hash", "config_hash")):
        problems.append("stage-state provenance mismatch")
    stages = state.get("stages")
    if not isinstance(stages, dict) or set(stages) != set(STAGES):
        return problems + ["stage-state must contain exactly the required stages"]
    for stage, record in stages.items():
        if not isinstance(record, dict) or any(record.get(key) != case[key] for key in ("source_hash", "config_hash")):
            problems.append(f"stage provenance mismatch: {stage}")
            continue
        if record.get("status") not in ("pending", "complete", "pass", "review", "block"):
            problems.append(f"invalid stage status: {stage}")
        if not include_stages:
            continue
        artifact_name = record.get("artifact")
        artifact_hash = record.get("artifact_sha256")
        if not artifact_name and not artifact_hash:
            if stage not in {"source_fixed", "content_located", "visual_evidence"} and record.get("status") != "pending":
                problems.append(f"completed stage has no artifact: {stage}")
            continue
        artifact = case_path(output, artifact_name)
        if not artifact.is_file():
            problems.append(f"missing stage artifact: {stage}")
        elif sha256_file(artifact) != artifact_hash:
            problems.append(f"stage artifact changed; downstream is STALE: {stage}")
        upstreams = record.get("upstream_artifacts", [])
        if not isinstance(upstreams, list):
            problems.append(f"stage upstream_artifacts must be an array: {stage}")
            continue
        for upstream in upstreams:
            upstream_path = case_path(output, upstream["path"])
            if not upstream_path.is_file():
                problems.append(f"missing upstream artifact; stage is STALE: {stage}")
            elif sha256_file(upstream_path) != upstream.get("sha256"):
                problems.append(f"upstream artifact changed; stage is STALE: {stage}")
    return sorted(set(problems))


def validate_command(args: argparse.Namespace) -> int:
    output = args.output.expanduser().resolve()
    problems = validate_case(output)
    if problems:
        print("Validation failed:")
        for problem in problems:
            print(f"- {problem}")
        return 2
    print("Validation passed")
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--pdf", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--title", required=True)
    build.add_argument("--doi", default="")
    build.add_argument("--zotero-library-id", type=int)
    build.add_argument("--zotero-key", default="")
    build.add_argument("--zotero-attachment-key", default="")
    build.set_defaults(func=build_case)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--output", type=Path, required=True)
    validate.set_defaults(func=validate_command)
    scaffold = subparsers.add_parser("scaffold")
    scaffold.add_argument("--output", type=Path, required=True)
    scaffold.add_argument("--force", action="store_true")
    scaffold.set_defaults(func=scaffold_command)
    mark_stage = subparsers.add_parser("mark-stage")
    mark_stage.add_argument("--output", type=Path, required=True)
    mark_stage.add_argument("--stage", choices=STAGES, required=True)
    mark_stage.add_argument("--artifact", required=True)
    mark_stage.add_argument("--upstream", action="append", default=[])
    mark_stage.add_argument("--status", choices=("complete", "pass", "review", "block"), default="complete")
    mark_stage.set_defaults(func=mark_stage_command)
    litnet = subparsers.add_parser("litnet-preview")
    litnet.add_argument("--output", type=Path, required=True)
    litnet.add_argument("--claim-audit", type=Path, required=True)
    litnet.add_argument("--litnet-work", default="")
    litnet.add_argument("--zotero-record", default="")
    litnet.set_defaults(func=litnet_preview_command)
    return parser


def main() -> int:
    args = make_parser().parse_args()
    try:
        return args.func(args)
    except (OSError, RuntimeError, ValueError, TypeError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
