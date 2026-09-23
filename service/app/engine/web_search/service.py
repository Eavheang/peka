import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.workspace_settings import provider_config


def web_search(query: str) -> list[dict[str, Any]]:
    config = provider_config()
    if not config["exa_api_key"] or not config["exa_api_key"].strip():
        raise RuntimeError("Web search is not configured")

    try:
        response = httpx.post(
            f"{config['exa_base_url'].rstrip('/')}/search",
            headers={"Authorization": f"Bearer {config['exa_api_key']}"},
            json={
                "query": query,
                "type": "auto",
                "numResults": settings.web_search_top_k,
                "contents": {"highlights": True},
            },
            timeout=settings.web_search_timeout,
        )
        response.raise_for_status()
        results = response.json()["results"]
    except httpx.HTTPStatusError as error:
        raise RuntimeError(f"Web search failed with HTTP {error.response.status_code}") from error
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        raise RuntimeError("Unable to complete web search") from error

    if not isinstance(results, list):
        raise RuntimeError("Web search returned an invalid response")

    normalized = []
    for result in results:
        if not isinstance(result, dict):
            continue
        url = result.get("url")
        if not _is_http_url(url):
            continue
        title = result.get("title")
        if not isinstance(title, str) or not title.strip():
            title = url
        content = _result_content(result)
        if content == title:
            content = ""
        else:
            for title_prefix in (f"# {title}", title):
                if content.startswith(f"{title_prefix}\n"):
                    content = content[len(title_prefix):].lstrip()
                    break
        if not content:
            continue
        score = result.get("score", 0)
        normalized.append({
            "title": title.strip(),
            "heading": "",
            "snippet": content[:300],
            "content": content[:4000],
            "source_locations": [],
            "score": float(score) if isinstance(score, (int, float)) else 0.0,
            "url": url,
        })
    return normalized


def _is_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _result_content(result: dict[str, Any]) -> str:
    highlights = result.get("highlights")
    if isinstance(highlights, list):
        excerpts = [
            item.strip()
            for item in highlights
            if isinstance(item, str) and item.strip() and item.strip() not in {"...", "…"}
        ]
        content = "\n\n".join(excerpts)
        if content:
            return _clean_excerpt(content)
    text = result.get("text")
    return _clean_excerpt(text) if isinstance(text, str) else ""


def _clean_excerpt(content: str) -> str:
    content = re.sub(r"(?m)^[ \t]*(?:\.\.\.|…)[ \t]*$", "", content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()
