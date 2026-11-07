"""Extract local source files into JSON records."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import pymupdf
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from openpyxl import load_workbook
from pptx import Presentation


SECTION_HEADING_RE = re.compile(r"^(?P<number>\d+)[.)]\s+(?P<title>[A-Z][^\n]*)$")

_TEXT_RULER_RE = re.compile(r"\s*-{2,}(?:\s+-{2,})+\s*")

SUPPORTED = {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md"}


def clean_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_id_for(path: Path) -> str:
    identity = path.resolve().as_posix().casefold()
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def extract_pdf(path: Path) -> list[dict[str, object]]:
    sections = []
    with pymupdf.open(path) as document:
        for number, page in enumerate(document, start=1):
            tables = page.find_tables().tables
            # Tables become pipe rows, which the chunker keeps apart from the prose around them.
            blocks = [
                block[4]
                for block in page.get_text("blocks")
                # By the block's centre: a table's box can be slightly smaller than the text in it.
                if not any(
                    pymupdf.Point((block[0] + block[2]) / 2, (block[1] + block[3]) / 2) in pymupdf.Rect(table.bbox)
                    for table in tables
                )
            ]
            rows = [_table_text(_pdf_cells(page, table)) for table in tables]
            text = clean_text("\n".join([*blocks, *rows]))
            if text:
                sections.append({"page": number, "text": text})
    return sections


def _table_text(rows: Iterable[Iterable[object]]) -> str:
    """Pipe-delimited rows: clean_text collapses tabs, which would lose the cell boundaries."""
    lines = []
    for row in rows:
        cells = [" ".join(str("" if cell is None else cell).split()) for cell in row]
        while cells and not cells[-1]:
            cells.pop()
        if cells:
            lines.append(f"| {' | '.join(cells)} |")
    return "\n".join(lines)


def _pdf_cells(page: pymupdf.Page, table: pymupdf.table.Table) -> list[list[str]]:
    # Read each cell from the page: table.extract() can lose the spaces between words.
    return [[page.get_text(clip=cell) if cell else "" for cell in row.cells] for row in table.rows]


def _pipe_aligned_tables(text: str) -> str:
    """Columns aligned under a dashed ruler become pipe rows, before clean_text collapses their spacing."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if index and _TEXT_RULER_RE.fullmatch(line):
            end = next((i for i in range(index + 1, len(lines)) if not lines[i].strip()), len(lines))
            rows = [lines[index - 1], *lines[index + 1 : end]]
            lines[index - 1 : end] = [_table_text(re.split(r"\s{2,}", row.strip()) for row in rows)]
    return "\n".join(lines)


def extract_docx(path: Path) -> list[dict[str, object]]:
    document = Document(path)
    section_blocks: dict[int, list[str]] = {0: []}
    current_section = 0
    last_number = 0

    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            paragraph = Paragraph(child, document)
            raw_text = paragraph.text
            text = clean_text(raw_text)
            style_name = paragraph.style.name if paragraph.style else ""
            match = SECTION_HEADING_RE.fullmatch(text)
            if text and (
                style_name.lower().startswith("heading")
                or (match and int(match.group("number")) == last_number + 1)
            ):
                last_number = int(match.group("number")) if match else last_number
                current_section += 1
                section_blocks[current_section] = []
                text = f"# {text}"  # The chunker splits on Markdown headings.
        elif child.tag.endswith("}tbl"):
            table = Table(child, document)
            text = _table_text([cell.text for cell in row.cells] for row in table.rows)
        else:
            continue

        if text:
            section_blocks.setdefault(current_section, []).append(text)

    return [
        {"section": number, "text": clean_text("\n".join(blocks))}
        for number, blocks in section_blocks.items()
        if clean_text("\n".join(blocks))
    ]


def extract_pptx(path: Path) -> list[dict[str, object]]:
    presentation = Presentation(path)
    sections = []
    for number, slide in enumerate(presentation.slides, start=1):
        blocks = []
        for shape in slide.shapes:
            if getattr(shape, "has_table", False):
                blocks.append(_table_text([cell.text for cell in row.cells] for row in shape.table.rows))
            elif getattr(shape, "has_text_frame", False) and shape.text.strip():
                blocks.append(shape.text)
        text = clean_text("\n".join(blocks))
        if text:
            sections.append({"slide": number, "text": text})
    return sections


def extract_xlsx(path: Path) -> list[dict[str, object]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    sections = []
    for number, sheet_name in enumerate(workbook.sheetnames, start=1):
        text = clean_text(_table_text(workbook[sheet_name].iter_rows(values_only=True)))
        if text:
            sections.append({"sheet": number, "name": sheet_name, "text": text})
    workbook.close()
    return sections


def extract_file(
    path: Path,
    *,
    source_id: str | None = None,
    content_hash: str | None = None,
) -> dict[str, object]:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(f"Unsupported file type: {path.suffix or '(none)'}")

    resolved_path = path.resolve()
    source_sha256 = content_hash or file_sha256(resolved_path)
    if suffix == ".pdf":
        sections = extract_pdf(resolved_path)
    elif suffix == ".docx":
        sections = extract_docx(resolved_path)
    elif suffix == ".pptx":
        sections = extract_pptx(resolved_path)
    elif suffix == ".xlsx":
        sections = extract_xlsx(resolved_path)
    else:
        text = clean_text(_pipe_aligned_tables(resolved_path.read_text(encoding="utf-8", errors="replace")))
        sections = [{"text": text}] if text else []

    return {
        "source_id": source_id or source_id_for(resolved_path),
        "source_sha256": source_sha256,
        "source_filename": resolved_path.name,
        "source_path": str(resolved_path),
        "source_extension": suffix,
        "extracted_at": datetime.now(UTC).isoformat(),
        "sections": sections,
    }

