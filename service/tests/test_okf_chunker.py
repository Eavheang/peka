from app.engine.chunked.chunker import parse_okf_chunks


def test_parser_builds_summary_and_heading_chunks():
    result = {
        "document_analysis": {"title": "Remote Work Policy"},
        "files": [
            {
                "path": "knowledge_base/policies/remote-work-policy.md",
                "file_type": "okf_concept",
                "content": """---
type: Policy Document
title: Remote Work Policy
summary: Defines eligibility and approval requirements.
---

# Eligibility

Employees need six months of service.

# Approval Process

Managers approve requests.
""",
            }
        ],
        "retrieval_sections": [
            {"heading": "Eligibility", "anchor": "eligibility", "pages": [1, 2]},
            {"heading": "Approval Process", "anchor": "approval-process", "pages": [2]},
        ],
    }

    chunks = parse_okf_chunks(result)

    assert [(chunk.heading, chunk.source_locations) for chunk in chunks] == [
        ("Summary", ()),
        ("Eligibility", ({"type": "page", "value": 1}, {"type": "page", "value": 2})),
        ("Approval Process", ({"type": "page", "value": 2},)),
    ]
    assert chunks[1].embedding_text == (
        "Document: Remote Work Policy\nSection: Eligibility\n\n"
        "Employees need six months of service."
    )


def test_parser_splits_only_oversized_sections():
    content = "\n\n".join(["A" * 50, "B" * 50, "C" * 50])
    result = {
        "document_analysis": {"title": "Long Policy"},
        "files": [
            {
                "path": "knowledge_base/policies/long-policy.md",
                "file_type": "okf_concept",
                "content": f"---\nsummary: Long policy.\n---\n\n# Requirements\n\n{content}\n",
            }
        ],
        "retrieval_sections": [
            {"heading": "Requirements", "anchor": "requirements", "pages": [3]}
        ],
    }

    chunks = parse_okf_chunks(result, max_chars=110, overlap_chars=10)
    sections = [chunk for chunk in chunks if chunk.heading == "Requirements"]

    assert len(sections) == 2
    assert all(chunk.source_locations == ({"type": "page", "value": 3},) for chunk in sections)
    assert all(len(chunk.content) <= 110 for chunk in sections)
