from dataclasses import dataclass
import re


@dataclass(frozen=True)
class OKFChunk:
    title: str
    heading: str
    content: str
    source_locations: tuple[dict[str, int | str], ...]

    @property
    def embedding_text(self) -> str:
        return f"Document: {self.title}\nSection: {self.heading}\n\n{self.content}"


def parse_okf_chunks(
    result: dict,
    max_chars: int = 3000,
    overlap_chars: int = 200,
) -> list[OKFChunk]:
    concept = next(
        (file for file in result.get("files", []) if file.get("file_type") == "okf_concept"),
        None,
    )
    if concept is None or not isinstance(concept.get("content"), str):
        raise ValueError("OKF result has no concept file")

    markdown = concept["content"]
    title = result.get("document_analysis", {}).get("title") or _frontmatter_value(markdown, "title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("OKF concept has no title")

    retrieval = {
        item.get("heading"): item
        for item in result.get("retrieval_sections", [])
        if isinstance(item, dict) and isinstance(item.get("heading"), str)
    }
    chunks: list[OKFChunk] = []
    summary = _frontmatter_value(markdown, "summary") or _frontmatter_value(markdown, "description")
    if summary:
        chunks.append(
            OKFChunk(
                title.strip(),
                "Summary",
                summary,
                (),
            )
        )

    for heading, content in _sections(markdown):
        metadata = retrieval.get(heading, {})
        pages = tuple(
            sorted(
                {
                    page
                    for page in metadata.get("pages", [])
                    if isinstance(page, int) and not isinstance(page, bool) and page > 0
                }
            )
        )
        source_locations = tuple({"type": "page", "value": page} for page in pages)
        for part in _split_content(content, max_chars, overlap_chars):
            chunks.append(
                OKFChunk(
                    title.strip(),
                    heading,
                    part,
                    source_locations,
                )
            )

    if not chunks:
        raise ValueError("OKF concept has no retrievable content")
    return chunks


def _sections(markdown: str) -> list[tuple[str, str]]:
    body = _without_frontmatter(markdown)
    sections: list[tuple[str, str]] = []
    heading: str | None = None
    lines: list[str] = []
    fenced = False
    for line in body.splitlines():
        if line.lstrip().startswith("```") or line.lstrip().startswith("~~~"):
            fenced = not fenced
        match = None if fenced else re.match(r"^#\s+(.+?)\s*#*\s*$", line)
        if match:
            if heading and (content := "\n".join(lines).strip()):
                sections.append((heading, content))
            heading = match.group(1).strip()
            lines = []
        elif heading:
            lines.append(line)
    if heading and (content := "\n".join(lines).strip()):
        sections.append((heading, content))
    return sections


def _split_content(content: str, max_chars: int, overlap_chars: int) -> list[str]:
    if max_chars < 1 or overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("Invalid OKF chunk size")
    if len(content) <= max_chars:
        return [content]

    output: list[str] = []
    current = ""
    for block in re.split(r"\n\s*\n", content):
        block = block.strip()
        if not block:
            continue
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            output.append(current)
            current = ""
        if len(block) <= max_chars:
            current = block
            continue
        # ponytail: character fallback handles unbroken/OCR text; tokenizer splitting if recall suffers.
        step = max_chars - overlap_chars
        output.extend(block[start : start + max_chars] for start in range(0, len(block), step))
    if current:
        output.append(current)
    return output


def _without_frontmatter(markdown: str) -> str:
    if not markdown.startswith("---\n"):
        return markdown
    end = markdown.find("\n---", 4)
    return markdown[end + 4 :] if end >= 0 else markdown


def _frontmatter_value(markdown: str, field: str) -> str | None:
    if not markdown.startswith("---\n"):
        return None
    end = markdown.find("\n---", 4)
    if end < 0:
        return None
    match = re.search(rf"(?m)^{re.escape(field)}:\s*(.+?)\s*$", markdown[4:end])
    if not match:
        return None
    return match.group(1).strip().strip("'\"")
