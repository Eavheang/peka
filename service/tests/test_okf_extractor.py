import json

import pytest

from app.engine.okf import converter as main
from app.engine.okf.file_writer import write_okf_files


def test_convert_to_okf_calls_llm_and_writes_files(monkeypatch, tmp_path):
    extraction = {
        "source_id": "abc123",
        "source_filename": "policy.txt",
        "sections": [{"text": "Employees must sign in."}],
    }
    result = {
        "document_analysis": {
            "title": "Sign-in Policy",
            "document_type": "Policy Document",
            "category": "policies",
            "filename": "sign-in-policy.md",
            "confidence": 1,
        },
        "files": [
            {
                "path": "knowledge_base/policies/sign-in-policy.md",
                "file_type": "okf_concept",
                "content": "---\ntype: Policy Document\n---\n\n# Overview\n\nEmployees must sign in.\n",
            }
        ],
        "folder_structure": ["knowledge_base/policies/sign-in-policy.md"],
    }
    request = {}

    def fake_generation(messages, output_type, max_tokens=None):
        request["messages"] = messages
        request["output_type"] = output_type
        request["max_tokens"] = max_tokens
        return main.OKFResult.model_validate(result)

    monkeypatch.setattr(main, "generate_structured", fake_generation)

    converted = main.convert_to_okf(extraction, tmp_path)

    assert converted["files"][0]["path"] == "knowledge_base/policies/sign-in-policy-abc123.md"
    assert request["output_type"] is main.OKFResult
    assert request["max_tokens"] == main.settings.okf_max_tokens
    payload = json.loads(request["messages"][1].text)
    assert payload["source_id"] == "abc123"
    assert "knowledge_base_state" not in payload
    assert (tmp_path / "knowledge_base" / "policies" / "sign-in-policy-abc123.md").is_file()
    assert (tmp_path / "knowledge_base" / "index.md").read_text(encoding="utf-8") == (
        '---\nokf_version: "0.2"\n---\n\n'
        "# Organization Knowledge Base\n\n## Categories\n\n"
        "- [Policies](./policies/index.md) - Policies documents.\n"
    )
    assert (tmp_path / "knowledge_base" / "policies" / "index.md").read_text(
        encoding="utf-8"
    ) == "# Policies\n\n- [Sign In Policy Abc123](./sign-in-policy-abc123.md) - Employees must sign in.\n"


def test_convert_to_okf_keeps_same_titled_sources_apart(monkeypatch, tmp_path):
    result = {
        "document_analysis": {
            "title": "Report",
            "document_type": "Report",
            "category": "reports",
            "filename": "report.md",
            "confidence": 1,
        },
        "files": [{"path": "knowledge_base/reports/report.md", "file_type": "okf_concept", "content": "# Overview\n\nText.\n"}],
        "folder_structure": ["knowledge_base/reports/report.md"],
    }
    monkeypatch.setattr(main, "generate_structured", lambda messages, output_type, **kwargs: main.OKFResult.model_validate(result))

    main.convert_to_okf({"source_id": "aaaaaaaa1111", "sections": []}, tmp_path)
    main.convert_to_okf({"source_id": "bbbbbbbb2222", "sections": []}, tmp_path)

    assert sorted(path.name for path in (tmp_path / "knowledge_base" / "reports").glob("report-*.md")) == [
        "report-aaaaaaaa.md",
        "report-bbbbbbbb.md",
    ]


def test_index_generation_preserves_and_sorts_existing_concepts(tmp_path):
    policies = tmp_path / "knowledge_base" / "policies"
    policies.mkdir(parents=True)
    (policies / "zebra.md").write_text(
        "---\ntitle: Zebra Policy\ndescription: Z description.\n---\n\n# Rules\n",
        encoding="utf-8",
    )
    (policies / "alpha.md").write_text(
        "---\ntitle: Alpha Policy\ndescription: A description.\n---\n\n# Rules\n",
        encoding="utf-8",
    )

    main.write_indexes(tmp_path)

    assert (policies / "index.md").read_text(encoding="utf-8") == (
        "# Policies\n\n"
        "- [Alpha Policy](./alpha.md) - A description.\n"
        "- [Zebra Policy](./zebra.md) - Z description.\n"
    )


def test_write_okf_files_rejects_paths_outside_knowledge_base(tmp_path):
    with pytest.raises(ValueError, match="Unsafe path"):
        write_okf_files(
            {"files": [{"path": "../outside.md", "content": "bad"}]},
            tmp_path,
        )


def test_convert_to_okf_rejects_invalid_structured_output(monkeypatch, tmp_path):
    monkeypatch.setattr(
        main,
        "generate_structured",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            main.AIModelError("Model returned an invalid structured response")
        ),
    )

    with pytest.raises(main.OKFConversionError, match="invalid structured"):
        main.convert_to_okf({"source_id": "abc123", "sections": []}, tmp_path)
