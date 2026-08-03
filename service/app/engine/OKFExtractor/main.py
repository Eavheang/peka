import json
from functools import lru_cache
from pathlib import Path

import httpx

from app.config import settings
from app.engine.OKFExtractor.extractor import write_okf_files


class OKFConversionError(RuntimeError):
    pass


def convert_to_okf(extraction: dict, base_dir: Path) -> dict:
    if settings.llama_api_key is None:
        raise OKFConversionError("LLAMA_API_KEY is not configured")

    payload = dict(extraction)
    indexes = _existing_indexes(base_dir)
    if indexes:
        payload["knowledge_base_state"] = {"index_files": indexes}

    try:
        response = httpx.post(
            f"{settings.llama_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.llama_api_key.get_secret_value()}"
            },
            json={
                "model": settings.llama_model,
                "messages": [
                    {"role": "system", "content": _prompt()},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                "response_format": {"type": "json_object"},
            },
            timeout=600,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        raise OKFConversionError("Unable to generate OKF output") from error

    try:
        result = json.loads(content)
    except (json.JSONDecodeError, TypeError) as error:
        raise OKFConversionError("LLM returned invalid JSON") from error

    try:
        write_okf_files(result, base_dir)
    except ValueError as error:
        raise OKFConversionError(str(error)) from error
    return result


@lru_cache(maxsize=1)
def _prompt() -> str:
    return Path(__file__).with_name("prompt.txt").read_text(encoding="utf-8")


def _existing_indexes(base_dir: Path) -> list[dict[str, str]]:
    knowledge_base = base_dir / "knowledge_base"
    if not knowledge_base.is_dir():
        return []
    return [
        {
            "path": path.relative_to(base_dir).as_posix(),
            "content": path.read_text(encoding="utf-8"),
        }
        for path in sorted(knowledge_base.rglob("index.md"))
    ]
