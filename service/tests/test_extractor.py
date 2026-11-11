import hashlib
import json
from io import BytesIO
from uuid import uuid4

import pymupdf
from docx import Document
from docx.opc.constants import CONTENT_TYPE as CT, RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches
from fastapi import UploadFile

from app.engine.chunks.chunker import chunk_extraction
from app.engine.source_extractor import extract_file
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


def test_docx_headers_footers_and_footnotes_become_their_own_chunks(tmp_path):
    path = tmp_path / "report.docx"
    document = Document()
    document.add_paragraph("Body text.")
    document.sections[0].header.paragraphs[0].text = "Internal use only"
    document.sections[0].footer.paragraphs[0].text = "Finance team"
    document.add_section()  # Its header links to the first one, so it must not repeat.
    footnotes = (
        '<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>'
        '<w:footnote w:id="1"><w:p><w:r><w:t>Source:</w:t><w:tab/><w:t>2025</w:t></w:r><w:r><w:br/><w:t>audit.</w:t></w:r></w:p></w:footnote>'
        "</w:footnotes>"
    )
    part = Part(PackURI("/word/footnotes.xml"), CT.WML_FOOTNOTES, footnotes.encode(), document.part.package)
    document.part.relate_to(part, RT.FOOTNOTES)
    document.save(path)

    chunks = chunk_extraction(extract_file(path))

    assert [(chunk.heading, chunk.content, chunk.source_locations) for chunk in chunks] == [
        ("Text", "Body text.", ({"section": 0},)),
        ("Footnotes", "Source: 2025 audit.", ({"part": "footnotes"},)),
        ("Headers and footers", "Internal use only\nFinance team", ({"part": "headers and footers"},)),
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


def test_pptx_table_text_is_extracted_as_its_own_chunk(tmp_path):
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
        ("Slide 1", "Roadmap", ({"slide": 1},)),
        ("Slide 1", "| Phase: Beta | Date: March |", ({"slide": 1},)),
    ]


def test_pptx_grouped_shapes_and_speaker_notes_are_extracted(tmp_path):
    path = tmp_path / "deck.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    group = slide.shapes.add_group_shape()
    group.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1)).text = "Grouped label"
    slide.notes_slide.notes_text_frame.text = "Mention the budget."
    presentation.save(path)

    chunks = chunk_extraction(extract_file(path))

    assert [(chunk.heading, chunk.content, chunk.source_locations) for chunk in chunks] == [
        ("Slide 1", "Grouped label", ({"slide": 1},)),
        ("Slide 1 notes", "Mention the budget.", ({"slide": 1, "part": "notes"},)),
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
