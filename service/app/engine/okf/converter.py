import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

import ai
from pydantic import BaseModel, ConfigDict, Field

from app.engine.ai_runtime import AIModelError, generate_structured
from app.engine.okf.file_writer import write_okf_files


class OKFConversionError(RuntimeError):
    pass


class OKFDocumentAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1)
    document_type: str = Field(min_length=1)
    category: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class OKFFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    file_type: Literal["okf_concept"]
    content: str = Field(min_length=1)


class OKFRetrievalSection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    concept_path: str = Field(min_length=1)
    heading: str = Field(min_length=1)
    anchor: str = Field(min_length=1)
    pages: list[int]
    summary: str = Field(min_length=1)


class OKFResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_analysis: OKFDocumentAnalysis
    folder_structure: list[str] = Field(min_length=1)
    files: list[OKFFile] = Field(min_length=1)
    retrieval_sections: list[OKFRetrievalSection]


def convert_to_okf(extraction: dict, base_dir: Path) -> dict:
    payload = dict(extraction)

    try:
        result = generate_structured(
            [
                ai.system_message(_prompt()),
                ai.user_message(json.dumps(payload, ensure_ascii=False, default=str)),
            ],
            OKFResult,
        )
    except AIModelError as error:
        raise OKFConversionError(str(error)) from error

    result_dict = result.model_dump(mode="json")

    try:
        _validate_concept_result(result_dict)
        # The LLM names the file from its title, so another upload with the same title
        # (e.g. the .pdf and .docx copy of one report) would overwrite this concept.
        concept = result_dict["files"][0]
        path = Path(concept["path"])
        concept["path"] = str(path.with_stem(f"{path.stem}-{extraction['source_id'][:8]}"))
        write_okf_files(result_dict, base_dir)
        write_indexes(base_dir)
    except ValueError as error:
        raise OKFConversionError(str(error)) from error
    return result_dict


def _validate_concept_result(result: dict) -> None:
    files = result.get("files")
    concepts = [
        file for file in files or []
        if isinstance(file, dict) and file.get("file_type") == "okf_concept"
    ]
    if not isinstance(files, list) or len(concepts) != 1 or len(files) != 1:
        raise ValueError("OKF result must contain exactly one concept file")


@lru_cache(maxsize=1)
def _prompt() -> str:
    return Path(__file__).with_name("prompt.txt").read_text(encoding="utf-8")


def write_indexes(base_dir: Path) -> None:
    knowledge_base = base_dir / "knowledge_base"
    if not knowledge_base.is_dir():
        raise ValueError("OKF knowledge base was not created")

    concepts = []
    for path in knowledge_base.rglob("*.md"):
        if path.name == "index.md" or len(path.relative_to(knowledge_base).parts) < 2:
            continue
        title, description = _concept_metadata(path)
        concepts.append((path.parent.name, title, description, path))

    categories = sorted({item[0] for item in concepts})
    root = ["---", 'okf_version: "0.2"', "---", "", "# Organization Knowledge Base", "", "## Categories", ""]
    root.extend(
        f"- [{_display_name(category)}](./{category}/index.md) - {_display_name(category)} documents."
        for category in categories
    )
    _write_index(knowledge_base / "index.md", root)

    for category in categories:
        entries = sorted((item for item in concepts if item[0] == category), key=lambda item: item[1].casefold())
        lines = [f"# {_display_name(category)}", ""]
        lines.extend(f"- [{title}](./{path.name}) - {description}" for _, title, description, path in entries)
        _write_index(knowledge_base / category / "index.md", lines)


def _concept_metadata(path: Path) -> tuple[str, str]:
    content = path.read_text(encoding="utf-8")
    end = content.find("\n---", 4) if content.startswith("---\n") else -1
    frontmatter = content[4:end] if end >= 0 else ""

    def value(field: str) -> str | None:
        match = re.search(rf"(?m)^{field}:\s*(.+?)\s*$", frontmatter)
        return match.group(1).strip().strip("'\"") if match else None

    title = value("title") or path.stem.replace("-", " ").title()
    description = value("description")
    if not description:
        body = content[end + 4:] if end >= 0 else content
        description = next((line.strip() for line in body.splitlines() if line.strip() and not line.startswith("#")), "Knowledge base document")
    return title, description.rstrip(".") + "."


def _display_name(value: str) -> str:
    return value.replace("-", " ").title()


def _write_index(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
