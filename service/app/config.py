from pathlib import Path

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PEKA Service"
    debug: bool = False
    database_url: str = "postgresql://peka:peka_dev_password@localhost:5432/peka"
    file_storage_dir: Path = Path("storage")
    llm_base_url: str = "http://localhost:8080/v1"
    llm_api_key: SecretStr | None = None
    llm_model: str = "local"
    embedding_base_url: str = "http://localhost:8081/v1"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimensions: int = 1024
    embedding_batch_size: int = 16
    jwt_secret_key: SecretStr
    jwt_access_token_expire_minutes: int = 30
    jwt_issuer: str = "peka-service"
    jwt_audience: str = "peka-api"
    admin_email: str | None = None
    admin_password: SecretStr | None = None

    @model_validator(mode="after")
    def validate_auth(self) -> "Settings":
        if len(self.jwt_secret_key.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        if not 1 <= self.jwt_access_token_expire_minutes <= 60:
            raise ValueError("JWT_ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 60")
        if (self.admin_email is None) != (self.admin_password is None):
            raise ValueError("ADMIN_EMAIL and ADMIN_PASSWORD must be supplied together")
        if self.admin_password is not None and not 12 <= len(self.admin_password.get_secret_value()) <= 1024:
            raise ValueError("ADMIN_PASSWORD must be between 12 and 1024 characters")
        return self

    @field_validator("jwt_secret_key")
    @classmethod
    def reject_placeholder_secret(cls, value: SecretStr) -> SecretStr:
        if value.get_secret_value().startswith(("CHANGE-ME", "replace-with-at-least-32-random-characters")):
            raise ValueError("JWT_SECRET_KEY must be replaced with a random secret")
        return value

    @field_validator("admin_email")
    @classmethod
    def normalize_admin_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if len(value) > 320 or value.count("@") != 1 or any(not part for part in value.split("@")):
            raise ValueError("ADMIN_EMAIL must be a valid email")
        return value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
