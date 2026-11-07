import re

import pytest

from app.engine.chunks.chunker import MAX_CHUNK_TOKENS, chunk_extraction, estimate_tokens


def extraction(*sections, extension=".txt", name="report"):
    return {
        "source_filename": f"{name}{extension}",
        "source_extension": extension,
        "sections": list(sections),
    }


def without_space(text):
    return re.sub(r"\s+", "", text)


def assert_fits(chunks):
    assert all(estimate_tokens(chunk.embedding_text) <= MAX_CHUNK_TOKENS for chunk in chunks)


def test_plain_text_without_headings_keeps_every_word():
    text = "\n\n".join(f"Paragraph {number} says the limit is {number * 7} days." for number in range(200))

    chunks = chunk_extraction(extraction({"text": text}))

    assert len(chunks) > 1
    assert {chunk.heading for chunk in chunks} == {"Text"}
    assert chunks[0].source_locations == ()
    assert without_space("".join(chunk.content for chunk in chunks)) == without_space(text)
    assert_fits(chunks)


def test_markdown_keeps_text_before_the_first_heading_and_splits_at_every_level():
    text = (
        "Intro before any heading.\n\n# Report\n\n## Scope\n\nApplies to staff.\n\n"
        "```\n# not a heading\n```\n\n### Details\n\nFine print.\n\n# Closing"
    )

    chunks = chunk_extraction(extraction({"text": text}, extension=".md"))

    assert [(chunk.heading, chunk.content) for chunk in chunks] == [
        ("Text", "Intro before any heading."),
        # "Report" has no body of its own, so its text moves into the next section.
        ("Scope", "Report\n\nApplies to staff.\n\n```\n# not a heading\n```"),
        ("Details", "Fine print."),
        ("Closing", "Closing"),
    ]


def test_hash_lines_are_not_headings_in_plain_text():
    chunks = chunk_extraction(extraction({"text": "# 12 is the ticket\nSee above."}))

    assert [chunk.heading for chunk in chunks] == ["Text"]
    assert chunks[0].content == "# 12 is the ticket\nSee above."


def test_overlong_markdown_heading_stays_as_body_text():
    line = f"# {'very long heading ' * 20}"

    chunks = chunk_extraction(extraction({"text": line}, extension=".md"))

    assert chunks[0].heading == "Text"
    assert "very long heading" in chunks[0].content


def test_pages_get_extractor_locators():
    long_page = " ".join(f"Sentence {number} holds a fact." for number in range(300))

    chunks = chunk_extraction(
        extraction({"page": 2, "text": "Short page."}, {"page": 3, "text": long_page}, extension=".pdf")
    )

    assert chunks[0].heading == "Page 2"
    assert chunks[0].content == "Short page."
    assert chunks[0].source_locations == ({"page": 2},)
    parts = chunks[1:]
    assert len(parts) > 1
    assert all(chunk.heading == "Page 3" and chunk.source_locations == ({"page": 3},) for chunk in parts)
    assert without_space("".join(chunk.content for chunk in parts)) == without_space(long_page)
    assert_fits(chunks)


def test_repeated_source_headings_keep_every_section():
    chunks = chunk_extraction(extraction({"text": "# Overview\n\nFirst.\n\n# Overview\n\nSecond."}, extension=".md"))

    assert [(chunk.heading, chunk.content) for chunk in chunks] == [("Overview", "First."), ("Overview", "Second.")]


def test_tables_become_their_own_chunks():
    table = "| Metric | Owner |\n|---|---|\n| Uptime | Dana |"
    text = f"# Metrics\n\nBefore the table.\n\n{table}\n\nAfter the table."

    chunks = chunk_extraction(extraction({"text": text}, extension=".md"))

    assert [chunk.content for chunk in chunks] == [
        "Before the table.", "| Metric: Uptime | Owner: Dana |", "After the table."]
    assert_fits(chunks)


def test_section_that_is_only_a_table_keeps_its_heading():
    table = "| Metric | Owner |\n|---|---|\n| Uptime | Dana |"

    chunks = chunk_extraction(extraction({"text": f"# Key Metrics\n\n{table}"}, extension=".md"))

    assert [(chunk.heading, chunk.content) for chunk in chunks] == [("Key Metrics", "| Metric: Uptime | Owner: Dana |")]


def test_large_markdown_table_labels_every_row_in_every_part():
    rows = [f"| Row {number} | {number * 1000} |" for number in range(200)]
    table = "\n".join(["| Name | Amount |", "|---|---|", *rows])

    chunks = chunk_extraction(extraction({"text": table}, extension=".md"))

    assert len(chunks) > 1
    expected = [f"| Name: Row {number} | Amount: {number * 1000} |" for number in range(200)]
    assert [line for chunk in chunks for line in chunk.content.splitlines()] == expected
    assert_fits(chunks)


def test_sheet_splits_between_labelled_rows_and_keeps_locator():
    rows = [f"| Region {number} | {number} | {number * 3} |" for number in range(200)]
    text = "\n".join(["| Region | Sales | Cost |", *rows])

    chunks = chunk_extraction(extraction({"sheet": 2, "name": "Q1", "text": text}, extension=".xlsx"))

    assert len(chunks) > 1
    assert {chunk.heading for chunk in chunks} == {"Sheet: Q1"}
    assert all(chunk.source_locations == ({"sheet": 2, "name": "Q1"},) for chunk in chunks)
    expected = [f"| Region: Region {number} | Sales: {number} | Cost: {number * 3} |" for number in range(200)]
    assert [line for chunk in chunks for line in chunk.content.splitlines()] == expected
    assert_fits(chunks)


def test_single_row_sheet_is_kept():
    chunks = chunk_extraction(extraction({"sheet": 1, "name": "Only", "text": "| Total | 5 |"}, extension=".xlsx"))

    assert [chunk.content for chunk in chunks] == ["| Total | 5 |"]


def test_title_rows_above_a_sheet_header_stay_and_the_widest_row_labels_the_rest():
    text = "| Stock levels |\n| SKU | Owner |\n| A1 | Dana |"

    chunks = chunk_extraction(extraction({"sheet": 1, "name": "S", "text": text}, extension=".xlsx"))

    assert chunks[0].content == "| Stock levels |\n| SKU: A1 | Owner: Dana |"


def test_short_rows_and_empty_cells_lose_nothing():
    table = "| A | B | C |\n| 1 |  | 3 |\n| 4 |"

    chunks = chunk_extraction(extraction({"text": table}))

    assert chunks[0].content == "| A: 1 | C: 3 |\n| A: 4 |"


def test_extraction_saved_before_this_format_still_chunks():
    chunks = chunk_extraction(
        extraction(
            {"section": 0, "text": "Cover text."},
            {"section": 2, "text": "2. Scope\nApplies to staff."},
            {"sheet": 1, "name": "Q1", "text": "Region Sales\nNorth 100"},
            extension=".docx",
        )
    )

    assert [(chunk.heading, chunk.source_locations) for chunk in chunks] == [
        ("Text", ({"section": 0},)),
        ("Section 2", ({"section": 2},)),
        ("Sheet: Q1", ({"sheet": 1, "name": "Q1"},)),
    ]


def test_slides_get_slide_headings_and_locators():
    chunks = chunk_extraction(extraction({"slide": 4, "text": "Roadmap"}, extension=".pptx"))

    assert [(chunk.heading, chunk.source_locations) for chunk in chunks] == [("Slide 4", ({"slide": 4},))]


@pytest.mark.parametrize(
    "text",
    [
        "公司政策规定所有员工必须签到。" * 400,
        "x" * 5000,
        "." * 5000,
        "1,234,567.89 " * 800,
        "A" * 3000 + " " + "b" * 3000,
    ],
)
def test_dense_text_fits_the_embedding_window_and_loses_nothing(text):
    chunks = chunk_extraction(extraction({"page": 1, "text": text}, extension=".pdf", name="n" * 300))

    assert_fits(chunks)
    assert without_space("".join(chunk.content for chunk in chunks)) == without_space(text)


@pytest.mark.parametrize(
    ("text", "real_tokens"),
    [
        # Counted with TEI /tokenize on BAAI/bge-small-en-v1.5, without [CLS] and [SEP].
        ("Employees must sign in at the start of every working day.", 12),
        ("| 1,234,567.89 | 78.9% | 2026-03-14 | 0.0042 |", 27),
    ],
)
def test_budget_keeps_measured_token_counts_inside_the_embedding_window(text, real_tokens):
    assert real_tokens * MAX_CHUNK_TOKENS <= estimate_tokens(text) * 512


def test_long_file_name_still_leaves_room_for_text():
    body = " ".join(f"Sentence {number} holds a fact." for number in range(100))

    chunks = chunk_extraction(extraction({"text": body}, name="-" * 500))

    assert without_space("".join(chunk.content for chunk in chunks)) == without_space(body)


def test_only_a_spaced_closing_hash_is_removed_from_a_heading():
    chunks = chunk_extraction(extraction({"text": "# C#\n\nOne.\n\n## Rust ##\n\nTwo."}, extension=".md"))

    assert [chunk.heading for chunk in chunks] == ["C#", "Rust"]


def test_title_comes_from_the_file_name():
    chunks = chunk_extraction(extraction({"text": "Hello."}, name="Remote Work Policy"))

    assert chunks[0].embedding_text == "Document: Remote Work Policy\nSection: Text\n\nHello."


def test_nul_characters_are_removed_because_postgres_rejects_them():
    chunks = chunk_extraction(extraction({"text": "before\x00after"}))

    assert chunks[0].content == "beforeafter"


@pytest.mark.parametrize("sections", [[], [{"page": 1, "text": "  \n "}]])
def test_extraction_without_text_fails_clearly(sections):
    with pytest.raises(ValueError, match=r"No text to index in report\.pdf"):
        chunk_extraction(extraction(*sections, extension=".pdf"))
