import json

import pytest
from pydantic import SecretStr

from app.engine.okf import converter as main
from app.engine.okf.file_writer import write_okf_files


def test_convert_to_okf_calls_llama_and_writes_files(monkeypatch, tmp_path):
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
        "retrieval_sections": [],
    }
    request = {}
    index = tmp_path / "knowledge_base" / "index.md"
    index.parent.mkdir()
    index.write_text("# Existing knowledge\n", encoding="utf-8")

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(result)}}]}

    def post(url, **kwargs):
        request.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr(main.httpx, "post", post)
    monkeypatch.setattr(main.settings, "llama_base_url", "http://llama:8080/v1")
    monkeypatch.setattr(main.settings, "llama_api_key", SecretStr("secret"))
    monkeypatch.setattr(main.settings, "llama_model", "local")

    converted = main.convert_to_okf(extraction, tmp_path)

    assert converted == result
    assert request["url"] == "http://llama:8080/v1/chat/completions"
    assert request["headers"] == {"Authorization": "Bearer secret"}
    assert request["json"]["model"] == "local"
    assert request["json"]["response_format"] == {"type": "json_object"}
    payload = json.loads(request["json"]["messages"][1]["content"])
    assert payload["source_id"] == "abc123"
    assert "knowledge_base_state" not in payload
    assert (tmp_path / "knowledge_base" / "policies" / "sign-in-policy.md").is_file()
    assert (tmp_path / "knowledge_base" / "index.md").read_text(encoding="utf-8") == (
        '---\nokf_version: "0.2"\n---\n\n'
        "# Organization Knowledge Base\n\n## Categories\n\n"
        "- [Policies](./policies/index.md) - Policies documents.\n"
    )
    assert (tmp_path / "knowledge_base" / "policies" / "index.md").read_text(
        encoding="utf-8"
    ) == "# Policies\n\n- [Sign In Policy](./sign-in-policy.md) - Employees must sign in.\n"


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


def test_convert_to_okf_rejects_invalid_llm_json(monkeypatch, tmp_path):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "not json"}}]}

    monkeypatch.setattr(main.httpx, "post", lambda *args, **kwargs: Response())
    monkeypatch.setattr(main.settings, "llama_api_key", SecretStr("secret"))

    with pytest.raises(main.OKFConversionError, match="invalid JSON"):
        main.convert_to_okf({"source_id": "abc123", "sections": []}, tmp_path)
