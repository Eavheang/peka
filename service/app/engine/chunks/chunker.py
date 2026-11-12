from dataclasses import dataclass
from pathlib import Path
import re


# ponytail: estimated tokens, not the real tokenizer. bge-small-en-v1.5 embeds 512 tokens, and on the 70-file
# evaluation corpus this budget gave at most 438 real ones. Text full of acronyms or rare words can run over;
# TEI truncates those rather than failing, and keyword search still reads the whole chunk. Call TEI /tokenize
# instead if that ever matters.
MAX_CHUNK_TOKENS = 400
_TOKEN_RE = re.compile(r"[A-Za-z]{1,12}|\d{1,2}|\S")

# The extractor writes `#` headings for Word headings and numbered PDF sections.
_HEADED_FORMATS = {".md", ".docx", ".pdf"}
_LOCATOR_KEYS = ("page", "slide", "sheet", "name", "section")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.{1,100}?)(?:\s+#+)?\s*$")
_TABLE_RE = re.compile(r"((?:^[ \t]*\|.*\|[ \t]*(?:\n|$)){2,})", re.MULTILINE)
_TABLE_DELIMITER_RE = re.compile(r"[\s|:-]+")
# One short line without a closing stop or list marker: a caption, not a sentence or a bullet.
_CAPTION_RE = re.compile(r"[A-Za-z][^|\n]{0,78}[^.:;,!?|\s]")
# Coarsest first: paragraphs, lines, sentences, words. Each cut keeps the text around it.
_BOUNDARIES = tuple(re.compile(pattern) for pattern in (r"(?<=\n\n)", r"(?<=\n)", r"(?<=[.!?]\s)", r"(?<=\s)"))


def passage_text(title: str, heading: str, content: str) -> str:
    """What the embedder and the reranker read for one chunk."""
    return f"Document: {title}\nSection: {heading}\n\n{content}"


@dataclass(frozen=True)
class Chunk:
    title: str
    heading: str
    content: str
    source_locations: tuple[dict[str, int | str], ...]

    @property
    def embedding_text(self) -> str:
        return passage_text(self.title, self.heading, self.content)


def estimate_tokens(text: str) -> int:
    return len(_TOKEN_RE.findall(text))


def chunk_extraction(extraction: dict) -> list[Chunk]:
    """Build retrieval chunks from the extractor's original text, without any model."""
    title = Path(extraction.get("source_filename") or "Document").stem
    headed = extraction.get("source_extension") in _HEADED_FORMATS
    chunks: list[Chunk] = []

    for section in extraction.get("sections", []):
        text = section["text"].replace("\x00", "")  # PostgreSQL text cannot hold NUL.
        location = {key: section[key] for key in _LOCATOR_KEYS if key in section}
        for heading, body in _markdown_sections(text, _label(section)) if headed else [(_label(section), text)]:
            header = estimate_tokens(passage_text(title, heading, ""))
            room = max(MAX_CHUNK_TOKENS // 2, MAX_CHUNK_TOKENS - header)  # Long labels must leave room for text.
            pieces = _split_table(body, room) if "sheet" in section else _split_blocks(body, room)
            chunks.extend(Chunk(title, heading, piece, (location,) if location else ()) for piece in pieces)

    if not chunks:
        raise ValueError(f"No text to index in {extraction.get('source_filename') or 'this file'}")
    return chunks


def _label(section: dict) -> str:
    if "page" in section:
        return f"Page {section['page']}"
    if "slide" in section:
        return f"Slide {section['slide']}"
    if "sheet" in section:
        return f"Sheet: {section.get('name') or section['sheet']}"
    return f"Section {section['section']}" if section.get("section") else "Text"


def _markdown_sections(text: str, default_heading: str) -> list[tuple[str, str]]:
    """Split at `#` headings. Text before the first one stays under the default heading."""
    sections: list[tuple[str, str]] = []
    heading, lines, fenced = default_heading, [], False

    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        match = None if fenced else _HEADING_RE.match(line)
        if not match:
            lines.append(line)
            continue
        if body := "\n".join(lines).strip():
            sections.append((heading, body))
            lines = []
        elif heading != default_heading:
            lines = [heading]  # A heading with no body of its own stays as text of the next section.
        heading = match.group(1).strip()

    if body := "\n".join(lines).strip():
        sections.append((heading, body))
    elif heading != default_heading:
        sections.append((heading, heading))
    return sections


def _split_blocks(text: str, budget: int) -> list[str]:
    """Give each table, with its caption, its own chunks. The capture group puts tables at the odd indexes."""
    blocks = _TABLE_RE.split(text)
    for index in range(1, len(blocks), 2):
        # A short line just above a table ("Revenue by Quarter (FY2025)") is its caption: it goes with the table.
        before, _, last = blocks[index - 1].rstrip().rpartition("\n")
        if _CAPTION_RE.fullmatch(last.strip()):
            blocks[index - 1], blocks[index] = before, f"| {last.strip()} |\n{blocks[index]}"
    pieces: list[str] = []
    for index, block in enumerate(blocks):
        pieces.extend(_split_table(block, budget) if index % 2 else _pieces(block, budget))
    return pieces


def _cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _split_table(table: str, budget: int) -> list[str]:
    """Name every cell after its column, so a row says what its numbers mean in any chunk, then cut between rows."""
    lines = table.strip().splitlines()
    # The widest row is the header: sheets often start with one-cell title rows, which stay as they are.
    start = max(range(len(lines)), key=lambda index: len(_cells(lines[index])))
    names, rows = _cells(lines[start]), lines[start + 1 :]
    labelled = [
        "| " + " | ".join(f"{name}: {cell}" if name else cell for name, cell in zip(names, _cells(row)) if cell) + " |"
        if len(_cells(row)) <= len(names) else row
        for row in rows
        if not _TABLE_DELIMITER_RE.fullmatch(row)
    ]
    if not labelled or len(names) < 2:
        return _pieces(table, budget)
    # Title rows (units, "forecast", the total budget) say what every row means, so each part repeats them.
    cost = estimate_tokens("\n".join(lines[:start]))
    if cost > budget // 2:  # Repeating a long title would leave each part little room for rows.
        return _pieces("\n".join([*lines[:start], *labelled]), budget)
    return ["\n".join([*lines[:start], piece]) for piece in _pieces("\n".join(labelled), budget - cost)]


def _pieces(text: str, budget: int) -> list[str]:
    return [part.strip() for part in _split(text, budget) if part.strip()]


def _split(text: str, budget: int, boundaries: tuple[re.Pattern[str], ...] = _BOUNDARIES) -> list[str]:
    """Cut at the coarsest boundary that fits. The parts join back into the text."""
    if estimate_tokens(text) <= budget:
        return [text]
    if not boundaries:  # Unbroken text such as a long ID.
        tokens = _TOKEN_RE.findall(text)
        return ["".join(tokens[start : start + budget]) for start in range(0, len(tokens), budget)]

    parts: list[str] = []
    current, used = "", 0
    for block in boundaries[0].split(text):
        cost = estimate_tokens(block)
        if used + cost <= budget:
            current += block
            used += cost
            continue
        parts.append(current)
        *whole, current = _split(block, budget, boundaries[1:])
        parts.extend(whole)
        used = estimate_tokens(current)
    return [*parts, current]
