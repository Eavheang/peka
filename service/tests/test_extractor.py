import hashlib
import json
from io import BytesIO
from uuid import uuid4

import pymupdf
import pytest
from docx import Document
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches
from fastapi import UploadFile

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
    monkeypatch.setattr(
        service,
        "convert_to_okf",
        lambda extraction, storage_root: pytest.fail("OKF conversion must run in worker"),
        raising=False,
    )
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
