import json
from urllib.parse import urlparse

import httpx
import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, SecretStr, field_validator

from app.auth.routes import admin_only
from app.database import get_connection

router = APIRouter(prefix="/admin/settings/providers", tags=["admin settings"])


class ProviderSettingsUpdate(BaseModel):
    llm_base_url: str
    llm_api_key: SecretStr | None = None
    llm_model: str
    exa_base_url: str = "https://api.exa.ai"
    exa_api_key: SecretStr | None = None

    @field_validator("llm_base_url", "exa_base_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Must be an HTTP(S) URL")
        return value.rstrip("/")


def _stored() -> dict:
    try:
        with get_connection() as connection:
            row = connection.execute("SELECT value FROM provider_settings WHERE id = 1").fetchone()
    except psycopg.Error:
        return {}
    return row["value"] if row else {}


@router.get("")
def get_provider_settings(_: dict = Depends(admin_only)) -> dict:
    config = provider_config()
    return {
        "llm_base_url": config["llm_base_url"],
        "llm_model": config["llm_model"],
        "llm_configured": bool(config["llm_api_key"]),
        "exa_base_url": config["exa_base_url"],
        "exa_configured": bool(config["exa_api_key"]),
    }


@router.put("")
def update_provider_settings(data: ProviderSettingsUpdate, _: dict = Depends(admin_only)) -> dict:
    previous = _stored()
    value = {
        "llm_base_url": data.llm_base_url,
        "llm_model": data.llm_model,
        "llm_api_key": data.llm_api_key.get_secret_value() if data.llm_api_key else previous.get("llm_api_key", ""),
        "exa_base_url": data.exa_base_url,
        "exa_api_key": data.exa_api_key.get_secret_value() if data.exa_api_key else previous.get("exa_api_key", ""),
    }
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO provider_settings (id, value) VALUES (1, %s::jsonb) "
            "ON CONFLICT (id) DO UPDATE SET value = EXCLUDED.value",
            (json.dumps(value),),
        )
    return get_provider_settings(_)


def provider_config() -> dict:
    from app.config import settings

    saved = _stored()
    return {
        "llm_base_url": saved.get("llm_base_url") or settings.llm_base_url,
        "llm_api_key": saved.get("llm_api_key") or settings.llm_api_key.get_secret_value(),
        "llm_model": saved.get("llm_model") or settings.llm_model,
        "exa_base_url": saved.get("exa_base_url") or settings.exa_base_url,
        "exa_api_key": saved.get("exa_api_key") or (settings.exa_api_key.get_secret_value() if settings.exa_api_key else None),
    }


@router.post("/test/{provider}")
def test_provider(provider: str, _: dict = Depends(admin_only)) -> dict:
    config = provider_config()
    if provider == "llm":
        base_url, key = config.get("llm_base_url"), config.get("llm_api_key")
        url = f"{base_url}/models" if base_url else ""
    elif provider == "exa":
        base_url, key = config.get("exa_base_url"), config.get("exa_api_key")
        url = f"{base_url}/search" if base_url else ""
    else:
        raise HTTPException(status_code=404, detail="Unknown provider")
    if not url or not key:
        return {"ok": False, "status": None, "message": "Provider credentials are not configured."}
    try:
        response = httpx.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=10) if provider == "llm" else httpx.post(
            url, headers={"Authorization": f"Bearer {key}"},
            json={"query": "connection test", "type": "auto", "numResults": 1}, timeout=10,
        )
        return {"ok": response.is_success, "status": response.status_code,
                "message": "Connection successful." if response.is_success else f"Provider returned HTTP {response.status_code}."}
    except httpx.HTTPError:
        return {"ok": False, "status": None, "message": "Unable to connect to provider. Check the URL and network."}
