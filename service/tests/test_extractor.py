import hashlib
import json
from io import BytesIO
from uuid import uuid4

import pymupdf
from docx import Document
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches
from fastapi import UploadFile

from app.engine.chunks.chunker import chunk_extraction
from app.engine.source_extractor import _numbered_headings, extract_file
from app.files import service


def test_upload_extraction_supports_every_format(monkeypatch, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "PDF text")
        pdf.save(pdf_path)

    docx_path = tmp_path / "sample.docx"
    document = Document()
    document.add_heading("1. Overview", level=1)
    document.add_paragraph("DOCX text")
    document.save(docx_path)

    pptx_path = tmp_path / "sample.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1)).text = "PPTX text"
    presentation.save(pptx_path)

    xlsx_path = tmp_path / "sample.xlsx"
    workbook = Workbook()
    workbook.active["A1"] = "XLSX text"
    workbook.save(xlsx_path)
    workbook.close()

    text_path = tmp_path / "sample.txt"
    text_path.write_text("TXT text", encoding="utf-8")
    markdown_path = tmp_path / "sample.md"
    markdown_path.write_text("# MD text", encoding="utf-8")

    samples = {
        pdf_path: "PDF text",
        docx_path: "DOCX text",
        pptx_path: "PPTX text",
        xlsx_path: "XLSX text",
        text_path: "TXT text",
        markdown_path: "MD text",
    }
    storage = tmp_path / "storage"
    monkeypatch.setattr(service.settings, "file_storage_dir", storage)
    monkeypatch.setattr(service.files_repository, "exists_by_sha256", lambda _: False)
    monkeypatch.setattr(service.files_repository, "create_many", lambda files, author_id: [])
    service.store_files(
        [UploadFile(file=BytesIO(path.read_bytes()), filename=path.name) for path in samples],
        uuid4(),
    )

    extraction_files = list((storage / "extracted").glob("*.json"))
    assert len(extraction_files) == len(samples)
    extractions = {
        record["source_filename"]: record
        for output in extraction_files
        for record in [json.loads(output.read_text(encoding="utf-8"))]
    }
    for path, expected_text in samples.items():
        record = extractions[path.name]
        assert record["source_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert record["source_extension"] == path.suffix
        assert expected_text in "\n".join(section["text"] for section in record["sections"])


def test_docx_chunks_follow_unnumbered_headings_and_tables(tmp_path):
    path = tmp_path / "policy.docx"
    document = Document()
    document.add_paragraph("Cover note.")
    document.add_heading("Scope", level=1)
    document.add_paragraph("Applies to staff.")
    table = document.add_table(rows=2, cols=2)
    for cell, text in zip(table._cells, ("Role", "Hours", "Nurse", "40")):
        cell.text = text
    document.add_heading("1. Approval", level=2)
    document.add_paragraph("Managers approve.")
    document.save(path)

    chunks = chunk_extraction(extract_file(path))

    assert [(chunk.heading, chunk.content, chunk.source_locations) for chunk in chunks] == [
        ("Text", "Cover note.", ({"section": 0},)),
        ("Scope", "Applies to staff.", ({"section": 1},)),
        ("Scope", "| Role: Nurse | Hours: 40 |", ({"section": 1},)),
        ("1. Approval", "Managers approve.", ({"section": 2},)),
    ]


def test_pdf_table_becomes_pipe_rows_apart_from_the_prose(tmp_path) -> None:
    path = tmp_path / "ruled.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "Narrative before the table.")
        for row, cells in enumerate([("Metric", "Owner"), ("Uptime", "Dana Lee")]):
            for column, text in enumerate(cells):
                cell = pymupdf.Rect(72 + 150 * column, 120 + 30 * row, 222 + 150 * column, 150 + 30 * row)
                page.draw_rect(cell)
                page.insert_text((cell.x0 + 5, cell.y0 + 20), text)
        pdf.save(path)

    chunks = chunk_extraction(extract_file(path))

    prose, table = [chunk.content for chunk in chunks]
    assert prose == "Narrative before the table."
    assert "Metric: Uptime" in table and "Owner: Dana Lee" in table
    assert all(chunk.source_locations == ({"page": 1},) for chunk in chunks)


def test_adjacent_pdf_tables_keep_their_own_columns_and_follow_their_headings(tmp_path) -> None:
    path = tmp_path / "two-tables.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "1. Approval", fontname="hebo")  # Helvetica Bold
        page.insert_text((72, 230), "2. Vendors", fontname="hebo")
        for top, table in ((90, [("Value", "Approver"), ("Small", "Manager")]),
                           (250, [("Category", "Vendor"), ("Video", "Northbank")])):
            for row, cells in enumerate(table):
                for column, text in enumerate(cells):
                    cell = pymupdf.Rect(72 + 150 * column, top + 30 * row, 222 + 150 * column, top + 30 + 30 * row)
                    page.draw_rect(cell)
                    page.insert_text((cell.x0 + 5, cell.y0 + 20), text)
        pdf.save(path)

    chunks = [(chunk.heading, chunk.content) for chunk in chunk_extraction(extract_file(path))]

    # Bold numbered lines become section headings.
    assert chunks == [("1. Approval", "| Value: Small | Approver: Manager |"),
                      ("2. Vendors", "| Category: Video | Vendor: Northbank |")]


def test_only_bold_numbered_pdf_lines_become_headings_and_continue_on_the_next_page() -> None:
    bold = {"1. Scope", "2. Steps", "3. Payment"}
    # A contents line and a numbered list share the numbering but are not bold.
    page_1, heading = _numbered_headings(
        "1. Scope 2\n1. Scope\nCovers vendors.\n2. Steps\n1. Call legal\n2. Wait", "", bold
    )
    page_2, heading = _numbered_headings("3. Wait more\nManagers approve.\n3. Payment", heading, bold)

    assert page_1 == "1. Scope 2\n# 1. Scope\nCovers vendors.\n# 2. Steps\n1. Call legal\n2. Wait"
    assert page_2 == "# 2. Steps\n3. Wait more\nManagers approve.\n# 3. Payment"
    assert heading == "3. Payment"


def test_plain_text_columns_under_a_ruler_become_their_own_table_chunk(tmp_path) -> None:
    path = tmp_path / "plan.txt"
    path.write_text(
        "Some narrative.\n\n"
        "Metric                Baseline  Target  Owner\n"
        "--------------------  --------  ------  -----------\n"
        "Performance Reviews   52%       91%     Quality Team\n"
        "\nClosing words.\n"
    )

    chunks = chunk_extraction(extract_file(path))

    assert [chunk.content for chunk in chunks] == [
        "Some narrative.",
        "| Metric: Performance Reviews | Baseline: 52% | Target: 91% | Owner: Quality Team |",
        "Closing words.",
    ]


def test_pptx_table_keeps_the_title_above_it_as_its_caption(tmp_path):
    path = tmp_path / "deck.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1)).text = "Roadmap"
    table = slide.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(4), Inches(1)).table
    for row, values in enumerate((("Phase", "Date"), ("Beta", "March"))):
        for column, value in enumerate(values):
            table.cell(row, column).text = value
    presentation.save(path)

    chunks = chunk_extraction(extract_file(path))

    assert [(chunk.heading, chunk.content, chunk.source_locations) for chunk in chunks] == [
        ("Slide 1", "| Roadmap |\n| Phase: Beta | Date: March |", ({"slide": 1},)),
    ]


def test_xlsx_keeps_cell_boundaries_and_skips_empty_rows(tmp_path):
    path = tmp_path / "sales.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Q1"
    sheet.append(["Region", "Sales", "Owner"])
    sheet.append(["North Coast", None, "Dana Lee"])
    sheet.append([None, None, None])
    sheet.append(["South", 100])
    workbook.save(path)
    workbook.close()

    chunks = chunk_extraction(extract_file(path))

    assert [(chunk.heading, chunk.content, chunk.source_locations) for chunk in chunks] == [
        (
            "Sheet: Q1",
            "| Region: North Coast | Owner: Dana Lee |\n| Region: South | Sales: 100 |",
            ({"sheet": 1, "name": "Q1"},),
        ),
    ]
